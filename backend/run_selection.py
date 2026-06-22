# -*- coding: utf-8 -*-
"""
CrossMart Selector - 选品主入口
=================================
每周流程：
  1. 把卖家精灵导出的 Excel 放到 backend/data/input/
  2. 运行：python backend/run_selection.py
  3. 自动生成 frontend/data/selection-data.json
  4. git push 部署到 GitHub Pages

逻辑沿用旧引擎（amazon_ai_kit）：16 核心指标 + 4 策略 + FBA 利润模型。
本入口负责：动态规整日期列名、复用引擎函数、计算综合评分、输出前端 JSON。
"""
import sys, os, re, json, glob
from datetime import datetime

_THIS = os.path.dirname(os.path.abspath(__file__))
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from config import RAW_DATA_DIR, STRATEGY_CONFIG
from selectors.product_selector import (
    check_16_indicators,
    calculate_profit_margin,
    calculate_profit_per_unit,
    check_strategy_match,
    is_seasonal,
    is_trending,
    get_category_priority,
    analyze_5w1h_scene,
)

KW_COL = '关键词(绿色建议进入，黄色找切入点，粉色观察)'
OUTPUT_JSON = os.path.join(_THIS, '..', 'frontend', 'data', 'selection-data.json')

# 策略英文名 → 前端标签
STRATEGY_LABEL = {
    'strategy1_blue_ocean': '蓝海',
    'strategy2_red_ocean': '红海',
    'strategy3_differentiation': '差异化',
    'strategy4_follow': '跟随',
}


