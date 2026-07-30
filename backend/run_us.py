# -*- coding: utf-8 -*-
"""
run_us.py — 只跑 US 一站（不破坏原 run_all.py）

用法（**一个命令**搞定）：
    python backend/run_us.py

跟 run_all.py 的差异：
  - run_all.py : 4 站全跑（quick_filter → triage → strategy_router → run_selection）
  - run_us.py  : 同样的 4 步，最后一步 run_selection 只抓 US
                  （Part A+ 省 ~75% 时间，UK/DE/CA 沿用旧数据）

为什么不动 run_all.py：
  - 原 `python run_all.py` 命令必须保持 4 站全跑行为不变
  - US-only 是临时入口，新建独立脚本即可

输出文件（与 run_all.py 一致）：
  frontend/data/strategy.json         ← selection.html 4 桶
  frontend/data/keyword_asins.json    ← US 词详（新抓）+ UK/DE/CA（旧数据保留）
  frontend/data/selection-data.json   ← 全部 products（备份）

部署：
  git add -A && git commit -m "data: US 选品" && git push
"""
import subprocess
import sys
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
    print('🇺🇸 CrossMart Selector · US-Only 端到端')
    print('=' * 70)
    print('  step 1-3: 仍跑全 4 站（离线 pandas，几秒）→ 保证 strategy.json 完整')
    print('  step 4  : Part A+ 只抓 US（带翻页早停）→ 节省 ~75% 抓取时间')
    print('  写盘    : 增量合并 keyword_asins.json（US 新抓 + 其他国旧数据保留）')
    print()

    # [1/4] quick_filter（4 站全跑，几秒）
    r1 = _run('1/4', 'selectors/quick_filter.py')
    if r1 != 0:
        print('⚠️ quick_filter 失败，但继续')

    # [2/4] triage（4 站全跑，几秒）
    _run('2/4', 'selectors/triage.py')

    # [3/4] strategy_router（4 站全跑，几秒）
    _run('3/4', 'selectors/strategy_router.py')

    # [4/4] run_selection（--country US → Part A+ 只抓 US）
    _run('4/4', 'run_selection.py', '--country', 'US')

    print('\n' + '=' * 70)
    print('✅ US-Only 流水线结束')
    print('=' * 70)
    print('前端消费文件:')
    print('  frontend/data/strategy.json         ← selection.html 4 桶')
    print('  frontend/data/keyword_asins.json    ← US 词详（新抓）+ 其他国（旧）')
    print('  frontend/data/selection-data.json   ← 全部 products（备份）')
    print()
    print('部署: git add -A && git commit -m "data: US 选品" && git push')
    return 0


if __name__ == '__main__':
    sys.exit(main())