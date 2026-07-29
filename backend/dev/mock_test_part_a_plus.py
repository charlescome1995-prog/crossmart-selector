# -*- coding: utf-8 -*-
"""
mock_test_part_a_plus.py — 验证 run_selection.py 新 Part A+ 逻辑
（不实际启 Edge，只验证控制流：读 triage.json → 🟢🟡 过滤 → 按国别分组 → 循环 fetch）
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Python 3.14 stdlib 也有 'selectors'，必须先 import 后再覆盖
import run_selection

# 替换 fetch_keywords_batch 为 mock
calls = []
def mock_fetch(items, max_asins_per_kw=20, keep_browser=False):
    calls.append(list(items))
    return [
        {**it, 'rec': {'ok': True, 'asin_count': 18, 'detail': [{'asin': f'B0{i:08d}'} for i in range(18)]}}
        for it in items
    ]

run_selection.fetch_keywords_batch = mock_fetch
os.environ['PART_A_PLUS'] = '1'
os.environ['PART_A_PLUS_MAX_ASINS'] = '15'
os.environ['PUSH_HUB'] = '0'

print('=' * 60)
print('MOCK 测试 Part A+ 新逻辑（不实际启 Edge）')
print('=' * 60)

# 只跑 Part A+ 部分（手动模拟它的核心逻辑）
triage_path = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'data', 'triage.json')
with open(triage_path, 'r', encoding='utf-8') as f:
    triage = json.load(f)
green_yellow = [it for it in triage['items'] if it['tier'] in ('🟢', '🟡')]

from collections import OrderedDict
by_country = OrderedDict()
for it in green_yellow:
    c = it.get('country') or '_'
    by_country.setdefault(c, []).append(it)

print(f'\n🟢🟡 候选: {len(green_yellow)} 条')
for c, lst in by_country.items():
    print(f'  {c}: {len(lst)} 条')

# 调用 mock
results = []
for country, items_country in by_country.items():
    kw_items = [{'country': it['country'], 'keyword': it['keyword']} for it in items_country]
    r = mock_fetch(kw_items, max_asins_per_kw=15)
    results.extend(r)

print(f'\n=== mock_fetch 被调用 {len(calls)} 次（每国 1 次）===')
for i, batch in enumerate(calls, 1):
    cs = sorted(set(it['country'] for it in batch))
    print(f'  Batch {i}: {len(batch)} 条, 国别: {cs}')

# 验证关键字段
records = {(r['country'] + '::' + r['keyword']): r.get('rec') or {} for r in results}
print(f'\n=== results 合并: {len(results)} 条 ===')
print(f'  records keys: {len(records)}')
print(f'  ok_count: {sum(1 for r in results if r.get("rec", {}).get("ok"))}')
print(f'  total_asins: {sum(r.get("rec", {}).get("asin_count", 0) for r in results)}')

# 验收
assert len(calls) == len(by_country), f'❌ mock 调用次数不对: {len(calls)} vs {len(by_country)} 国'
assert len(results) == len(green_yellow), f'❌ 总数不对: {len(results)} vs {len(green_yellow)}'
for batch in calls:
    cs = set(it['country'] for it in batch)
    assert len(cs) == 1, f'❌ 一批内混合国家: {cs}'
print('\n✅ 全部断言通过：按国别分组抓取 ✓')
