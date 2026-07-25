#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - keyword -> Amazon srp full-page ASIN scraper

Input  : crossmart-selector/frontend/data/strategy.json (Part B, 4 buckets)
Output : crossmart-selector/frontend/data/keyword_asins.json
         { records: { COUNTRY::keyword: { asin_list, detail, seller_sprite } } }
         whole-page overwrite (Yan Xu 2026-07-24)

Depends:
  - crossmart-monitor/backend/browser/{cdp_bridge,amazon_browser,sprite_bridge,asin_monitor}.py
  - **Edge 默认 profile (闫旭账户) + 端口 9225 + 卖家精灵扩展 (用户手动激活一次)**

Rules:
  - 浏览器只用 Edge 默认账户 (TOOLS.md 红线 2026-07-25)
  - 不许 chrome.exe / chromium.exe (这条是底线)
  - 不许 --user-data-dir 自定义路径
  - 不许 OpenClaw 管理的 profile
  - 整页抓 (48 ASINs, no limit)
  - 字段全要 (SellerSprite ext + Amazon page native)

历史:
  - 2026-07-24  1b32058  初版 (commit, Edge 9225 在本机不响应 --remote-debugging-port)
  - 2026-07-25  修 connect_tab(tab_url_filter=...) bug -> connect_tab(idx=0)
                 撤回 Plan B (Chrome 9226 违反红线，删 SellerSprite)
