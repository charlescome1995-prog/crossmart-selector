# -*- coding: utf-8 -*-
"""debug_ss_text.py — 看 EXTRACT_JS 实际拿到的 ss_text 长什么样"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from selectors.fetch_keyword_asins import (
    start_edge_cdp, fetch_keyword_via_cdp, EXTRACT_JS
)

if __name__ == '__main__':
    country = sys.argv[1] if len(sys.argv) > 1 else 'US'
    keyword = sys.argv[2] if len(sys.argv) > 2 else 'essence nose ring diffuser'

    print(f'TEST: {country} / {keyword}')
    if not start_edge_cdp():
        sys.exit(1)
    try:
        rec = fetch_keyword_via_cdp(country, keyword, max_asins=3, max_retries=1)
    finally:
        subprocess.run('taskkill /F /IM msedge.exe', shell=True, capture_output=True)
    if not rec or not rec.get('detail'):
        print('FAIL no detail'); sys.exit(1)
    for i, a in enumerate(rec['detail'][:3]):
        ss = a.get('ss_text') or ''
        print(f"\n=== ASIN {i}: {a['asin']} (ss_text len={len(ss)}) ===")
        if ss:
            print(ss[:600])
        else:
            print('(empty)')
        print(f"  has_ss={a.get('ss_has_ss')}, ss_brand={a.get('ss_brand')!r}")
        print(f"  ss_all_traffic_words={a.get('ss_all_traffic_words')!r}")
        print(f"  ss_days_listed={a.get('ss_days_listed')!r}")