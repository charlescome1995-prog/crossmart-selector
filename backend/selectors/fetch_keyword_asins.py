#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector · 关键词 → Amazon 搜索页整页 ASIN 抓取

输入 : crossmart-selector/frontend/data/strategy.json (Part B 输出, 4 桶)
输出 : crossmart-selector/frontend/data/keyword_asins.json
       { COUNTRY: { keyword: [asin, ...all 48] } }
       整页覆盖 (闫旭 2026-07-24)

依赖 :
  - crossmart-monitor/backend/browser/{cdp_bridge,amazon_browser,sprite_bridge,asin_monitor,keyword_monitor}.py
  - Edge 默认 profile (9225) + 卖家精灵扩展 (用户手动激活一次)

闫旭原则 :
  - 整页抓 (48 个), 不限量
  - 字段全要 (卖家精灵扩展给的 + Amazon 页面本身的)
  - 给用户留登录/激活卖家精灵的时间 (脚本启动后无固定等待期, 由用户自己说 "GO")
"""
import sys
import os
import json
import re
import time

# 强制 UTF-8 (Windows + 德语关键词)
sys.stdout.reconfigure(encoding='utf-8')

# ─── 加 monitor 那边的模块路径 (sys.path, 不复制代码) ───
SEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MON_BACKEND = os.path.normpath(os.path.join(SEL_ROOT, '..', 'crossmart-monitor', 'backend'))
if MON_BACKEND not in sys.path:
    sys.path.insert(0, MON_BACKEND)

from browser.cdp_bridge import CDPBrowser, ensure_edge_running  # noqa: E402
from browser.amazon_browser import AmazonBrowser  # noqa: E402
from browser.asin_monitor import extract_asin_data, extract_sprite_plugin_data  # noqa: E402

# ─── 路径 ───
FRONTEND_DATA = os.path.join(SEL_ROOT, 'frontend', 'data')
STRATEGY_JSON = os.path.join(FRONTEND_DATA, 'strategy.json')
OUT_JSON = os.path.join(FRONTEND_DATA, 'keyword_asins.json')

# ─── 国别 → Amazon 域名 ───
DOMAIN_MAP = {
    'UK': 'amazon.co.uk',
    'DE': 'amazon.de',
    'CA': 'amazon.ca',
    'US': 'amazon.com',
}

# ─── 限速 (Amazon 反爬) ───
PAGE_PAUSE = 4          # 翻下一页之间
SEARCH_PAUSE = 3        # 关键词间


def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


def load_strategy_keywords():
    """读 strategy.json, 反向解析: (country, keyword) 列表"""
    if not os.path.exists(STRATEGY_JSON):
        raise FileNotFoundError(f'{STRATEGY_JSON} 不存在, 先跑 strategy_router.py')
    with open(STRATEGY_JSON, 'r', encoding='utf-8') as f:
        s = json.load(f)

    pairs = []  # [(country, keyword, bucket), ...]
    bucket_name_map = {
        '品牌创新': 'Brand Innovation',
        'newrelease': 'New Release',
        '模仿跟风': 'Follow Crowd',
        '老款延伸': 'Legacy Extension',
    }
    for backend_key, b in (s.get('buckets') or {}).items():
        for it in (b.get('items') or []):
            country = it.get('country')
            keyword = it.get('keyword')
            if country and keyword:
                pairs.append((country, keyword, bucket_name_map.get(backend_key, backend_key)))
    return pairs, s.get('generated_at', '')


def parse_search_page_full(browser, country, max_results=48):
    """
    在 Amazon 搜索结果页提取全部搜索结果 ASIN (TOP 48)
    返回 : [{asin, rank, title_plain, sponsored}, ...]
    (这一页只拿 ASIN 列表 + 简要信息, 不进详情)
    """
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
        log(f'   [JS err] {e}')
    return []


def extract_seller_sprite_panel(browser):
    """卖家精灵扩展: 整页 summary (LQS/变体数/Top Traffic Words)"""
    js = r"""
    (() => {
        var out = {};
        // sprite 元素 (on-click 模式激活后, DOM 里会出现 .seller-sprite-* / [class*=seller-sprite])
        var panel = document.querySelector('.seller-sprite-panel, [class*=seller-sprite-popup], [id*=seller-sprite]');
        if (!panel) {
            // 退化: 任何包含关键词 "LQS" 的块
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
        log(f'   [sprite JS err] {e}')
    return {'has_panel': False}


def search_one(browser, country, keyword, max_results=48):
    """开 Amazon 搜索 → 抓整页 ASIN (含卖家精灵面板)"""
    domain = DOMAIN_MAP.get(country, 'amazon.com')
    url = f'https://{domain}/s?k=' + re.sub(r'\s+', '+', keyword.strip())
    log(f'  → {country} : {keyword!r}  (打开 {domain})')
    browser.navigate(url)
    time.sleep(SEARCH_PAUSE)

    # 等待搜索结果加载
    for attempt in range(10):
        asins = parse_search_page_full(browser, country, max_results)
        if len(asins) >= 10:
            break
        time.sleep(1)

    sprite = extract_seller_sprite_panel(browser)
    if sprite.get('has_panel'):
        log(f'     卖家精灵面板: ✓ ({(sprite.get("panel_text") or "")[:80]!r})')
    else:
        log(f'     卖家精灵面板: ✗ (你需要手动激活一次 seller-sprite)')

    return {
        'country': country,
        'keyword': keyword,
        'asin_count': len(asins),
        'asin_list': [a['asin'] for a in asins],
        'detail': asins,        # title/price/rating/reviews/sponsored
        'seller_sprite': sprite,
        'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }


def run(start_with_one=None):
    """
    主流程:
    - 启 Edge (默认 profile, 9225)
    - 读 strategy.json, 反向解析 (country, keyword) 列表
    - 一次跑完所有 (country, keyword) 组合, 抓整页
    - 整页覆盖 keyword_asins.json
    """
    pairs, strategy_at = load_strategy_keywords()
    log(f'共 {len(pairs)} 个 (国家, 关键词) 组合要从 strategy.json 抓')
    for c, kw, bucket in pairs[:5]:
        log(f'   · [{c}] {kw}  →  {bucket}')

    # 可选: 只跑 1 个 (测试用)
    if start_with_one:
        idx = 0
        for i, (c, kw, _) in enumerate(pairs):
            if c == start_with_one[0] and kw == start_with_one[1]:
                idx = i
                break
        pairs = pairs[idx:idx+1]
        log(f'⚙️ 测试模式: 只跑 1 个 ({start_with_one})')

    log('=' * 60)
    log('🚀 Step 2: 浏览器抓 ASIN')
    log('=' * 60)

    # 确保 Edge 在 9225 跑 (不指定 --user-data-dir)
    log('启动/确认 Edge (port 9225, 默认 profile)...')
    if not ensure_edge_running(port=9225):
        log('❌ 启动 Edge 失败')
        return None

    time.sleep(2)

    browser = CDPBrowser()
    browser.connect_tab(tab_url_filter='about:blank')
    if not browser.tab:
        browser.cmd('Target.createTarget', {'url': 'about:blank'})
        time.sleep(0.5)
        browser.connect_tab(tab_url_filter='about:blank')
    log(f'✓ CDP 已连接: tab={browser.tab}')

    results = {}
    started_at = time.strftime('%Y-%m-%dT%H:%M:%S')
    try:
        for i, (country, keyword, bucket) in enumerate(pairs, 1):
            log(f'[{i}/{len(pairs)}]')
            try:
                rec = search_one(browser, country, keyword, max_results=48)
                rec['bucket'] = bucket
                key = f'{country}::{keyword}'
                results[key] = rec
            except Exception as e:
                log(f'   ❌ {country} {keyword}: {e}')
                results[f'{country}::{keyword}'] = {'error': str(e)}
            # 限速 (Amazon 反爬)
            if i < len(pairs):
                time.sleep(PAGE_PAUSE)

            # 周期性落盘 (避免脚本中断丢数据)
            if i % 5 == 0 or i == len(pairs):
                _save_partial(results, started_at, strategy_at, finished=(i == len(pairs)))
    finally:
        try:
            browser.close()
        except Exception:
            pass

    return results


def _save_partial(results, started_at, strategy_at, finished=False):
    """周期性 / 最终落盘: 整页覆盖 keyword_asins.json"""
    os.makedirs(FRONTEND_DATA, exist_ok=True)
    payload = {
        'meta': {
            'started_at': started_at,
            'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S') if finished else None,
            'strategy_generated_at': strategy_at,
            'total_keywords': len(results),
            'complete': finished,
        },
        'records': results,
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f'   💾 已写盘 {OUT_JSON}  ({len(results)} 条, finished={finished})')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--test', nargs=2, metavar=('COUNTRY', 'KW'),
                   help='只抓 1 个 (country, keyword) 验证')
    args = p.parse_args()
    run(start_with_one=tuple(args.test) if args.test else None)
