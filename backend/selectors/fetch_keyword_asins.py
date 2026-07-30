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

# ── SS 注入等待策略（2026-07-29：从「固定超时后跳过」改为「逐卡等到加载完」）──
# 每张卡都会被反复滚进视口，直到卖家精灵把字段写进 DOM；
# 只有「反复喂满 SS_CARD_NUDGES 次视口仍然空」才判定这个 ASIN 真的没数据。
SS_WAIT_MAX_SEC = int(os.environ.get("SS_WAIT_MAX_SEC", "300"))   # 单次抓取的等待上限（兜底，防死循环）
SS_CARD_NUDGES = int(os.environ.get("SS_CARD_NUDGES", "8"))       # 单卡最多喂几次视口才认定「真没有」
SS_READY_MINLEN = int(os.environ.get("SS_READY_MINLEN", "300"))   # 容器 innerText 长度达标线
SS_MIN_RATIO = float(os.environ.get("SS_MIN_RATIO", "0.9"))       # 覆盖率达标 → 直接通过
SS_ACCEPT_RATIO = float(os.environ.get("SS_ACCEPT_RATIO", "0.5")) # 已收敛（真没数据）时的最低接受覆盖率
SS_NUDGE_BATCH = int(os.environ.get("SS_NUDGE_BATCH", "6"))       # 每轮滚多少张 pending 卡
SS_NUDGE_SLEEP = float(os.environ.get("SS_NUDGE_SLEEP", "1.2"))   # 每张卡停留时长

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


EXTRACT_JS = r"""(() => {
  function extractData() {
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
  // 不等 MutationObserver（它监听不到 innerText）：SS 已经由 _fetch_srp_attempt
  // 的 Phase 3/4 滚动+等待保证了（maxLen>=500）。
  // 直接 extract。
  return extractData();
})()
"""


SS_SELECTOR = '[name^="seller-sprite-extension-quick-view-"]'

# 逐卡体检：每张 search-result 卡的 SS 容器是否已经注入满字段
SS_STATUS_JS = """(() => {
  const MINLEN = %(minlen)d;
  const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
  const ready = [], pending = [];
  for (const c of cards) {
    const asin = c.getAttribute('data-asin') || '';
    if (!asin.startsWith('B0') || asin.length !== 10) continue;
    const box = c.querySelector('%(sel)s');
    const len = box ? (box.innerText || '').length : 0;
    (len >= MINLEN ? ready : pending).push(asin);
  }
  return {total: ready.length + pending.length, ready: ready.length, pending: pending};
})()"""

# 把指定 ASIN 的卡滚到视口正中，逼卖家精灵的 IntersectionObserver 开工
SS_NUDGE_JS = """(() => {
  const c = document.querySelector('div[data-asin="%(asin)s"]');
  if (!c) return false;
  c.scrollIntoView({block: 'center'});
  return true;
})()"""


def _wait_ss_all(cmd, log_prefix="  "):
    """
    等到每一张卡的卖家精灵字段都注入完成，而不是超时就跳过。

    做法：反复把「还空着」的卡滚进视口逼扩展加载；某张卡被喂过
    SS_CARD_NUDGES 次视口仍然空，才认定它真的没有数据（卖家精灵查不到），
    从待办里划掉。全部待办清空 = 收敛。

    Returns: (converged: bool, ready: int, total: int, no_data: list[str])
    """
    status_js = SS_STATUS_JS % {"minlen": SS_READY_MINLEN, "sel": SS_SELECTOR}
    deadline = time.time() + SS_WAIT_MAX_SEC
    nudges = {}          # asin -> 已喂视口次数
    ready = total = 0
    rr = 0               # 轮转起点，保证每张待办卡都轮得到

    def probe():
        ev = cmd("Runtime.evaluate", {"expression": status_js, "returnByValue": True}, t=10)
        v = ev.get("result", {}).get("value")
        return v if isinstance(v, dict) else {}

    while time.time() < deadline:
        st = probe()
        total = st.get("total", 0) or 0
        ready = st.get("ready", 0) or 0
        pending = st.get("pending") or []
        if total == 0:
            time.sleep(1)
            continue
        # 达标条件：一张不剩（不是「够多了就走」）
        if not pending:
            log(f"{log_prefix}✓ SS 全部就位 {ready}/{total} (100%)")
            return True, ready, total, []
        # 还没喂够次数的卡 = 值得继续等
        todo = [a for a in pending if nudges.get(a, 0) < SS_CARD_NUDGES]
        if not todo:
            no_data = list(pending)
            log(f"{log_prefix}✓ SS 收敛 {ready}/{total}；{len(no_data)} 个 ASIN 喂满 "
                f"{SS_CARD_NUDGES} 次仍无数据（判定卖家精灵确实没有）")
            return True, ready, total, no_data
        batch = [todo[(rr + i) % len(todo)] for i in range(min(SS_NUDGE_BATCH, len(todo)))]
        rr += len(batch)
        log(f"{log_prefix}… SS {ready}/{total} 就位，待等 {len(todo)} 张，本轮喂 {len(batch)} 张")
        for asin in batch:
            cmd("Runtime.evaluate", {"expression": SS_NUDGE_JS % {"asin": asin}}, t=5)
            nudges[asin] = nudges.get(asin, 0) + 1
            time.sleep(SS_NUDGE_SLEEP)

    log(f"{log_prefix}⚠ SS 等待触顶 {SS_WAIT_MAX_SEC}s，当前 {ready}/{total}（会触发 retry）")
    return False, ready, total, []


