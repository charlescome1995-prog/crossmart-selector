#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector - keyword -> Amazon srp full-page ASIN scraper via Edge CDP

Input  : crossmart-selector/frontend/data/strategy.json (Part B, 4 buckets)
Output : crossmart-selector/frontend/data/keyword_asins.json

Architecture (2026-07-25):
  - Use TEMP Edge profile (not user's polluted profile) + --load-extension=SellerSprite
  - Connect to ws://127.0.0.1:9225 via Python websocket-client
  - Page.navigate to Amazon srp
  - Runtime.evaluate JS to extract ASINs + Amazon native fields + SellerSprite injection presence
  - Note: LQS / 月销量 / 变体 are detail-page fields, NOT on srp. srp only injects clickable icons.

Depends:
  - crossmart-monitor/backend/browser/{cdp_bridge,...}.py (legacy compat only)
  - Edge 150 with --remote-debugging-port=9225 (TOOLS.md red line: Edge only)
  - websocket-client (pip install websocket-client)
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

DOMAIN_MAP = {
    "UK": "amazon.co.uk",
    "DE": "amazon.de",
    "CA": "amazon.ca",
    "US": "amazon.com",
}

PAGE_PAUSE = 4
SEARCH_PAUSE = 3

# Edge 9225 - 用 temp profile + --load-extension=SellerSprite
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PROFILE_REAL = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
SELLERSPRITE_EXT = os.path.join(EDGE_PROFILE_REAL, "Default", "Extensions",
                                  "ecanjpklimgeijdcdpdfoooofephbbln", "5.0.4_0")
EDGE_CDP_PORT = 9225
EDGE_TEMP_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Temp\Edge-SS-CDP-9225")


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


def start_edge_cdp(port=EDGE_CDP_PORT, wait_sec=30):
    """
    Start Edge with TEMP profile + --load-extension=SellerSprite + --remote-debugging-port.
    This is the WORKING posture as of 2026-07-25 (user's profile is polluted; temp profile works).
    Returns True if CDP port is listening.
    """
    # Kill all Edge first
    subprocess.run("taskkill /F /IM msedge.exe", shell=True, capture_output=True)
    time.sleep(3)
    os.makedirs(EDGE_TEMP_PROFILE, exist_ok=True)
    if not os.path.exists(SELLERSPRITE_EXT):
        log(f"FAIL SellerSprite extension not found at {SELLERSPRITE_EXT}")
        return False
    args = [
        EDGE_EXE,
        f"--user-data-dir={EDGE_TEMP_PROFILE}",
        f"--load-extension={SELLERSPRITE_EXT}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window", "about:blank",
    ]
    subprocess.Popen(args)
    # Poll for CDP
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3)
            data = json.loads(req.read())
            if data.get("Browser"):
                log(f"ok Edge CDP ready (Browser={data.get('Browser')}, port={port})")
                return True
        except Exception:
            pass
        time.sleep(1)
    log(f"FAIL Edge CDP timeout (port={port})")
    return False


def get_tabs(port=EDGE_CDP_PORT):
    """Return list of page-type tabs (skip iframes/service workers)."""
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
        tabs = json.loads(req.read())
        return [t for t in tabs if t.get("type") == "page"]
    except Exception as e:
        log(f"get_tabs err: {e}")
        return []


