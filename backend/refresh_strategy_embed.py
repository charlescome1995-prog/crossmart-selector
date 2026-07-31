# -*- coding: utf-8 -*-
"""
refresh_strategy_embed.py — 一次性：把 strategy.json 的 buckets 重新嵌入到 selection-data.json

2026-07-30 用途：
  - run_selection.py 在 Part A+ 完成后才嵌入 strategy.buckets 到 selection-data.json，
    但 Part A+ 是 100 分钟级的浏览器抓取，不会轻易重跑。
  - strategy_router.py 加了 kw_zh 透传后，新 strategy.json 已经有 23/23 kw_zh，
    但 selection-data.json 里嵌入的 strategy.buckets.items 还是上一轮旧值（kw_zh 全空）。
  - 前端实际读 selection-data.json（不是 strategy.json），所以「4 桶表中文标签」bug 没修。
  - 这个脚本：5 秒把新 strategy.json 的 buckets.items 替换进 selection-data.json 的 strategy.buckets.items，
    不重跑 Part A+，前端刷新即可。

用法：
    python backend/refresh_strategy_embed.py
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SEL_ROOT = os.path.dirname(os.path.abspath(__file__))
STRATEGY_JSON = os.path.join(SEL_ROOT, '..', 'frontend', 'data', 'strategy.json')
SELECTION_JSON = os.path.join(SEL_ROOT, '..', 'frontend', 'data', 'selection-data.json')


def main():
    if not os.path.exists(STRATEGY_JSON):
        print(f'❌ 找不到 {STRATEGY_JSON}')
        sys.exit(1)
    if not os.path.exists(SELECTION_JSON):
        print(f'❌ 找不到 {SELECTION_JSON}')
        sys.exit(1)

    with open(STRATEGY_JSON, 'r', encoding='utf-8') as f:
        strategy = json.load(f)
    with open(SELECTION_JSON, 'r', encoding='utf-8') as f:
        selection = json.load(f)

    new_buckets = strategy.get('buckets', {})
    if not new_buckets:
        print(f'❌ strategy.json 里 buckets 为空')
        sys.exit(1)

    # 验证：新 buckets 里 kw_zh 覆盖率
    new_total = 0
    new_with_zh = 0
    for bucket in new_buckets.values():
        items = bucket.get('items', [])
        new_total += len(items)
        new_with_zh += sum(1 for it in items if it.get('kw_zh'))
    print(f'📊 新 strategy.json: {new_with_zh}/{new_total} 桶 items 有 kw_zh')

    # 旧 selection-data.json 里嵌入的 strategy.buckets 覆盖率
    old_embedded = (selection.get('strategy') or {}).get('buckets') or {}
    old_total = 0
    old_with_zh = 0
    for bucket in old_embedded.values():
        items = bucket.get('items', [])
        old_total += len(items)
        old_with_zh += sum(1 for it in items if it.get('kw_zh'))
    print(f'📊 旧 selection-data.json 嵌入: {old_with_zh}/{old_total} 桶 items 有 kw_zh')

    if old_with_zh == new_with_zh and old_total == new_total:
        print(f'✅ 两边一致，无需刷新')
        return

    # 替换 selection-data.json 里的 strategy.buckets
    if 'strategy' not in selection or not isinstance(selection['strategy'], dict):
        selection['strategy'] = {}
    selection['strategy']['buckets'] = new_buckets
    # 顺便同步 legacy_keywords + stats + generated_at
    selection['strategy']['legacy_keywords'] = strategy.get('legacy_keywords', [])
    selection['strategy']['stats'] = strategy.get('stats', {})
    selection['strategy']['generated_at'] = strategy.get('generated_at')

    # 写回
    with open(SELECTION_JSON, 'w', encoding='utf-8') as f:
        json.dump(selection, f, ensure_ascii=False, indent=2)

    print(f'✅ 已把 strategy.buckets 重新嵌入 selection-data.json')
    print(f'   覆盖: {old_total} 条 → {new_total} 条 (kw_zh: {old_with_zh} → {new_with_zh})')


if __name__ == '__main__':
    main()