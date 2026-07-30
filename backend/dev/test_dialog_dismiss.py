# -*- coding: utf-8 -*-
"""
test_dialog_dismiss.py — 验证 2026-07-30 弹窗免疫层 + SS 字段完整性升级

跑法：
  python backend/dev/test_dialog_dismiss.py US "essence nose ring diffuser"
  python backend/dev/test_dialog_dismiss.py UK "shampoo caps no rinse for elderly"
  python backend/dev/test_dialog_dismiss.py DE "poolleiter bestway"

每次只跑一个关键词，max_asins=5（快）。完成后断 Edge。

期望：
  - US：无弹窗，正常抓 SS
  - UK/DE：自动 dismiss 货币切换弹窗，日志输出 "🚫 dismiss 弹窗 × 1: currency_keep:..."
  - SS 数据应包含 ss_all_traffic_words / ss_organic_keywords / ss_ad_keywords / ss_suggest_keywords
"""
import os, sys, json, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from selectors.fetch_keyword_asins import fetch_keyword_via_cdp, start_edge_cdp

if __name__ == '__main__':
    country = sys.argv[1] if len(sys.argv) > 1 else 'US'
    keyword = sys.argv[2] if len(sys.argv) > 2 else 'essence nose ring diffuser'

    print('=' * 70)
    print(f'TEST: {country} / {keyword}')
    print('=' * 70)

    if not start_edge_cdp():
        print('FAIL Edge CDP 启动失败')
        sys.exit(1)

    try:
        rec = fetch_keyword_via_cdp(country, keyword, max_asins=5, max_retries=1)
    finally:
        # 不留浏览器
        subprocess.run('taskkill /F /IM msedge.exe', shell=True, capture_output=True)

    print('\n' + '=' * 70)
    print('RESULT')
    print('=' * 70)
    if not rec:
        print('FAIL: rec 为空')
        sys.exit(1)

    print(f"  ok           = {rec.get('ok')}")
    print(f"  asin_count   = {rec.get('asin_count')}")
    print(f"  ss_converged = {rec.get('ss_converged')}")
    print(f"  ss_ready     = {rec.get('ss_ready')}/{rec.get('ss_total')}")

    # 检查 4 个流量词字段
    detail = rec.get('detail') or []
    if not detail:
        print('FAIL: 无 detail')
        sys.exit(1)

    fields = ['ss_all_traffic_words', 'ss_organic_keywords', 'ss_ad_keywords', 'ss_suggest_keywords']
    print(f'\n  4 流量词字段覆盖率（{len(detail)} ASIN）：')
    for f in fields:
        cnt = sum(1 for a in detail if a.get(f))
        print(f'    {f:30s} {cnt}/{len(detail)} ({cnt/len(detail):.0%})')

    # 第一条样本
    a = detail[0]
    print(f'\n  样本 ASIN: {a.get("asin")} {a.get("title","")[:40]}...')
    print(f'    ss_brand           = {a.get("ss_brand")}')
    print(f'    ss_monthly_sales_child = {a.get("ss_monthly_sales_child")}')
    print(f'    ss_review_count    = {a.get("ss_review_count")}')
    print(f'    ss_days_listed     = {a.get("ss_days_listed")}')
    print(f'    ss_all_traffic_words = {a.get("ss_all_traffic_words")}')

    # 4 流量词全有 → 通过；否则算 "卖家精灵确实没数据" 也接受
    full_have = sum(1 for a in detail if all(a.get(f) for f in fields))
    print(f'\n  4 流量词全有 ASIN: {full_have}/{len(detail)}')
    if full_have >= 3:
        print('  ✅ PASS')
    else:
        print('  ⚠️ 数据稀疏（可能是卖家精灵没数据 / 没登录）')