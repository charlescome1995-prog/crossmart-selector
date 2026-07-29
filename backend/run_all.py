# -*- coding: utf-8 -*-
"""
run_all.py — 一键端到端跑选品流水线（用户主入口）

按顺序：
  [1/4] quick_filter  Excel → 48 条候选（黑名单 + 阈值 + 品类过滤）
  [2/4] triage        候选 → 🔴🟡🟢 三档
  [3/4] strategy_router  🟢🟡 → 4 桶（品牌创新 / newrelease / 模仿跟风 / 老款延伸）
  [4/4] run_selection Excel + 4 桶 → selection-data.json + Part A+ 浏览器补抓 keyword_asins.json

关闭浏览器抓取：set PART_A_PLUS=0 或 export PART_A_PLUS=0
限制 ASIN 数 / 关键词：set PART_A_PLUS_MAX_ASINS=10
不推 hub：       set PUSH_HUB=0
"""
import os
import sys
import subprocess
from pathlib import Path

_THIS = Path(__file__).resolve().parent


def _run(label, script_relpath, *args):
    """子进程调一个 selectors/*.py，捕获输出显示前缀"""
    script = _THIS / script_relpath
    print(f'\n{"="*70}\n[{label}] {script.name} {" ".join(args)}\n{"="*70}', flush=True)
    cmd = [sys.executable, '-X', 'utf8', str(script), *args]
    proc = subprocess.run(cmd, cwd=str(_THIS))
    if proc.returncode != 0:
        print(f'  ⚠️ {label} 退出码 {proc.returncode}（继续下一步）', flush=True)
    return proc.returncode


def main():
    print('=' * 70)
    print('🚀 CrossMart Selector · 一键端到端')
    print('=' * 70)
    print(f'  PART_A_PLUS       = {os.environ.get("PART_A_PLUS", "1")}（0 = 跳过浏览器抓）')
    print(f'  PART_A_PLUS_MAX   = {os.environ.get("PART_A_PLUS_MAX_ASINS", "20")} ASIN/词')
    print(f'  PUSH_HUB          = {os.environ.get("PUSH_HUB", "1")}（0 = 跳过 hub 同步）')
    print()

    # [1/4] quick_filter
    r1 = _run('1/4', 'selectors/quick_filter.py')
    if r1 != 0:
        print('⚠️ quick_filter 失败，但继续')

    # [2/4] triage
    r2 = _run('2/4', 'selectors/triage.py')
    if r2 != 0:
        print('⚠️ triage 失败，但继续')

    # [3/4] strategy_router
    r3 = _run('3/4', 'selectors/strategy_router.py')
    if r3 != 0:
        print('⚠️ strategy_router 失败，但继续')

    # [4/4] run_selection（含 Part A+ 浏览器抓）
    r4 = _run('4/4', 'run_selection.py')

    print('\n' + '=' * 70)
    print('📊 流水线结束')
    print('=' * 70)
    print('前端消费文件:')
    print('  frontend/data/strategy.json         ← selection.html 4 桶')
    print('  frontend/data/keyword_asins.json    ← selection.html Step 2 展开')
    print('  frontend/data/selection-data.json   ← 全部 products（备份）')
    print()
    print('部署: git add -A && git commit -m "data: 本周选品" && git push')
    return 0


if __name__ == '__main__':
    sys.exit(main())