def find_latest_excel():
    """找 input 目录里最新的关键词 Excel"""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    files = glob.glob(os.path.join(RAW_DATA_DIR, '*.xlsx'))
    files = [f for f in files if not os.path.basename(f).startswith('~$')]
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def normalize_date_columns(df):
    """
    把带日期的列（每周变化）规整为引擎期望的固定列名：
      - 4 个 \\d{8}排名 列（按日期升序）→ 20260106/13/20/27排名
      - \\d{8}月搜 → 20260113月搜
    """
    rename = {}

    # 排名列：找所有 \d{8}排名，按日期排序，映射到引擎固定的 4 个名
    rank_cols = sorted([c for c in df.columns if re.match(r'^\d{8}排名$', str(c))])
    fixed_rank = ['20260106排名', '20260113排名', '20260120排名', '20260127排名']
    if len(rank_cols) >= 4:
        # 取最早 + 最晚等 4 个（若多于 4 个，取首尾间隔）
        picked = [rank_cols[0], rank_cols[len(rank_cols)//3],
                  rank_cols[2*len(rank_cols)//3], rank_cols[-1]]
        for src, dst in zip(picked, fixed_rank):
            rename[src] = dst
    elif len(rank_cols) > 0:
        # 不足 4 个：把现有的铺到固定名（首=earliest，尾=latest）
        rename[rank_cols[0]] = '20260106排名'
        rename[rank_cols[-1]] = '20260127排名'
        if len(rank_cols) >= 2:
            rename[rank_cols[1]] = '20260113排名'
            rename[rank_cols[-1]] = '20260120排名'
            rename[rank_cols[-1]] = '20260127排名'

    # 月搜列
    search_cols = [c for c in df.columns if re.match(r'^\d{8}月搜$', str(c))]
    if search_cols:
        rename[search_cols[0]] = '20260113月搜'

    df = df.rename(columns=rename)

    # 若仍缺固定排名列，用已有的补齐（避免 KeyError）
    if '20260106排名' in df.columns:
        for col in fixed_rank:
            if col not in df.columns:
                df[col] = df['20260106排名']
    if '20260113月搜' not in df.columns:
        # 兜底：找任何 月搜 列
        any_search = [c for c in df.columns if '月搜' in str(c)]
        if any_search:
            df['20260113月搜'] = df[any_search[0]]

    return df


def to_numeric(df):
    numeric_cols = ['20260113月搜', '月购', '月展示', '月点击', '需供比', '点击集中度',
                    '转化集中度', 'SPR', '标题密度', '广告竞品数', '评分数', '评分值',
                    '价格（美元）', 'PCP竞价（美元）', '购买率']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    rank_cols = ['20260106排名', '20260113排名', '20260120排名', '20260127排名']
    for col in rank_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def compute_score(row, indicators, margin):
    """
    综合评分 0-100（前端用：≥85🔥强推 / ≥70⚡考虑 / 其余👀观察）
    权重：16指标通过率 40% + 毛利率 25% + 市场热度 20% + 竞争宽松度 15%
    """
    # 1. 指标通过率（0-100）
    pass_score = indicators.get('pass_rate', 0)

    # 2. 毛利率（30%=满分基准，封顶 100）
    margin_score = min(margin / 30 * 100, 100) if margin > 0 else 0

    # 3. 市场热度（月搜 8k-50k 映射 0-100）
    ms = row.get('20260113月搜', 0) or 0
    heat_score = min(max((ms - 8000) / (50000 - 8000), 0), 1) * 100

    # 4. 竞争宽松度（广告竞品数越少越好，0-150 映射 100-0）
    pc = row.get('广告竞品数', 0) or 0
    comp_score = max(0, 1 - pc / 150) * 100

    score = pass_score * 0.4 + margin_score * 0.25 + heat_score * 0.2 + comp_score * 0.15
    return round(score, 1)


def run():
    print('=' * 70)
    print('CrossMart Selector - 选品引擎')
    print('=' * 70)

    excel = find_latest_excel()
    if not excel:
        print(f'❌ 未找到 Excel，请把卖家精灵导出文件放到：\n   {RAW_DATA_DIR}')
        return 1
    print(f'📥 读取: {os.path.basename(excel)}')

    df = pd.read_excel(excel)
    print(f'   原始行数: {len(df):,}')

    df = normalize_date_columns(df)
    df = to_numeric(df)

    # 排名变化
    df['rank_earliest'] = df.get('20260106排名')
    df['rank_latest'] = df.get('20260127排名')
    df['rank_change'] = df['rank_earliest'] - df['rank_latest']
    df['rank_change_rate'] = df['rank_change'] / (df['rank_earliest'] + 1)

    # 毛利率
    df['预估毛利率'] = df['价格（美元）'].apply(calculate_profit_margin)

    # 清理
    df = df[(df['rank_earliest'] > 0) & (df['rank_latest'] > 0)].copy()
    df = df.dropna(subset=['20260113月搜', '广告竞品数', '价格（美元）'])
    print(f'   有效行数: {len(df):,}')

    # 4 策略筛选
    print('\n执行 4 策略筛选...')
    all_selected = []
    seen = set()
    strategy_keys = ['strategy1_blue_ocean', 'strategy2_red_ocean',
                     'strategy3_differentiation', 'strategy4_follow']
    for key in strategy_keys:
        cfg = STRATEGY_CONFIG[key]
        quota = cfg.get('quota', 30)
        filtered = df[df.apply(lambda r: check_strategy_match(r, key), axis=1)]
        filtered = filtered[~filtered[KW_COL].isin(seen)]
        filtered = filtered.sort_values('rank_change', ascending=False).head(quota)
        if len(filtered) > 0:
            f = filtered.copy()
            f['_strategy_key'] = key
            all_selected.append(f)
            seen.update(f[KW_COL].tolist())
        print(f'  {STRATEGY_LABEL[key]}: {len(filtered)}/{quota}')

    if not all_selected:
        print('⚠️  策略筛选结果为空，输出空数据集')
        df_final = df.head(0).copy()
        df_final['_strategy_key'] = []
    else:
        df_final = pd.concat(all_selected, ignore_index=True)
        max_quota = STRATEGY_CONFIG.get('total_quota', 100)
        if len(df_final) > max_quota:
            df_final = df_final.head(max_quota)

    # 逐行分析 → 组装 JSON
    products = []
    for _, row in df_final.iterrows():
        keyword = str(row[KW_COL])
        price = float(row['价格（美元）']) if pd.notna(row['价格（美元）']) else 0
        indicators = check_16_indicators(row)
        margin = calculate_profit_margin(price)
        profit = calculate_profit_per_unit(price, margin)
        priority, note = get_category_priority(keyword)

        # 过滤食品类
        if priority == '❌过滤':
            continue

        score = compute_score(row, indicators, margin)
        scene = analyze_5w1h_scene(keyword,
                                   row.get('20260113月搜', 0),
                                   price,
                                   row.get('评分数', 0),
                                   row.get('评分值', 0))

        def safe_int(v):
            try:
                return int(v) if pd.notna(v) else 0
            except Exception:
                return 0

        def safe_float(v, d=1):
            try:
                return round(float(v), d) if pd.notna(v) else 0
            except Exception:
                return 0

        products.append({
            'keyword': keyword,
            'url': str(row.get('网址', '')) if pd.notna(row.get('网址', '')) else '',
            'category': str(row.get('品类组', '')) if pd.notna(row.get('品类组', '')) else '',
            'strategy': STRATEGY_LABEL.get(row.get('_strategy_key', ''), ''),
            'score': score,
            'margin': margin,
            'profit': profit,
            'price': safe_float(price, 2),
            'rating': safe_float(row.get('评分值'), 1),
            'reviews': safe_int(row.get('评分数')),
            'sellers': safe_int(row.get('广告竞品数')),
            'monthly_search': safe_int(row.get('20260113月搜')),
            'monthly_purchase': safe_int(row.get('月购')),
            'spr': safe_int(row.get('SPR')),
            'need_supply': safe_float(row.get('需供比'), 1),
            'conv_conc': safe_float(row.get('转化集中度'), 3),
            'click_conc': safe_float(row.get('点击集中度'), 3),
            'pcp_price': safe_float(row.get('PCP竞价（美元）'), 2),
            'rank_earliest': safe_int(row.get('rank_earliest')),
            'rank_latest': safe_int(row.get('rank_latest')),
            'rank_change_rate': safe_float(row.get('rank_change_rate'), 3),
            'pass_rate': round(indicators.get('pass_rate', 0), 0),
            'seasonal': bool(is_seasonal(keyword)),
            'trending': bool(is_trending(keyword)),
            'category_note': note,
            'scene': scene.get('who', '') + '/' + scene.get('where', ''),
        })

    # 按评分降序
    products.sort(key=lambda x: x['score'], reverse=True)

    out = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source_file': os.path.basename(excel),
        'total': len(products),
        'strategy_dist': _dist(products, 'strategy'),
        'products': products,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 精选 {len(products)} 个产品')
    print(f'   策略分布: {out["strategy_dist"]}')
    print(f'📤 已输出: {OUTPUT_JSON}')
    if products:
        avg_score = sum(p['score'] for p in products) / len(products)
        avg_margin = sum(p['margin'] for p in products) / len(products)
        print(f'   平均评分: {avg_score:.1f} | 平均毛利: {avg_margin:.1f}%')
        print(f'   Top3: ' + ' / '.join(p['keyword'][:20] for p in products[:3]))
    return 0


def _dist(products, key):
    d = {}
    for p in products:
        d[p[key]] = d.get(p[key], 0) + 1
    return d


if __name__ == '__main__':
    sys.exit(run())
