#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - dev scraper for ONE keyword (no strategy.json, no production overwrite).

用法：
    python backend/dev/asin_dev_scraper.py --country US --keyword "storage bins"
    python backend/dev/asin_dev_scraper.py --country US --keyword "..." --keep-browser

铁律：复用 crossmart-monitor 的 browser/edge_session.open_edge()，强制端口 9225
+ 默认 profile（不新建任何 --user-data-dir）。

参考：
    - 卖家精灵插件字段解析复用 backend/selectors/fetch_keyword_asins.py 的 SS_REGEX
      与 parse_ss_text（与 monitor asin_monitor.py 同思路：regex over Chinese text）
    - SRP 抓取复用 fetch_srp_via_cdp() 整段导航 + scroll + 等待 + 提取 JS
"""
import sys, os, json, time, argparse

# ─── 路径 ───
_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_HERE)                  # backend/
SEL_ROOT = os.path.dirname(BACKEND)               # crossmart-selector/
OUT_DIR = os.path.join(_HERE, "test_output")

for p in (BACKEND,):
    if p not in sys.path:
        sys.path.insert(0, p)

# ⚠️ import 顺序很重要：
#   selectors.fetch_keyword_asins 会在 import 时把 crossmart-monitor/backend 加到
#   sys.path[0]，污染 browser 包解析（monitor 的 browser 没有 edge_session.py）。
#   所以 browser.edge_session 必须先 import。
from browser.edge_session import open_edge, ensure_default_edge

# 复用现有生产代码
from selectors.fetch_keyword_asins import (
    fetch_srp_via_cdp,        # 导航 + scroll + 等待 + 提取 JS（已含 SS 等待逻辑）
    parse_ss_text,            # 中文 regex 解析 24 个 SS 字段
    SS_REGEX,
    EXTRACT_JS,
)


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_one(country, keyword, keep_browser=False):
    """跑一次：铁律→打开新 tab→SRP 抓取→关闭 tab。返回 dict 或 None。"""
    log(f"=== {country} | {keyword} ===")

    # 1. 铁律连通性自检（端口 9225 + 默认 profile）
    if not ensure_default_edge():
        log("FAIL Edge 默认账户未就绪。请先手动按铁律启动（见 browser/README_IRON_RULE.md）")
        return None

    br = open_edge(auto_start=False)
    try:
        # 2. 在新 tab 抓取（不污染现有 tab）
        log("  open new tab")
        rec = fetch_srp_via_cdp(country, keyword)
        if rec is None:
            log("  FAIL fetch_srp_via_cdp returned None")
            return None
        return rec
    finally:
        if not keep_browser:
            br.close()
            log("  Edge WS closed")
        else:
            log("  --keep-browser: Edge WS 保留，你可以手动看页面")


def summarize(rec):
    """打印抓取结果摘要。"""
    if not rec:
        return
    detail = rec.get("detail", [])
    log(f"  ASINs: {rec.get('asin_count', 0)}")

    # SS 字段覆盖率
    if detail:
        sample = len(detail)
        keys = ["ss_brand", "ss_seller", "ss_fulfillment", "ss_bsr_main",
                "ss_monthly_sales_parent", "ss_variants", "ss_price",
                "ss_rating", "ss_review_count", "ss_launch_date",
                "ss_days_listed", "ss_sponsored"]
        log("  SS 字段覆盖率：")
        for k in keys:
            n = sum(1 for a in detail if a.get(k))
            flag = "✓" if n >= sample * 0.7 else ("△" if n > 0 else "✗")
            log(f"    {flag} {k}: {n}/{sample}")

    # 价格 / 评分 / 评论 摘要
    prices = [float(re.sub(r"[^\d.]", "", a.get("price", "")))
              for a in detail if a.get("price")]
    prices = [p for p in prices if 0 < p < 1000]
    if prices:
        log(f"  价格区间: ${min(prices):.2f} - ${max(prices):.2f} (均值 ${sum(prices)/len(prices):.2f})")
    sponsored = sum(1 for a in detail if a.get("sponsored"))
    if sponsored:
        log(f"  ⚠️ Sponsored: {sponsored}/{len(detail)}")


def save(rec, country, keyword, out_dir):
    """保存到 dev/test_output/。"""
    os.makedirs(out_dir, exist_ok=True)
    safe_kw = re.sub(r"[^\w]+", "_", keyword).strip("_")[:30]
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{country}_{safe_kw}_{ts}.json")

    payload = {
        "meta": {
            "country": country,
            "keyword": keyword,
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "asin_count": rec.get("asin_count", 0),
            "source": "dev/asin_dev_scraper.py via browser.edge_session (iron rule)",
        },
        "record": rec,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"  SAVED → {path}")
    return path


import re  # 价格 parse


def main():
    ap = argparse.ArgumentParser(description="Selector dev scraper (1 keyword)")
    ap.add_argument("--country", required=True, choices=["US", "UK", "DE", "CA"])
    ap.add_argument("--keyword", required=True, help="Amazon search keyword")
    ap.add_argument("--keep-browser", action="store_true",
                    help="抓完不关 Edge，方便人眼验证页面")
    ap.add_argument("--out-dir", default=OUT_DIR,
                    help=f"输出目录（默认 {OUT_DIR}）")
    args = ap.parse_args()

    rec = fetch_one(args.country, args.keyword, keep_browser=args.keep_browser)
    if not rec:
        sys.exit(1)
    summarize(rec)
    save(rec, args.country, args.keyword, args.out_dir)


if __name__ == "__main__":
    main()