def fetch_srp_via_cdp(country, keyword, port=EDGE_CDP_PORT, timeout=30):
    """
    Connect to Edge CDP, navigate to Amazon srp, extract ASINs + Amazon native fields.
    Returns dict {asin_count, asin_list, detail, seller_sprite}.
    """
    import websocket
    tabs = get_tabs(port)
    if not tabs:
        log(f"  no Edge tabs available")
        return None
    # Use the first page-type tab
    target_tab = tabs[0]
    tab_id = target_tab["id"]
    ws_url = target_tab["webSocketDebuggerUrl"]
    log(f"  using tab {tab_id[:8]}... ({target_tab.get('title','')[:40]})")
    ws = websocket.create_connection(ws_url, timeout=timeout)

    mid = [0]
    def cmd(method, params=None, t=20):
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
    log(f"  waiting {SEARCH_PAUSE+10}s for page + SellerSprite injection...")
    time.sleep(SEARCH_PAUSE + 10)

    # Extraction JS
    js = r"""
    new Promise(resolve => {
      const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
      const out = [];
      const seen = new Set();
      cards.forEach((el) => {
        const asin = el.getAttribute('data-asin') || '';
        if (!asin || !asin.startsWith('B0') || asin.length !== 10 || seen.has(asin)) return;
        seen.add(asin);
        const titleEl = el.querySelector('h2 span');
        const title = titleEl ? titleEl.textContent.trim() : '';
        const priceEl = el.querySelector('.a-price .a-offscreen');
        const price = priceEl ? priceEl.textContent.trim() : '';
        const ratingEl = el.querySelector('i.a-icon-star-medium span.a-icon-alt, [aria-label*="out of 5 stars"]');
        const rating = ratingEl ? (ratingEl.getAttribute('aria-label') || ratingEl.textContent || '').trim() : '';
        const reviewsEl = el.querySelector('a.a-link-normal[href*="#customerReviews"] span, [aria-label*="ratings"]');
        const reviews = reviewsEl ? (reviewsEl.getAttribute('aria-label') || reviewsEl.textContent || '').trim() : '';
        const sponsored = !!(el.querySelector('.s-sponsored-info, [class*=sponsored]'));
        const ssIcon = el.outerHTML.includes('seller-sprite') || el.outerHTML.includes('sellerSprite');
        out.push({asin, rank: out.length + 1, title: title.slice(0,200), price, rating, reviews, sponsored, seller_sprite_icon: ssIcon});
      });
      const overallSs = document.querySelectorAll('[class*="seller-sprite"], [class*="sellerSprite"]').length;
      resolve({
        url: location.href,
        title: document.title,
        total_cards: cards.length,
        asins: out,
        seller_sprite: {
          total_in_page: overallSs,
          asins_with_icon: out.filter(a => a.seller_sprite_icon).length,
          note: 'srp page: SellerSprite injects click-to-expand icons only. LQS/月销量/变体 require per-card click or detail-page visit.'
        }
      });
    });
    """

    result = cmd("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
    val = result.get("result", {}).get("value")
    ws.close()
    if not val:
        log(f"  extraction failed: {result}")
        return None

    return {
        "country": country,
        "keyword": keyword,
        "asin_count": len(val.get("asins", [])),
        "asin_list": [a["asin"] for a in val.get("asins", [])],
        "detail": val.get("asins", []),
        "seller_sprite": val.get("seller_sprite", {}),
        "page_url": val.get("url", ""),
        "page_title": val.get("title", ""),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run(mode="chrome", start_with_one=None):
    """
    Main loop.
    - mode=chrome: use NEW temp-profile + --load-extension approach (working 2026-07-25)
    - mode=edge: use legacy ensure_edge_running (broken in this env, kept for future)
    """
    pairs, strategy_at = load_strategy_keywords()
    log(f"共 {len(pairs)} (country, keyword) pairs")
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
    log("Step 2: Edge CDP fetch ASIN")
    log("=" * 60)

    if mode == "chrome":  # temp profile + load-extension (working)
        if not start_edge_cdp(port=EDGE_CDP_PORT):
            log("FAIL Edge CDP not ready")
            return None
    else:  # legacy - kept but probably broken in this env
        from browser.cdp_bridge import ensure_edge_running
        if not ensure_edge_running(port=9225):
            log("FAIL Edge 9225 not ready")
            return None
        os.environ["CDP_PORT"] = "9225"

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
                log(f"   ok {rec['asin_count']} ASINs, {rec['seller_sprite'].get('asins_with_icon',0)} with SS icon")
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
            "source": "Edge CDP via temp profile + --load-extension=SellerSprite (2026-07-25)",
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
    p.add_argument("--mode", choices=["chrome", "edge"], default="chrome")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()
    if args.list:
        pairs, _ = load_strategy_keywords()
        for c, kw, b in pairs:
            print(f"  [{b}] {c} | {kw}")
        sys.exit(0)
    run(mode=args.mode, start_with_one=tuple(args.test) if args.test else None)
