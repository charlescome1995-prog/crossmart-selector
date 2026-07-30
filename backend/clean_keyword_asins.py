# -*- coding: utf-8 -*-
"""
clean_keyword_asins.py — 一次性清洗旧 keyword_asins.json 的脏数据

2026-07-30 用途：
  - 老版 parse_ss_text 的 ss_rating regex 不兼容新 SS 格式「评分数: 4.4(157)」，
    导致 1898 条 ASIN 的 ss_rating 字段被错填成「评分数」（脏串）。
  - 同时 ss_price 也有少数非数字值。
  - 一次性脚本：把所有非「可选货币前缀 + 数字」的 ss_rating/ss_price 置 None。

用法：
    python backend/clean_keyword_asins.py
"""
import json
import os
import re
import sys

SEL_ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(SEL_ROOT, '..', 'frontend', 'data', 'keyword_asins.json')

VALID_NUM = re.compile(r'^[\$£€¥]?\d+(\.\d+)?$')


def main():
    if not os.path.exists(OUT_JSON):
        print(f'❌ 找不到 {OUT_JSON}')
        sys.exit(1)

    with open(OUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned = 0
    samples = []
    for rec in data.get('records', {}).values():
        for d in (rec.get('detail') or []):
            for k in ('ss_rating', 'ss_price'):
                v = d.get(k)
                if v is None:
                    continue
                v_str = str(v).strip()
                if v_str and not VALID_NUM.match(v_str):
                    if len(samples) < 3:
                        samples.append((d.get('asin'), k, v_str))
                    d[k] = None
                    cleaned += 1

    # 写回
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'✅ 已清洗 {OUT_JSON}')
    print(f'   共清洗 {cleaned} 条脏 ss_rating/ss_price → None')
    if samples:
        print(f'   样本（前 3 条）:')
        for asin, k, v in samples:
            print(f'     {asin} {k}: {v!r}')


if __name__ == '__main__':
    main()