def _ss_ratio(rec):
    """SS 字段覆盖率 = 有品牌/卖家的 ASIN 数 / 总 ASIN 数。"""
    detail = (rec or {}).get("detail") or []
    if not detail:
        return 0.0, 0, 0
    filled = sum(1 for a in detail if a.get("ss_brand") or a.get("ss_seller"))
    return filled / len(detail), filled, len(detail)


def _is_sufficient(rec):
    """
    是否可以收工（不再 retry）。

    两条通过路径：
      1. 覆盖率 ≥ SS_MIN_RATIO（默认 90%）—— 正常情况
      2. 已收敛（每张空卡都被反复喂过视口 SS_CARD_NUDGES 次仍然空 = 卖家精灵真没这条数据）
         且覆盖率 ≥ SS_ACCEPT_RATIO
    """
    if not rec:
        return False
    ratio, filled, total = _ss_ratio(rec)
    if total == 0:
        return False
    if ratio >= SS_MIN_RATIO:
        return True
    return bool(rec.get("ss_converged")) and ratio >= SS_ACCEPT_RATIO


def fetch_srp_via_cdp(country, keyword, port=EDGE_CDP_PORT, timeout=60, max_retries=3):
    """带 retry: 若 SS 注入覆盖率不够且未收敛，重新打开 tab 再抓。"""
    import websocket
    last_rec = None
    best_rec = None
    best_ratio = -1.0
    for attempt in range(1, max_retries + 1):
        log(f"  attempt {attempt}/{max_retries}")
        rec = _fetch_srp_attempt(country, keyword, port, timeout)
        last_rec = rec
        ratio, filled, total = _ss_ratio(rec)
        if ratio > best_ratio:
            best_ratio, best_rec = ratio, rec
        if _is_sufficient(rec):
            log(f"  ✓ attempt {attempt} SS 覆盖 {filled}/{total} ({ratio:.0%})"
                f"{'（已收敛：剩余卡确认无数据）' if ratio < SS_MIN_RATIO else ''}")
            return rec
        log(f"  ⚠ attempt {attempt} SS 覆盖仅 {filled}/{total} ({ratio:.0%})，重试中...")
        if attempt < max_retries:
            time.sleep(3)
    log(f"  ✗ {max_retries} 次尝试后覆盖率仍不足，返回最好一次（{best_ratio:.0%}）")
    return best_rec or last_rec


