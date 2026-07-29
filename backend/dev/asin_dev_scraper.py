#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - dev scraper for ONE keyword (no strategy.json, no production overwrite).

用法：
    python backend/dev/asin_dev_scraper.py --country US --keyword "storage bins"
    python backend/dev/asin_dev_scraper.py --country US --keyword "..." --keep-browser

技术栈：
    Selenium 4.6+ 接管 Edge（Selenium 内置 selenium-manager 自动下匹配 Edge 版本的 msedgedriver）。
    不依赖手工 --remote-debugging-port=9225（CDP 在某些 Edge 150 + Windows 11 环境下静默 bind 失败）。

    ⚠️ 重要：脚本里 Selenium Edge 是不指定 --user-data-dir 的——让 Edge 自己用临时 profile。
        你登录态/卖家精灵插件不会自动有，但**保证脚本能跑起来并打开目标 Amazon 关键词页面**。
        截图 + page_source dump 会保存到 dev/test_output/，你可以一眼看到脚本效果。

下一步（用户确认后）：
    - 想保留卖家精灵字段：用 cdp_bridge + 我之前写的 detect_edge_cdp_port 智能探测
    - 只想看脚本能跑：现在这版就够
"""
import sys, os, json, time, argparse, re
sys.stdout.reconfigure(encoding='utf-8')

# ─── 路径 ───
_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_HERE)                  # backend/
SEL_ROOT = os.path.dirname(BACKEND)               # crossmart-selector/
OUT_DIR = os.path.join(_HERE, "test_output")

# Selenium 4.6+ 内置 selenium-manager 自动下匹配 Edge 版本的 msedgedriver
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def build_driver():
    """启 Edge：不指定 --user-data-dir（用临时 profile，绕开 Edge 150 + 9225 bind bug）。"""
    options = EdgeOptions()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--start-maximized")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.page_load_strategy = "normal"
    # Selenium 内部 selenium-manager 自动下匹配 Edge 150 的 msedgedriver
    driver = webdriver.Edge(options=options)
    return driver


def search_amazon(driver, country, keyword):
    """根据 country 选 Amazon 域，跳进关键词搜索结果页，等渲染完。"""
    domain = {
        "US": "https://www.amazon.com/",
        "UK": "https://www.amazon.co.uk/",
        "DE": "https://www.amazon.de/",
        "CA": "https://www.amazon.ca/",
    }[country]
    log(f"  → {domain}")
    driver.get(domain)
    log(f"  ✓ title: {driver.title[:60]}")

    # 找搜索框（Amazon 主页/结果页都用 id='twotabsearchtextbox'）
    log(f"  搜索框 send_keys: {keyword!r}")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
    )
    box = driver.find_element(By.ID, "twotabsearchtextbox")
    box.clear()
    box.send_keys(keyword)
    box.submit()

    # 等搜索结果至少有一个 product card
    log("  等结果渲染…")
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
        )
    )
    # 让 JS / lazy-load / Sponsored 标签完整跑一下
    time.sleep(3)
    return driver.current_url


def collect_summary(driver):
    """扫一遍当前 SRP，产一个摘要 dict（不依赖卖家精灵）。"""
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div[data-component-type='s-search-result']"
    )
    log(f"  找到 {len(cards)} 个 product card")

    summary = {
        "asin_count": len(cards),
        "sponsored_count": 0,
        "title_samples": [],
        "price_samples": [],
        "rating_samples": [],
        "asin_samples": [],
    }

    for i, card in enumerate(cards):
        # sponsored 标签
        sel_sp = ".s-sponsored-label-text, [aria-label*='Sponsored'], .puis-sponsored-label"
        sponsored = bool(card.find_elements(By.CSS_SELECTOR, sel_sp))
        if sponsored:
            summary["sponsored_count"] += 1

        # 标题
        try:
            title_el = card.find_element(By.CSS_SELECTOR, "h2 span")
            title = title_el.text.strip()
        except Exception:
            title = ""
        if title and len(summary["title_samples"]) < 5:
            summary["title_samples"].append(title[:80])

        # 价格
        try:
            price_els = card.find_elements(By.CSS_SELECTOR, ".a-price .a-offscreen")
            if price_els:
                ptext = price_els[0].get_attribute("textContent").strip()
                m = re.search(r"(\d+(?:\.\d+)?)", ptext)
                if m:
                    summary["price_samples"].append(float(m.group(1)))
        except Exception:
            pass

        # 评分
        try:
            rating_el = card.find_element(By.CSS_SELECTOR, "[aria-label*='stars']")
            label = rating_el.get_attribute("aria-label") or ""
            m = re.search(r"([\d.]+)\s*out of", label)
            if m:
                summary["rating_samples"].append(float(m.group(1)))
        except Exception:
            pass

        # ASIN
        try:
            aid = card.get_attribute("data-asin")
            if aid and len(summary["asin_samples"]) < 5:
                summary["asin_samples"].append(aid)
        except Exception:
            pass

    return summary


def save_artifacts(driver, country, keyword, summary, out_dir):
    """保存：截屏 + page_source + summary JSON 三件套。同时镜像到 frontend/dev_runs 让 GitHub Pages 可看。"""
    os.makedirs(out_dir, exist_ok=True)
    safe_kw = re.sub(r"[^\w]+", "_", keyword).strip("_")[:30]
    ts = time.strftime("%Y%m%d_%H%M%S")

    base = f"{country}_{safe_kw}_{ts}"
    out_screenshot = os.path.join(out_dir, f"{base}_screenshot.png")
    driver.save_screenshot(out_screenshot)
    log(f"  ✓ screenshot → {out_screenshot}")

    out_html = os.path.join(out_dir, f"{base}.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    log(f"  ✓ html ({len(driver.page_source)} chars) → {out_html}")

    summary["screenshot_path"] = out_screenshot
    summary["html_path"] = out_html
    summary["meta"] = {
        "country": country,
        "keyword": keyword,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "driver": "selenium-webdriver (Edge auto-managed)",
        "base_name": base,
    }

    out_json = os.path.join(out_dir, f"{base}_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"  ✓ summary → {out_json}")

    # 镜像到 frontend/dev_runs/ 让 GitHub Pages 直接可访问
    # git push 之后用户访问 https://charlescome1995-prog.github.io/crossmart-selector/dev_runs.html
    pages_dir = os.path.join(SEL_ROOT, "frontend", "dev_runs")
    os.makedirs(pages_dir, exist_ok=True)
    import shutil
    pages_screenshot = os.path.join(pages_dir, f"{base}_screenshot.png")
    pages_summary = os.path.join(pages_dir, f"{base}_summary.json")
    shutil.copy(out_screenshot, pages_screenshot)
    shutil.copy(out_json, pages_summary)
    log(f"  ✓ mirror to GitHub Pages → {pages_dir}/{base}_*")

    # 重新生成 dev_runs/index.json（每次跑都覆盖）
    rebuild_index(pages_dir)

    return out_screenshot, out_json


def rebuild_index(pages_dir):
    """重建 frontend/dev_runs/index.json（让 dev_runs.html 拉数据用）。"""
    index_path = os.path.join(pages_dir, "index.json")
    runs = []
    for f in sorted(os.listdir(pages_dir), reverse=True):
        if f.endswith("_summary.json"):
            try:
                with open(os.path.join(pages_dir, f), "r", encoding="utf-8") as fp:
                    s = json.load(fp)
                meta = s.get("meta", {})
                runs.append({
                    "base": meta.get("base_name", f.replace("_summary.json", "")),
                    "country": meta.get("country", ""),
                    "keyword": meta.get("keyword", ""),
                    "scraped_at": meta.get("scraped_at", ""),
                    "asin_count": s.get("asin_count", 0),
                    "sponsored_count": s.get("sponsored_count", 0),
                    "title_first": (s.get("title_samples") or [""])[0],
                    "price_min": min(s["price_samples"]) if s.get("price_samples") else None,
                    "price_max": max(s["price_samples"]) if s.get("price_samples") else None,
                    "price_avg": round(sum(s["price_samples"]) / len(s["price_samples"]), 2)
                                  if s.get("price_samples") else None,
                    "rating_samples": (s.get("rating_samples") or [])[:5],
                    "asin_samples": (s.get("asin_samples") or [])[:5],
                })
            except Exception as e:
                log(f"  ⚠ 解析 {f} 失败: {e}")
    with open(index_path, "w", encoding="utf-8") as fp:
        json.dump({"runs": runs}, fp, ensure_ascii=False, indent=2)
    log(f"  ✓ index.json 写完 ({len(runs)} runs)")


def render_summary(summary):
    """打印人看的摘要。"""
    log("─" * 56)
    log(f"  ASINs:               {summary.get('asin_count', 0)}")
    log(f"  Sponsored count:     {summary.get('sponsored_count', 0)}")
    prices = summary.get("price_samples", [])
    if prices:
        log(f"  价格区间:            ${min(prices):.2f} - ${max(prices):.2f} (均值 ${sum(prices)/len(prices):.2f})")
    ratings = summary.get("rating_samples", [])
    if ratings:
        log(f"  评分:                {ratings[:5]}")
    log(f"  示例 ASIN:           {summary.get('asin_samples', [])[:5]}")
    log(f"  示例标题:")
    for t in summary.get("title_samples", []):
        log(f"    • {t}")
    log("─" * 56)


def main():
    ap = argparse.ArgumentParser(description="Selector dev scraper (Selenium, 1 keyword)")
    ap.add_argument("--country", required=True, choices=["US", "UK", "DE", "CA"])
    ap.add_argument("--keyword", required=True, help="Amazon search keyword")
    ap.add_argument("--keep-browser", action="store_true",
                    help="抓完不关 Edge，方便人眼验证页面")
    ap.add_argument("--out-dir", default=OUT_DIR,
                    help=f"输出目录（默认 {OUT_DIR}）")
    args = ap.parse_args()

    log(f"=== {args.country} | {args.keyword} ===")
    log("启 Edge driver（Selenium 自动下匹配 Edge 版本的 msedgedriver）…")
    driver = build_driver()
    log(f"  ✓ driver ready, current URL: {driver.current_url}")

    try:
        try:
            search_amazon(driver, args.country, args.keyword)
            log(f"  ✓ final URL: {driver.current_url}")
        except Exception as e:
            log(f"  ✗ 搜索失败: {type(e).__name__}: {e}")
            return 2

        summary = collect_summary(driver)
        render_summary(summary)
        shot, jpath = save_artifacts(driver, args.country, args.keyword, summary, args.out_dir)
        log(f"\n✅ 完成！截屏：{shot}")
        return 0
    finally:
        if not args.keep_browser:
            driver.quit()
            log("  Edge quit")
        else:
            log("  --keep-browser: Edge 保留不关，自己手动看")


if __name__ == "__main__":
    sys.exit(main())
