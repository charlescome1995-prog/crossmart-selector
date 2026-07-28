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
EDGE_TEMP_PROFILE = r"C:\Users\OPENPC\AppData\Local\Microsoft\Edge\User Data-CDP-9225"


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


EXTRACT_JS = r"""(() => async function() {
  const timeout = setTimeout(() => { extractData(); }, 60000);
  function extractData() {
    clearTimeout(timeout);
    const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
    const results = [];
    for (const card of cards) {
      const asin = card.getAttribute('data-asin') || '';
      if (!asin || !asin.startsWith('B0') || asin.length !== 10) continue;
      const titleEl = card.querySelector('h2 span');
      const title = titleEl ? titleEl.textContent.trim() : '';
      const priceEl = card.querySelector('.a-price .a-offscreen');
      const price = priceEl ? priceEl.textContent.trim() : '';
      const ratingEl = card.querySelector('i.a-icon-star-medium span.a-icon-alt, [aria-label*="out of 5 stars"]');
      const rating = ratingEl ? (ratingEl.getAttribute('aria-label') || ratingEl.textContent || '').trim() : '';
      const reviewsEl = card.querySelector('a.a-link-normal[href*="#customerReviews"] span, [aria-label*="ratings"]');
      const reviews = reviewsEl ? (reviewsEl.getAttribute('aria-label') || reviewsEl.textContent || '').trim() : '';
      // Sponsored 检测：Amazon 2026 主要靠祖先节点标识（不只是子 badge）
      let sponsored = false;
      let _p = card.parentElement;
      while (_p && _p !== document.body) {
        if (_p.matches && _p.matches('[data-component-type="s-search-result-ads"], [data-ad-type], .AdHolder, [data-test-component="SearchAdSlot"]')) {
          sponsored = true; break;
        }
        _p = _p.parentElement;
      }
      if (!sponsored && card.querySelector('.s-sponsored-info, [class*="SponsoredBadge"], .puis-sponsored-label')) sponsored = true;
      if (!sponsored && /\bSponsored\b/i.test((card.innerText || '').slice(0, 120))) sponsored = true;
      const ssContainer = card.querySelector('[name^="seller-sprite-extension-quick-view-"]');
      const ss_text = ssContainer ? ssContainer.innerText : '';
      results.push({asin, title: title.slice(0,200), price, rating, reviews, sponsored, ss_text: ss_text.slice(0, 5000)});
    }
    return results;
  }
  const initial = document.querySelectorAll('[name^="seller-sprite-extension-quick-view-"]').length;
  if (initial >= 20) return extractData();
  return new Promise((resolve) => {
    function checkReady() {
      const ssEls = document.querySelectorAll('[name^="seller-sprite-extension-quick-view-"]');
      if (ssEls.length < 20) return false;
      let maxLen = 0;
      for (const e of ssEls) if (e.innerText.length > maxLen) maxLen = e.innerText.length;
      return maxLen > 200;
    }
    if (checkReady()) { resolve(extractData()); return; }
    const obs = new MutationObserver(() => {
      if (checkReady()) { obs.disconnect(); resolve(extractData()); }
    });
    obs.observe(document.body, {childList: true, subtree: true, characterData: true});
  });
}
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
    def cmd(method, params=None, t=100):
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
    cmd("Page.enable", t=5)
    cmd("Page.navigate", {"url": url})
    # Poll until location.href matches target AND cards exist
    waited = 0
    domain = DOMAIN_MAP.get(country, "amazon.com")
    # Phase 1: wait for navigation + cards (up to 45s)
    waited = 0
    while waited < 10000:
        ev = cmd("Runtime.evaluate", {"expression": "(() => ({url: location.href, rs: document.readyState, cards: document.querySelectorAll(\"div[data-component-type=s-search-result]\").length}))()"}, t=5)
        v = ev.get("result", {}).get("value", {})
        if v.get("url", "").find(domain) >= 0 and v.get("rs") == "complete" and v.get("cards", 0) >= 10:
            break
        time.sleep(1)
        waited += 1000
    # Phase 2: scroll to trigger lazy-load
    for y in range(0, 5500, 300):
        cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, " + str(y) + ")"}, t=3)
        time.sleep(0.3)
    cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"}, t=3)
    # Phase 3: wait for SellerSprite injection (up to 30s)
    waited = 0
    while waited < 15000:
        ev = cmd("Runtime.evaluate", {"expression": "(() => document.querySelectorAll(String.fromCharCode(91,93)).length)"}, t=5)
        n = ev.get("result", {}).get("value", 0)
        if isinstance(n, int) and n >= 20:
            break
        time.sleep(1)
        waited += 1000
    # Phase 4: extra wait for SS to fully inject data into containers (up to 20s)
    waited = 0
    while waited < 10000:
        ev = cmd("Runtime.evaluate", {"expression": "(() => { const els = document.querySelectorAll(chr(34) + chr(34) + chr(34) + chr(34) + chr(34) + chr(34) + chr(34) + chr(34)).length}"}, t=5)

        v = ev.get("result", {}).get("value", {})
        if v.get("maxLen", 0) >= 300:
            break
        time.sleep(1)
        waited += 1000
    # scroll to trigger lazy-load SS
    for y in range(0, 5500, 300):
        cmd("Runtime.evaluate", {"expression": f"window.scrollTo(0, {y})"}, t=3)
        time.sleep(0.3)
    cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"}, t=3)
    time.sleep(8)  # wait for SS to fully inject on visible cards

    result = cmd("Runtime.evaluate", {"expression": EXTRACT_JS, "returnByValue": True, "awaitPromise": True})
    val = result.get("result", {}).get("value")
    ws.close()
    if not val:
        return None
    detail = []
    for a in val:
        ss_text = a.get("ss_text", "")
        ss = parse_ss_text(ss_text)
        ss["ss_has_ss"] = bool(ss_text)
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
            "ss_revenue": ss.get("revenue", ""),
            "ss_fba_fee": ss.get("fba_fee", ""),
            "ss_margin": ss.get("margin", ""),
            "ss_variants": ss.get("variants", ""),
            "ss_price": ss.get("ss_price", ""),
            "ss_rating": ss.get("ss_rating", ""),
            "ss_review_count": ss.get("ss_review_count", ""),
            "ss_delivery_days": ss.get("delivery_days", ""),
            "ss_prime_days": ss.get("prime_days", ""),
            "ss_launch_date": ss.get("launch_date", ""),
            "ss_days_listed": ss.get("days_listed", ""),
            "ss_all_traffic_words": ss.get("all_traffic_words", ""),
            "ss_organic_keywords": ss.get("organic_keywords", ""),
            "ss_ad_keywords": ss.get("ad_keywords", ""),
            "ss_suggest_keywords": ss.get("suggest_keywords", ""),
            "ss_has_ss": ss.get("has_ss", False),
        }
        detail.append(flat)
    return {
        "country": country, "keyword": keyword, "asin_count": len(detail),
        "asin_list": [a["asin"] for a in detail], "detail": detail,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# Parser: extract all 24 SS fields from raw ss_text (Chinese regex via \u escapes)
SS_REGEX = [
    ("ss_brand", re.compile("\u54c1\u724c:\s*([^\n]+)")),
    ("ss_seller", re.compile("\u5356\u5bb6:([^\n]+)")),
    ("ss_fulfillment", re.compile("\u914d\u9001:\s*([^\n]+)")),
    ("ss_seller_count", re.compile("\u5356\u5bb6\u6570:\s*(\d+)")),
    ("ss_natural_position", re.compile("\u81ea\u7136\u4f4d[:\uff1a]\s*([^\n]+)")),
    ("ss_monthly_sales_parent", re.compile("\u8fd1\s*30\s*\u5929\u9500\u91cf\(\u7236\u4f53\):\s*([^*\n]+)")),
    ("ss_monthly_sales_child", re.compile("\u8fd1\s*30\s*\u5929\u9500\u91cf\(\u5b50\u4f53\):\s*([^*\n]+)")),
    ("ss_revenue", re.compile("\u9500\u552e\u989d:\s*([^\n]+)")),
    ("ss_fba_fee", re.compile("FBA\u8d39\u7528:\s*([^\n]+)")),
    ("ss_margin", re.compile("\u6bdb\u5229\u7387:\s*([^\n]+)")),
    ("ss_variants", re.compile("\u53d8\u4f53\u6570:\s*(\d+)")),
    ("ss_price", re.compile("\u4ef7\u683c:\s*\$?\s*([\d.,]+)")),
    ("ss_delivery_days", re.compile("\u914d\u9001\u65f6\u957f:\s*(\d+\s*\u5929)")),
    ("ss_prime_days", re.compile("Prime\u914d\u9001\u65f6\u957f:\s*(\d+\s*\u5929)")),
    ("ss_launch_date", re.compile("\u4e0a\u67b6\u65f6\u95f4[\s::\uff1a]+(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})")),
    ("ss_days_listed", re.compile("\u4e0a\u67b6\u65f6\u95f4[\s::\uff1a]+\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s*[\(\uff08]?([\d,]+)\s*\u5929[\)\uff09]?")),
    ("ss_all_traffic_words", re.compile("\u5168\u90e8\u6d41\u91cf\u8bcd:\s*(\d+)")),
    ("ss_organic_keywords", re.compile("\u81ea\u7136\u641c\u7d22\u8bcd:\s*(\d+)")),
    ("ss_ad_keywords", re.compile("\u5e7f\u544a\u6d41\u91cf\u8bcd:\s*(\d+)")),
    ("ss_suggest_keywords", re.compile("\u641c\u7d22\u63a8\u8350\u8bcd:\s*(\d+)")),
]


def parse_ss_text(ss_text):
    """Parse SellerSprite raw text into 24 SS fields. Uses regex (raw string list at top of file)."""
    if not ss_text:
        return {}
    out = {}
    for key, rx in SS_REGEX:
        m = rx.search(ss_text)
        if m:
            v = m.group(1).strip()
            # Clean up
            if key == "ss_price" and not v.startswith("$"):
                v = "$" + v
            if key == "ss_days_listed":
                v = v.replace(",", "")  # "3,868" -> "3868"
            out[key] = v
    # BSR main / sub (could be 1 or 2)
    bsr_matches = re.findall(r"#([\d,]+)\s+in\s+([^\n]+)", ss_text)
    if len(bsr_matches) > 0:
        out["ss_bsr_main"] = bsr_matches[0][0] + " in " + bsr_matches[0][1]
    if len(bsr_matches) > 1:
        out["ss_bsr_sub"] = bsr_matches[1][0] + " in " + bsr_matches[1][1]
    # Rating: 4.2(1,007) or 4.2 out of 5 stars
    m = re.search(r"\u8bc4\u5206\(([^\n]+)\)", ss_text)
    if m:
        inner = m.group(1)
        rm = re.match(r"([\d.]+)\(([\d,]+)\)", inner)
        if rm:
            out["ss_rating"] = rm.group(1)
            out["ss_review_count"] = rm.group(2)
        else:
            out["ss_rating"] = inner
    return out


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