def _fetch_srp_attempt(country, keyword, port=EDGE_CDP_PORT, timeout=60):
    """单次抓取尝试（原 fetch_srp_via_cdp 主体）。"""
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
    # ── Phase 2: 整页粗滚一遍，先让所有卡片进过一次视口（触发 lazy-load + SS 容器建好）──
    SCROLL_STEP = 250
    SCROLL_SLEEP = 1.0
    for y in range(0, 6000, SCROLL_STEP):
        cmd("Runtime.evaluate", {"expression": f"window.scrollTo(0, {y})"}, t=3)
        time.sleep(SCROLL_SLEEP)
    cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"}, t=3)
    time.sleep(2)

    # ── Phase 3: 逐卡等到加载完（不再固定超时跳过）──
    converged, ss_ready, ss_total, ss_no_data = _wait_ss_all(cmd)

    cmd("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"}, t=3)
    time.sleep(1)

    result = cmd("Runtime.evaluate", {"expression": EXTRACT_JS, "returnByValue": True, "awaitPromise": True})
    val = result.get("result", {}).get("value")
    ws.close()
    if not val:
        return None
    ss_no_data_set = set(ss_no_data or [])
    detail = []
    for a in val:
        ss_text = a.get("ss_text", "")
        ss = parse_ss_text(ss_text)
        # parse_ss_text 返回的 dict key 已经是带 ss_ 前缀的（如 ss_brand, ss_seller），
        # 直接展开 + 标 has_ss
        flat = {
            "asin": a.get("asin"),
            "title": a.get("title"),
            "price": a.get("price"),
            "rating": a.get("rating"),
            "reviews": a.get("reviews"),
            "sponsored": a.get("sponsored"),
            "ss_has_ss": bool(ss_text),
            # 直接合并 parse_ss_text 输出（key 形如 ss_brand / ss_seller）
            **ss,
        }
        # 标注：这个 ASIN 是「等到确认没数据」而不是「等不及跳过」
        if flat["asin"] in ss_no_data_set:
            flat["ss_no_data"] = True
        detail.append(flat)
    return {
        "country": country, "keyword": keyword, "asin_count": len(detail),
        "asin_list": [a["asin"] for a in detail], "detail": detail,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        # SS 等待结果（供 _is_sufficient / 前端诊断用）
        "ss_converged": converged,
        "ss_ready": ss_ready,
        "ss_total": ss_total,
        "ss_no_data_asins": list(ss_no_data),
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


# ══════════════════════════════════════════════════════════════════════════
# 顶层包装：run_selection.py Part A+ 调用入口
# ══════════════════════════════════════════════════════════════════════════
def fetch_keyword_via_cdp(country, keyword, max_asins=20, port=EDGE_CDP_PORT, timeout=60, max_retries=3):
    """
    抓一个关键词的 Amazon SRP（带卖家精灵），返回标准 rec。

    Args:
        country: "US"/"UK"/"DE"/"CA"
        keyword: 关键词原始字符串（含空格）
        max_asins: 截断 detail 到多少条（默认 20；Part A+ 不需要 50 条）
        port: Edge CDP 端口
        timeout/ max_retries: 透传给 fetch_srp_via_cdp

    Returns:
        dict {country, keyword, asin_count, asin_list, detail, fetched_at, ok, error?}
        - ok=True  表示 _is_sufficient() 通过
        - ok=False 表示 SS 不充分但尽力抓了；error 表示完全失败
    """
    try:
        rec = fetch_srp_via_cdp(country, keyword, port=port, timeout=timeout, max_retries=max_retries)
    except Exception as e:
        log(f"  ✗ fetch_srp_via_cdp 异常: {e}")
        return {
            "country": country, "keyword": keyword,
            "asin_count": 0, "asin_list": [], "detail": [],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ok": False, "error": str(e),
        }
    if not rec:
        return {
            "country": country, "keyword": keyword,
            "asin_count": 0, "asin_list": [], "detail": [],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ok": False, "error": "no_rec",
        }
    # 截断到 max_asins
    detail = rec.get("detail") or []
    if len(detail) > max_asins:
        detail = detail[:max_asins]
    return {
        "country": country, "keyword": keyword,
        "asin_count": len(detail),
        "asin_list": [a["asin"] for a in detail],
        "detail": detail,
        "fetched_at": rec.get("fetched_at", time.strftime("%Y-%m-%dT%H:%M:%S")),
        # 截断后重新判定，但要把等待结果一起带上（否则「已收敛」信息丢失）
        "ok": _is_sufficient({
            "detail": detail,
            "ss_converged": rec.get("ss_converged"),
        }),
        "ss_converged": rec.get("ss_converged"),
        "ss_ready": rec.get("ss_ready"),
        "ss_total": rec.get("ss_total"),
        "ss_no_data_asins": rec.get("ss_no_data_asins") or [],
    }


def fetch_keywords_batch(items, max_asins_per_kw=20, keep_browser=False):
    """
    批量抓取：对 items 里每条 (country, keyword) 调 fetch_keyword_via_cdp。

    Args:
        items: [{country, keyword, ...}, ...]  任意带 country/keyword 字段的对象
        max_asins_per_kw: 每关键词最多抓几条 ASIN
        keep_browser: 是否最后保留浏览器（默认 False 关闭）

    Returns:
        [{country, keyword, rec (含 ok/error), tier, rank}, ...]
    """
    log(f"═══ 批量抓取 {len(items)} 条 🟢🟡 ═══")
    if not start_edge_cdp():
        log("Edge CDP 启动失败，整批返回空")
        return [
            {**it, "rec": {"ok": False, "error": "edge_start_failed", "asin_count": 0, "detail": []}}
            for it in items
        ]
    out = []
    for idx, it in enumerate(items, 1):
        country = it["country"]
        keyword = it["keyword"]
        log(f"[{idx}/{len(items)}] {country} / {keyword}")
        rec = fetch_keyword_via_cdp(country, keyword, max_asins=max_asins_per_kw)
        out.append({**it, "rec": rec})
        log(f"  ✓ asin_count={rec['asin_count']} ok={rec['ok']}")
    if not keep_browser:
        try:
            subprocess.run("taskkill /F /IM msedge.exe", shell=True, capture_output=True)
        except Exception:
            pass
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