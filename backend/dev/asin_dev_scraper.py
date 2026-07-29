#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - dev scraper for ONE keyword.

复用项目主抓取流程：
    backend/selectors/fetch_keyword_asins.py
        - start_edge_cdp()      启 Edge 临时 profile + --load-extension=卖家精灵
        - fetch_srp_via_cdp()   SRP 抓取主体（含 SS 注入 retry + _is_sufficient 判定）
        - parse_ss_text()       卖家精灵 24 字段解析
    backend/browser/cdp_bridge.py
        - CDPBrowser.screenshot()   SRP 截屏
        - ensure_edge_running()     已修过 9225 静默 bind bug

用法：
    python backend/dev/asin_dev_scraper.py --country US --keyword "storage bins"
    python backend/dev/asin_dev_scraper.py --country US --keyword "..." --keep-browser

产物：
    backend/dev/test_output/{base}_summary.json   完整 SS 24 字段
    backend/dev/test_output/{base}_screenshot.png SRP 截屏
    frontend/dev_runs/{base}_summary.json         镜像（GitHub Pages）
    frontend/dev_runs/{base}_screenshot.png       镜像
    frontend/dev_runs/index.json                  自动重建
"""
import sys, os, json, time, argparse, re, base64
sys.stdout.reconfigure(encoding="utf-8")

# ─── 路径 ───
_HERE = os.path.dirname(os.path.abspath(__file__))              # backend/dev/
BACKEND = os.path.dirname(_HERE)                                # backend/
SEL_ROOT = os.path.dirname(BACKEND)                             # crossmart-selector/
OUT_DIR = os.path.join(_HERE, "test_output")

# 让 dev_scraper 能复用主流程模块
for p in (BACKEND, os.path.join(BACKEND, "selectors"), os.path.join(BACKEND, "browser")):
    if p not in sys.path:
        sys.path.insert(0, p)

# 项目主抓取主体（卖家精灵注入 + 24 字段 + retry）
from fetch_keyword_asins import (
    start_edge_cdp, fetch_srp_via_cdp, EDGE_CDP_PORT,
)
# 截屏底座
from cdp_bridge import CDPBrowser


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def summarize(rec):
    """从完整 rec 算一份 dev_runs 友好的摘要（含 SS 关键字段统计）。"""
    detail = rec.get("detail") or []
    s = {
        "asin_count": rec.get("asin_count", len(detail)),
        "sponsored_count": sum(1 for a in detail if a.get("sponsored")),
        "ss_injected_count": sum(1 for a in detail if a.get("ss_has_ss")),
        "asins_with_ss_brand": sum(1 for a in detail if a.get("ss_brand")),
        "asins_with_ss_seller": sum(1 for a in detail if a.get("ss_seller")),
        "asins_with_ss_bsr": sum(1 for a in detail if a.get("ss_bsr_main")),
        "asins_with_ss_launch": sum(1 for a in detail if a.get("ss_launch_date")),
        "asins_with_ss_monthly": sum(1 for a in detail if a.get("ss_monthly_sales_parent")),
        "asins_with_ss_traffic": sum(1 for a in detail if a.get("ss_all_traffic_words")),
        # 样本（最多 5 个）
        "title_samples": [a.get("title", "")[:80] for a in detail[:5]],
        "price_samples": [_parse_price(a.get("price", "")) for a in detail
                          if _parse_price(a.get("price", "")) is not None],
        "rating_samples": [_parse_rating(a.get("rating", "")) for a in detail
                           if _parse_rating(a.get("rating", "")) is not None],
        "asin_samples": [a.get("asin") for a in detail[:5] if a.get("asin")],
        # SS 字段样本
        "brand_samples": [a.get("ss_brand", "") for a in detail[:5] if a.get("ss_brand")],
        "seller_samples": [a.get("ss_seller", "") for a in detail[:5] if a.get("ss_seller")],
        "bsr_samples": [a.get("ss_bsr_main", "") for a in detail[:5] if a.get("ss_bsr_main")],
        "monthly_sales_samples": [a.get("ss_monthly_sales_parent", "")
                                  for a in detail[:5] if a.get("ss_monthly_sales_parent")],
        "launch_days_samples": [a.get("ss_days_listed", "")
                                for a in detail[:5] if a.get("ss_days_listed")],
        "traffic_samples": [a.get("ss_all_traffic_words", "")
                            for a in detail[:5] if a.get("ss_all_traffic_words")],
        # 自然位分布
        "natural_position_buckets": _bucket_natural_positions(detail),
        # 上架天数均值（数字化的）
        "avg_days_listed": _avg_days_listed(detail),
        # 平均流量词
        "avg_traffic_words": _avg_int(detail, "ss_all_traffic_words"),
    }
    return s


def _parse_price(price_text):
    if not price_text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", price_text.replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_rating(rating_text):
    if not rating_text:
        return None
    m = re.search(r"([\d.]+)", rating_text)
    return float(m.group(1)) if m else None


def _bucket_natural_positions(detail):
    """自然位分布：1-10 / 11-20 / 21-30 / 31+ / 未注入"""
    b = {"1-10": 0, "11-20": 0, "21-30": 0, "31+": 0, "未注入": 0}
    for a in detail:
        v = a.get("ss_natural_position", "") or ""
        m = re.search(r"(\d+)", v)
        if not m:
            b["未注入"] += 1
            continue
        n = int(m.group(1))
        if n <= 10: b["1-10"] += 1
        elif n <= 20: b["11-20"] += 1
        elif n <= 30: b["21-30"] += 1
        else: b["31+"] += 1
    return b


def _avg_days_listed(detail):
    vals = []
    for a in detail:
        v = a.get("ss_days_listed", "")
        if v:
            try:
                vals.append(int(str(v).replace(",", "")))
            except (ValueError, TypeError):
                pass
    return round(sum(vals) / len(vals)) if vals else None


def _avg_int(detail, key):
    vals = []
    for a in detail:
        v = a.get(key, "")
        if v:
            try:
                vals.append(int(str(v).replace(",", "")))
            except (ValueError, TypeError):
                pass
    return round(sum(vals) / len(vals)) if vals else None


def take_screenshot(br, port=EDGE_CDP_PORT):
    """通过 CDPBrowser 截当前页面。返回 PNG 文件路径。"""
    # 找到当前 tab 的 WebSocket 重连（fetch_srp_via_cdp 跑完后 tab 可能变）
    br._refresh_tabs()
    if not br._raw_tabs:
        return None
    target = br._raw_tabs[0]
    ws_url = target.get("webSocketDebuggerUrl")
    try:
        import websocket
        if br.ws:
            br.ws.close()
        br.ws = websocket.create_connection(ws_url, timeout=15)
        br.tab = target
        r = br.cmd("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        data = r.get("data", "")
        if data:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(OUT_DIR, f"dev_run_{ts}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
            return path
    except Exception as e:
        log(f"  ⚠ screenshot 失败: {e}")
    return None


def save_artifacts(rec, summary, country, keyword, screenshot_path):
    """保存 summary JSON（完整 rec 折叠进去）+ 镜像到 frontend/dev_runs/。"""
    os.makedirs(OUT_DIR, exist_ok=True)
    safe_kw = re.sub(r"[^\w]+", "_", keyword).strip("_")[:30]
    ts = time.strftime("%Y%m%d_%H%M%S")
    base = f"{country}_{safe_kw}_{ts}"

    # summary.json = dev 友好的摘要 + 完整 rec（前端按需展开）
    out = {
        "meta": {
            "country": country,
            "keyword": keyword,
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "driver": "Edge CDP via temp profile + SellerSprite extension",
            "cdp_port": EDGE_CDP_PORT,
            "base_name": base,
        },
        "summary": summary,
        "record": rec,   # 完整抓取结果（含 24 个 SS 字段）
        "screenshot_path": screenshot_path or "",
    }

    out_json = os.path.join(OUT_DIR, f"{base}_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log(f"  ✓ summary → {out_json}")

    # 镜像截屏到 frontend/dev_runs/
    pages_dir = os.path.join(SEL_ROOT, "frontend", "dev_runs")
    os.makedirs(pages_dir, exist_ok=True)
    pages_screenshot = os.path.join(pages_dir, f"{base}_screenshot.png")
    pages_summary = os.path.join(pages_dir, f"{base}_summary.json")

    if screenshot_path and os.path.exists(screenshot_path):
        import shutil
        shutil.copy(screenshot_path, pages_screenshot)
        log(f"  ✓ screenshot 镜像 → {pages_screenshot}")

    import shutil
    shutil.copy(out_json, pages_summary)
    log(f"  ✓ summary 镜像 → {pages_summary}")

    rebuild_index(pages_dir)
    return out_json


def rebuild_index(pages_dir):
    """重建 frontend/dev_runs/index.json（dev_runs.html 拉数据用）。"""
    index_path = os.path.join(pages_dir, "index.json")
    runs = []
    for f in sorted(os.listdir(pages_dir), reverse=True):
        if not f.endswith("_summary.json"):
            continue
        try:
            with open(os.path.join(pages_dir, f), "r", encoding="utf-8") as fp:
                payload = json.load(fp)
            meta = payload.get("meta", {}) or {}
            # 兼容两种格式：新版（summary 子对象） vs 旧版（扁平在顶层）
            summary = payload.get("summary", {}) or {}
            if not summary:
                # 旧 Selenium 版的 summary.json 是扁平的，把顶层当 summary
                summary = {k: v for k, v in payload.items() if k not in ("meta", "record")}
            runs.append({
                "base": meta.get("base_name", f.replace("_summary.json", "")),
                "country": meta.get("country", ""),
                "keyword": meta.get("keyword", ""),
                "scraped_at": meta.get("scraped_at", ""),
                # Amazon 自带
                "asin_count": summary.get("asin_count", 0),
                "sponsored_count": summary.get("sponsored_count", 0),
                "price_min": min(summary["price_samples"]) if summary.get("price_samples") else None,
                "price_max": max(summary["price_samples"]) if summary.get("price_samples") else None,
                "price_avg": round(sum(summary["price_samples"]) / len(summary["price_samples"]), 2)
                              if summary.get("price_samples") else None,
                "rating_samples": (summary.get("rating_samples") or [])[:5],
                "asin_samples": (summary.get("asin_samples") or [])[:5],
                "title_first": (summary.get("title_samples") or [""])[0],
                # SS 字段摘要
                "ss_injected_count": summary.get("ss_injected_count", 0),
                "ss_brand_count": summary.get("asins_with_ss_brand", 0),
                "ss_seller_count": summary.get("asins_with_ss_seller", 0),
                "ss_bsr_count": summary.get("asins_with_ss_bsr", 0),
                "ss_launch_count": summary.get("asins_with_ss_launch", 0),
                "ss_monthly_count": summary.get("asins_with_ss_monthly", 0),
                "ss_traffic_count": summary.get("asins_with_ss_traffic", 0),
                "avg_days_listed": summary.get("avg_days_listed"),
                "avg_traffic_words": summary.get("avg_traffic_words"),
                "natural_position_buckets": summary.get("natural_position_buckets", {}),
                "brand_samples": (summary.get("brand_samples") or [])[:3],
                "seller_samples": (summary.get("seller_samples") or [])[:3],
                "bsr_samples": (summary.get("bsr_samples") or [])[:3],
                "monthly_sales_samples": (summary.get("monthly_sales_samples") or [])[:3],
                "launch_days_samples": (summary.get("launch_days_samples") or [])[:3],
                "traffic_samples": (summary.get("traffic_samples") or [])[:3],
            })
        except Exception as e:
            log(f"  ⚠ 解析 {f} 失败: {e}")
    with open(index_path, "w", encoding="utf-8") as fp:
        json.dump({"runs": runs}, fp, ensure_ascii=False, indent=2)
    log(f"  ✓ index.json 写完 ({len(runs)} runs)")


def render_summary(summary):
    log("─" * 56)
    log(f"  ASINs:               {summary['asin_count']}")
    log(f"  Sponsored:           {summary['sponsored_count']}")
    log(f"  SS 注入 ASINs:       {summary['ss_injected_count']} / {summary['asin_count']}")
    log(f"  含品牌字段:          {summary['asins_with_ss_brand']}")
    log(f"  含卖家字段:          {summary['asins_with_ss_seller']}")
    log(f"  含 BSR 字段:         {summary['asins_with_ss_bsr']}")
    log(f"  含上架日期:          {summary['asins_with_ss_launch']}")
    log(f"  含月销量父体:        {summary['asins_with_ss_monthly']}")
    log(f"  含流量词:            {summary['asins_with_ss_traffic']}")
    if summary.get("avg_days_listed"):
        log(f"  均上架天数:          {summary['avg_days_listed']}")
    if summary.get("avg_traffic_words"):
        log(f"  均流量词数:          {summary['avg_traffic_words']}")
    log(f"  自然位分布:          {summary['natural_position_buckets']}")
    prices = summary.get("price_samples", [])
    if prices:
        log(f"  价格区间:            ${min(prices):.2f} - ${max(prices):.2f} (均值 ${sum(prices)/len(prices):.2f})")
    ratings = summary.get("rating_samples", [])
    if ratings:
        log(f"  评分样本:            {ratings[:5]}")
    log("─" * 56)


def main():
    ap = argparse.ArgumentParser(description="Selector dev scraper (复用主抓取流程)")
    ap.add_argument("--country", required=True, choices=["US", "UK", "DE", "CA"])
    ap.add_argument("--keyword", required=True, help="Amazon search keyword")
    ap.add_argument("--keep-browser", action="store_true",
                    help="抓完不关 Edge，方便人眼验证页面")
    ap.add_argument("--out-dir", default=OUT_DIR,
                    help=f"输出目录（默认 {OUT_DIR}）")
    args = ap.parse_args()

    log(f"=== {args.country} | {args.keyword} ===")
    log("启 Edge (临时 profile + 卖家精灵 extension)…")
    if not start_edge_cdp(port=EDGE_CDP_PORT):
        log("FAIL Edge CDP 启动失败")
        return 2

    # CDPBrowser 拿来截图（跟 fetch_srp_via_cdp 共享同一个 9225 端口）
    br = CDPBrowser(auto_start=False)
    log(f"  ✓ CDP 已连，标签页 {len(br.tabs)} 个")

    try:
        log("  fetch_srp_via_cdp (含 retry)…")
        rec = fetch_srp_via_cdp(args.country, args.keyword, port=EDGE_CDP_PORT)
        if not rec:
            log("FAIL fetch_srp_via_cdp 返回空")
            return 3

        log(f"  ✓ rec: asin_count={rec.get('asin_count')}, detail={len(rec.get('detail', []))}")

        # 截图（先回滚到顶部，让首屏 SS 容器可见）
        try:
            br.eval("window.scrollTo(0, 0)")
            time.sleep(1)
        except Exception:
            pass
        screenshot_path = take_screenshot(br)
        if screenshot_path:
            log(f"  ✓ screenshot → {screenshot_path}")

        summary = summarize(rec)
        render_summary(summary)
        out_json = save_artifacts(rec, summary, args.country, args.keyword, screenshot_path)
        log(f"\n✅ 完成！摘要：{out_json}")
        return 0
    finally:
        if not args.keep_browser:
            br.close()
            log("  WS closed")
        else:
            log("  --keep-browser: Edge 保留不关，自己手动看")


if __name__ == "__main__":
    sys.exit(main())