"""
import sys, os, json, re, time
sys.stdout.reconfigure(encoding="utf-8")

SEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MON_BACKEND = os.path.normpath(os.path.join(SEL_ROOT, "..", "crossmart-monitor", "backend"))
if MON_BACKEND not in sys.path:
    sys.path.insert(0, MON_BACKEND)

from browser.cdp_bridge import CDPBrowser, ensure_edge_running  # noqa: E402
from browser.amazon_browser import AmazonBrowser  # noqa: E402
from browser.asin_monitor import extract_asin_data, extract_sprite_plugin_data  # noqa: E402

FRONTEND_DATA = os.path.join(SEL_ROOT, "frontend", "data")
STRATEGY_JSON = os.path.join(FRONTEND_DATA, "strategy.json")
OUT_JSON = os.path.join(FRONTEND_DATA, "keyword_asins.json")

DOMAIN_MAP = {
    "UK": "amazon.co.uk",
    "DE": "amazon.de",
    "CA": "amazon.ca",
    "US": "amazon.com",
}

PAGE_PAUSE = 4
SEARCH_PAUSE = 3


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_strategy_keywords():
    """read strategy.json, reverse-parse (country, keyword, bucket) list"""
    if not os.path.exists(STRATEGY_JSON):
        raise FileNotFoundError(f"{STRATEGY_JSON} missing, run strategy_router.py first")
    with open(STRATEGY_JSON, "r", encoding="utf-8") as f:
        s = json.load(f)

    pairs = []
    bucket_name_map = {
        "品牌创新": "Brand Innovation",
        "newrelease": "New Release",
        "模仿跟风": "Follow Crowd",
        "老款延伸": "Legacy Extension",
    }
    for backend_key, b in (s.get("buckets") or {}).items():
        for it in (b.get("items") or []):
            country = it.get("country")
            keyword = it.get("keyword")
            if country and keyword:
                pairs.append((country, keyword, bucket_name_map.get(backend_key, backend_key)))
    return pairs, s.get("generated_at", "")


def parse_search_page_full(browser, max_results=48):
    """Amazon srp: extract all [data-asin] (TOP 48)"""
    js = r"""
    (() => {
        var out = [];
        var seen = new Set();
        var cards = document.querySelectorAll("[data-asin]:not([data-asin='']):not([data-asin-template])");
        cards.forEach((el, i) => {
            var asin = el.getAttribute('data-asin') || '';
            if (!asin || !asin.startsWith('B0') || asin.length !== 10 || seen.has(asin)) return;
            seen.add(asin);
            var titleEl = el.querySelector('h2 a span, h2 span, .a-link-normal .a-text-normal');
            var title = (titleEl && titleEl.textContent || '').replace(/\s+/g, ' ').trim();
            var priceEl = el.querySelector('.a-price .a-offscreen');
            var price = priceEl ? priceEl.textContent.trim() : '';
            var ratingEl = el.querySelector('[aria-label*="out of 5 stars"], i.a-icon-star-medium span.a-icon-alt');
            var rating = ratingEl ? (ratingEl.getAttribute('aria-label') || ratingEl.textContent || '').trim() : '';
            var reviewsEl = el.querySelector('[aria-label*="ratings"], a.a-link-normal[href*="#customerReviews"]');
            var reviews = reviewsEl ? (reviewsEl.getAttribute('aria-label') || reviewsEl.textContent || '').trim() : '';
            var sponsored = !!(
                el.querySelector('.s-sponsored-info') ||
                el.querySelector('[class*=sponsored]') ||
                el.closest('[class*=sponsored]')
            );
            out.push({
                asin: asin,
                rank: i + 1,
                title: title.slice(0, 200),
                price: price,
                rating: rating,
                reviews: reviews,
                sponsored: sponsored
            });
        });
        return JSON.stringify(out);
    })()
    """
    try:
        raw = browser.eval(js)
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return data[:max_results]
    except Exception as e:
        log(f"   [JS err] {e}")
    return []


def extract_seller_sprite_panel(browser):
    """SellerSprite ext: srp usually has no panel (on-click + detail-page), fallback to LQS+变体 div"""
    js = r"""
    (() => {
        var out = {};
        var panel = document.querySelector('.seller-sprite-panel, [class*=seller-sprite-popup], [id*=seller-sprite]');
        if (!panel) {
            var all = document.querySelectorAll('div, section');
            for (var i = 0; i < all.length; i++) {
                var t = (all[i].innerText || '').slice(0, 500);
                if (t.indexOf('LQS') >= 0 && t.indexOf('变体') >= 0) {
                    panel = all[i];
                    break;
                }
            }
        }
        if (panel) {
            out.panel_text = (panel.innerText || '').slice(0, 3000);
            out.has_panel = true;
        } else {
            out.has_panel = false;
        }
        return JSON.stringify(out);
    })()
    """
    try:
        raw = browser.eval(js)
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        log(f"   [sprite JS err] {e}")
    return {"has_panel": False}


def search_one(browser, country, keyword, max_results=48):
    """open Amazon srp -> scrape full-page ASINs + SellerSprite panel"""
    domain = DOMAIN_MAP.get(country, "amazon.com")
    url = f"https://{domain}/s?k=" + re.sub(r"\s+", "+", keyword.strip())
    log(f"  -> {country} : {keyword!r}  (open {domain})")
    browser.navigate(url)
    time.sleep(SEARCH_PAUSE)

    for attempt in range(10):
        asins = parse_search_page_full(browser, max_results)
        if len(asins) >= 10:
            break
        time.sleep(1)

    sprite = extract_seller_sprite_panel(browser)
    if sprite.get("has_panel"):
        snippet = (sprite.get("panel_text") or "")[:80]
        log(f"     sprite panel: ok ({snippet!r})")
    else:
        log("     sprite panel: no (srp usually empty, need detail page)")

    return {
        "country": country,
        "keyword": keyword,
        "asin_count": len(asins),
        "asin_list": [a["asin"] for a in asins],
        "detail": asins,
        "seller_sprite": sprite,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run(start_with_one=None):
    """main loop - Edge 9225 only"""
    pairs, strategy_at = load_strategy_keywords()
    log(f"共 {len(pairs)} (country, keyword) pairs to fetch")
    for c, kw, bucket in pairs[:5]:
        log(f"   - [{c}] {kw}  -> {bucket}")

    if start_with_one:
        idx = 0
        for i, (c, kw, _) in enumerate(pairs):
            if c == start_with_one[0] and kw == start_with_one[1]:
                idx = i
                break
        pairs = pairs[idx:idx+1]
        log(f"TEST MODE: only ({start_with_one})")

    log("=" * 60)
    log("Step 2: Edge browser fetch ASIN")
    log("=" * 60)

    log("Plan A: Edge 默认 profile + 9225")
    if not ensure_edge_running(port=9225):
        log("FAIL Edge 9225 start - this is the known env bug (TOOLS.md 灾难教训 2026-07-25)")
        log("Fallback: 请 闫旭 手动 Edge 带 flag 启动 (一次性)")
        log("  1. kill 所有 msedge.exe")
        log("  2. msedge --remote-debugging-port=9225 --remote-allow-origins=* --new-window about:blank")
        log("  3. 等 Edge 窗口稳定 + curl 127.0.0.1:9225/json/version 返回 Browser 字段")
        return None

    time.sleep(2)

    browser = CDPBrowser()
    # FIX 2026-07-25: connect_tab signature is (idx=0), not tab_url_filter
    browser.connect_tab(0)
    if not browser.tab:
        browser.cmd("Target.createTarget", {"url": "about:blank"})
        time.sleep(0.5)
        browser.connect_tab(0)
    tab_url = (browser.tab.get("url", "") if browser.tab else "")[:60]
    log(f"ok CDP connected, tab={tab_url}")

    results = {}
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        for i, (country, keyword, bucket) in enumerate(pairs, 1):
            log(f"[{i}/{len(pairs)}]")
            try:
                rec = search_one(browser, country, keyword, max_results=48)
                rec["bucket"] = bucket
                key = f"{country}::{keyword}"
                results[key] = rec
            except Exception as e:
                log(f"   FAIL {country} {keyword}: {e}")
                results[f"{country}::{keyword}"] = {"error": str(e)}
            if i < len(pairs):
                time.sleep(PAGE_PAUSE)
            if i % 5 == 0 or i == len(pairs):
                _save_partial(results, started_at, strategy_at, finished=(i == len(pairs)))
    finally:
        try:
            browser.close()
        except Exception:
            pass
    return results


def _save_partial(results, started_at, strategy_at, finished=False):
    """periodic / final save: whole-page overwrite keyword_asins.json"""
    os.makedirs(FRONTEND_DATA, exist_ok=True)
    payload = {
        "meta": {
            "started_at": started_at,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S") if finished else None,
            "strategy_generated_at": strategy_at,
            "total_keywords": len(results),
            "complete": finished,
        },
        "records": results,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"   SAVED {OUT_JSON}  ({len(results)} records, finished={finished})")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--test", nargs=2, metavar=("COUNTRY", "KW"))
    args = p.parse_args()
    run(start_with_one=tuple(args.test) if args.test else None)
