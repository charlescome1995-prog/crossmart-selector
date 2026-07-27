#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - keyword -> Amazon srp full-page ASIN scraper via Edge CDP (2026-07-27)
"""
import sys, os, json, re, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

SEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MON_BACKEND = os.path.normpath(os.path.join(SEL_ROOT, "..", "crossmart-monitor", "backend"))
if MON_BACKEND not in sys.path:
    sys.path.insert(0, MON_BACKEND)

FRONTEND_DATA = os.path.join(SEL_ROOT, "frontend", "data")
STRATEGY_JSON = os.path.join(FRONTEND_DATA, "strategy.json")
OUT_JSON = os.path.join(FRONTEND_DATA, "keyword_asins.json")

DOMAIN_MAP = {"UK": "amazon.co.uk", "DE": "amazon.de", "CA": "amazon.ca", "US": "amazon.com"}
PAGE_PAUSE = 4
SEARCH_PAUSE = 3

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PROFILE_REAL = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
SELLERSPRITE_EXT = os.path.join(EDGE_PROFILE_REAL, "Default", "Extensions",
                                  "ecanjpklimgeijdcdpdfoooofephbbln", "5.0.4_0")
EDGE_CDP_PORT = 9225
EDGE_TEMP_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Temp\Edge-CDP-9225")


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_strategy_keywords():
    if not os.path.exists(STRATEGY_JSON):
        raise FileNotFoundError(f"{STRATEGY_JSON} missing")
    with open(STRATEGY_JSON, "r", encoding="utf-8") as f:
        s = json.load(f)
    pairs = []
    bucket_name_map = {
        "\u54c1\u724c\u521b\u65b0": "Brand Innovation",
        "newrelease": "New Release",
        "\u6a21\u4eff\u8ddf\u98ce": "Follow Crowd",
        "\u8001\u6b3e\u5ef6\u4f38": "Legacy Extension",
    }
    for backend_key, b in (s.get("buckets") or {}).items():
        for it in (b.get("items") or []):
            country = it.get("country")
            keyword = it.get("keyword")
            if country and keyword:
                pairs.append((country, keyword, bucket_name_map.get(backend_key, backend_key)))
    return pairs, s.get("generated_at", "")


def start_edge_cdp(port=EDGE_CDP_PORT, wait_sec=30):
    subprocess.run("taskkill /F /IM msedge.exe", shell=True, capture_output=True)
    time.sleep(3)
    os.makedirs(EDGE_TEMP_PROFILE, exist_ok=True)
    if not os.path.exists(SELLERSPRITE_EXT):
        log(f"FAIL SellerSprite ext not found at {SELLERSPRITE_EXT}")
        return False
    args = [EDGE_EXE, f"--user-data-dir={EDGE_TEMP_PROFILE}", f"--load-extension={SELLERSPRITE_EXT}",
            f"--remote-debugging-port={port}", "--remote-allow-origins=*", "--no-first-run",
            "--no-default-browser-check", "--new-window", "about:blank"]
    subprocess.Popen(args)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3)
            data = json.loads(req.read())
            if data.get("Browser"):
                log(f"ok Edge CDP ready ({data.get('Browser')}, port={port})")
                return True
        except Exception:
            pass
        time.sleep(1)
    log(f"FAIL Edge CDP timeout (port={port})")
    return False


def get_tabs(port=EDGE_CDP_PORT):
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
        tabs = json.loads(req.read())
        return [t for t in tabs if t.get("type") == "page"]
    except Exception as e:
        log(f"get_tabs err: {e}")
        return []


EXTRACT_JS = r"""
(() => {
  const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
  const results = [];
  const seen = new Set();
  for (const card of cards) {
    const asin = card.getAttribute('data-asin') || '';
    if (!asin || !asin.startsWith('B0') || asin.length !== 10 || seen.has(asin)) continue;
    seen.add(asin);
    const titleEl = card.querySelector('h2 span');
    const title = titleEl ? titleEl.textContent.trim() : '';
    const priceEl = card.querySelector('.a-price .a-offscreen');
    const price = priceEl ? priceEl.textContent.trim() : '';
    const ratingEl = card.querySelector('i.a-icon-star-medium span.a-icon-alt, [aria-label*="out of 5 stars"]');
    const rating = ratingEl ? (ratingEl.getAttribute('aria-label') || ratingEl.textContent || '').trim() : '';
    const reviewsEl = card.querySelector('a.a-link-normal[href*="#customerReviews"] span, [aria-label*="ratings"]');
    const reviews = reviewsEl ? (reviewsEl.getAttribute('aria-label') || reviewsEl.textContent || '').trim() : '';
    const sponsored = !!(card.querySelector('.s-sponsored-info, [class*=sponsored]'));
    const ssContainer = card.querySelector('[name^="seller-sprite-extension-quick-view-"]');
    const ss = {has_ss: !!ssContainer, raw_text: '', brand: '', seller: '', fulfillment: '', seller_count: '', natural_position: '', bsr_main: '', bsr_sub: '', monthly_sales_parent: '', monthly_sales_child: '', variants: '', ss_rating: ''};
    if (ssContainer) {
      const fullText = ssContainer.innerText || '';
      ss.raw_text = fullText.slice(0, 2000);
      const mBrand = fullText.match(/\u54c1\u724c:\s*([^\n]+)/);
      if (mBrand) ss.brand = mBrand[1].trim();
      const mSeller = fullText.match(/\u5356\u5bb6:([^\n]+)/);
      if (mSeller) ss.seller = mSeller[1].trim();
      const mFulfillment = fullText.match(/\u914d\u9001:\s*([^\n]+)/);
      if (mFulfillment) ss.fulfillment = mFulfillment[1].trim();
      const mSellerCount = fullText.match(/\u5356\u5bb6\u6570:\s*(\d+)/);
      if (mSellerCount) ss.seller_count = mSellerCount[1];
      const mNatPos = fullText.match(/\u81ea\u7136\u4f4d[:\uff1a]?\s*([^\n]+)/);
      if (mNatPos) ss.natural_position = mNatPos[1].trim();
      const bsrMatches = [...fullText.matchAll(/#([\d,]+)\s+in\s+([^\n]+)/g)];
      if (bsrMatches[0]) ss.bsr_main = bsrMatches[0][1] + ' in ' + bsrMatches[0][2];
      if (bsrMatches[1]) ss.bsr_sub = bsrMatches[1][1] + ' in ' + bsrMatches[1][2];
      const mParentSales = fullText.match(/\u8fd1\s*30\s*\u5929\u9500\u91cf\(\u7236\u4f53\):\s*([^*\n]+)/);
      if (mParentSales) ss.monthly_sales_parent = mParentSales[1].trim();
      const mChildSales = fullText.match(/\u8fd1\s*30\s*\u5929\u9500\u91cf\(\u5b50\u4f53\):\s*([^*\n]+)/);
      if (mChildSales) ss.monthly_sales_child = mChildSales[1].trim();
      const mVariants = fullText.match(/\u53d8\u4f53\u6570:\s*(\d+)/);
      if (mVariants) ss.variants = mVariants[1];
      const mRating = fullText.match(/\u8bc4\u5206\((.*?)\)/);
      if (mRating) ss.ss_rating = mRating[1];
    }
    results.push({asin, title: title.slice(0,200), price, rating, reviews, sponsored, seller_sprite: ss});
  }
  return results;
})()
"""


def fetch_srp_via_cdp(country, keyword, port=EDGE_CDP_PORT, timeout=60):
    import websocket
    tabs = get_tabs(port)
    if not tabs:
        log(f"  no Edge tabs available")
        return None
    target_tab = tabs[0]
    ws = websocket.create_connection(target_tab["webSocketDebuggerUrl"], timeout=timeout)
    log(f"  tab {target_tab['id'][:8]}... ({target_tab.get('title','')[:40]})")

    mid = [0]
    def cmd(method, params=None, t=30):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        ws.settimeout(t)
        deadline = time.time() + t
        while time.time() < deadline:
            try:
                raw = ws.recv()
                d = json.loads(raw)
                if d.get("id") == mid[0]:
                    return d.get("result", {})
            except Exception:
                pass
        return {}

    cmd("Page.enable", t=5)
    cmd("Runtime.enable", t=5)

    domain = DOMAIN_MAP.get(country, "amazon.com")
    url = f"https://{domain}/s?k=" + re.sub(r"\s+", "+", keyword.strip())
    log(f"  navigate {url}")
    cmd("Page.navigate", {"url": url})
    time.sleep(SEARCH_PAUSE + 5)

    for y in range(0, 5500, 300):
        cmd("Runtime.evaluate", {"expression": f"window.scrollTo(0, {y})"})
        time.sleep(0.4)
    cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"})
    time.sleep(5)

    result = cmd("Runtime.evaluate", {"expression": EXTRACT_JS, "returnByValue": True})
    val = result.get("result", {}).get("value")
    ws.close()
    if not val:
        return None
    detail = []
    for a in val:
        ss = a.get("seller_sprite", {})
        flat = {
            "asin": a.get("asin"),
            "title": a.get("title"),
            "price": a.get("price"),
            "rating": a.get("rating"),
            "reviews": a.get("reviews"),
            "sponsored": a.get("sponsored"),
            "ss_brand": ss.get("brand", ""),
            "ss_seller": ss.get("seller", ""),
            "ss_fulfillment": ss.get("fulfillment", ""),
            "ss_seller_count": ss.get("seller_count", ""),
            "ss_natural_position": ss.get("natural_position", ""),
            "ss_bsr_main": ss.get("bsr_main", ""),
            "ss_bsr_sub": ss.get("bsr_sub", ""),
            "ss_monthly_sales_parent": ss.get("monthly_sales_parent", ""),
            "ss_monthly_sales_child": ss.get("monthly_sales_child", ""),
            "ss_variants": ss.get("variants", ""),
            "ss_rating": ss.get("ss_rating", ""),
            "ss_has_ss": ss.get("has_ss", False),
        }
        detail.append(flat)
    return {
        "country": country, "keyword": keyword, "asin_count": len(detail),
        "asin_list": [a["asin"] for a in detail], "detail": detail,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run(start_with_one=None):
    pairs, strategy_at = load_strategy_keywords()
    log(f"Total {len(pairs)} (country, keyword) pairs")
    if start_with_one:
        idx = 0
        for i, (c, kw, _) in enumerate(pairs):
            if c == start_with_one[0] and kw == start_with_one[1]:
                idx = i
                break
        pairs = pairs[idx:idx+1]
        log(f"TEST MODE: only ({start_with_one})")

    if not start_edge_cdp(port=EDGE_CDP_PORT):
        log("FAIL Edge CDP not ready")
        return None

    results = {}
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    for i, (country, keyword, bucket) in enumerate(pairs, 1):
        log(f"[{i}/{len(pairs)}] {country} | {keyword}")
        try:
            rec = fetch_srp_via_cdp(country, keyword)
            if rec:
                rec["bucket"] = bucket
                key = f"{country}::{keyword}"
                results[key] = rec
                log(f"   ok {rec['asin_count']} ASINs")
            else:
                results[f"{country}::{keyword}"] = {"error": "extraction failed"}
        except Exception as e:
            log(f"   FAIL {country} {keyword}: {e}")
            results[f"{country}::{keyword}"] = {"error": str(e)}
        if i < len(pairs):
            time.sleep(PAGE_PAUSE)
        if i % 5 == 0 or i == len(pairs):
            _save_partial(results, started_at, strategy_at, finished=(i == len(pairs)))
    return results


def _save_partial(results, started_at, strategy_at, finished=False):
    os.makedirs(FRONTEND_DATA, exist_ok=True)
    payload = {
        "meta": {
            "started_at": started_at,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S") if finished else None,
            "strategy_generated_at": strategy_at,
            "total_keywords": len(results),
            "complete": finished,
            "source": "Edge 150.0.4078.99 CDP via temp profile + --load-extension=SellerSprite (2026-07-27)",
        },
        "records": results,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"   SAVED {OUT_JSON} ({len(results)} records)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--test", nargs=2, metavar=("COUNTRY", "KW"))
    args = p.parse_args()
    run(start_with_one=tuple(args.test) if args.test else None)