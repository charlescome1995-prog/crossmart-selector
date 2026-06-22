# -*- coding: utf-8 -*-
"""
选区引擎 - 第1阶段：关键词层
借鉴卖家精灵「关键词挖掘→反查→分析」思路

核心功能：
1. 关键词竞争力评分
2. 市场机会分析（需供比、竞价、集中度）
3. 关键词→ASIN关联分析
4. 输出Top关键词清单供下一步选品

数据源：1Amazon关键词_20260322.xlsx (34565个关键词)
"""

import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "0_latest_rawdata")
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 1. 加载关键词数据
# ============================================================
def load_keyword_data():
    """加载关键词摘要数据"""
    data_file = os.path.join(DATA_DIR, "1Amazon关键词_20260322.xlsx")
    df = pd.read_excel(data_file)
    
    # 数值化
    numeric_cols = ['20260113月搜', '月购', '月展示', '月点击', '需供比', 
                    '点击集中度', '转化集中度', 'SPR', '标题密度', '广告竞品数',
                    '评分数', '评分值', '价格（美元）', 'PCP竞价（美元）', '购买率']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 计算排名变化（从4周排名看趋势）
    df['rank_earliest'] = pd.to_numeric(df['20260106排名'], errors='coerce')
    df['rank_latest'] = pd.to_numeric(df['20260127排名'], errors='coerce')
    df['rank_change'] = df['rank_earliest'] - df['rank_latest']  # 正=上升
    
    # 清洗无效数据
    df = df[(df['20260113月搜'] > 0) & (df['价格（美元）'] > 0)].copy()
    
    return df

# ============================================================
# 2. 关键词竞争力评分（卖家精灵风格）
# ============================================================
def score_keyword_competitiveness(row):
    """
    多维竞争力评分 (满分100)
    
    维度：
    - 搜索需求量 (20分): 月搜越高越好，但超高竞争也大
    - 竞价负担 (15分): PCP竞价低=进入成本低
    - 市场饱和度 (20分): 广告竞品数少=蓝海
    - 产品匹配 (15分): 价格合适=利润空间
    - 供需健康度 (15分): 需供比合理
    - 增长趋势 (15分): 排名上升趋势
    """
    score = 0
    details = []
    
    # 1. 搜索需求量 (20分)
    ms = row.get('20260113月搜', 0) or 0
    if 30000 <= ms <= 150000:
        score += 20
        details.append(f"搜索量{int(ms):,}(完美)")
    elif 10000 <= ms < 30000:
        score += 15
        details.append(f"搜索量{int(ms):,}(良好)")
    elif 5000 <= ms < 10000:
        score += 10
        details.append(f"搜索量{int(ms):,}(一般)")
    elif ms >= 150000:
        score += 8
        details.append(f"搜索量{int(ms):,}(超大)")
    elif ms > 0:
        score += 5
        details.append(f"搜索量{int(ms):,}(偏低)")
    
    # 2. 竞价负担 (15分)
    pcp = row.get('PCP竞价（美元）', 0) or 0
    if pcp <= 0.5:
        score += 15
        details.append(f"竞价${pcp:.2f}(低)")
    elif pcp <= 1.0:
        score += 12
        details.append(f"竞价${pcp:.2f}(中等)")
    elif pcp <= 2.0:
        score += 8
        details.append(f"竞价${pcp:.2f}(偏高)")
    else:
        score += 4
        details.append(f"竞价${pcp:.2f}(高)")
    
    # 3. 市场饱和度 (20分)
    comp = row.get('广告竞品数', 0) or 0
    if comp <= 50:
        score += 20
        details.append(f"竞品{int(comp)}(蓝海)")
    elif comp <= 150:
        score += 15
        details.append(f"竞品{int(comp)}(低竞争)")
    elif comp <= 300:
        score += 10
        details.append(f"竞品{int(comp)}(中等)")
    elif comp <= 500:
        score += 5
        details.append(f"竞品{int(comp)}(高竞争)")
    else:
        score += 2
        details.append(f"竞品{int(comp)}(红海)")
    
    # 4. 产品价格匹配 (15分)
    price = row.get('价格（美元）', 0) or 0
    if 15 <= price <= 40:
        score += 15
        details.append(f"价格${price:.0f}(甜蜜点)")
    elif 10 <= price < 15 or 40 < price <= 60:
        score += 10
        details.append(f"价格${price:.0f}(可接受)")
    elif price > 0:
        score += 5
        details.append(f"价格${price:.0f}(边缘)")
    
    # 5. 供需健康度 (15分)
    supply_demand = row.get('需供比', 0) or 0
    # 需供比 = 月搜/月购，越大说明需求>供给
    if 5 <= supply_demand <= 20:
        score += 15
        details.append(f"需供{supply_demand:.1f}(健康)")
    elif 3 <= supply_demand < 5:
        score += 12
        details.append(f"需供{supply_demand:.1f}(尚可)")
    elif 20 < supply_demand <= 50:
        score += 8
        details.append(f"需供{supply_demand:.1f}(需求大)")
    elif supply_demand > 0:
        score += 4
        details.append(f"需供{supply_demand:.1f}(不均衡)")
    
    # 6. 增长趋势 (15分)
    rank_earliest = row.get('rank_earliest', 0) or 0
    rank_latest = row.get('rank_latest', 0) or 0
    rank_change = row.get('rank_change', 0) or 0
    
    # 最新排名靠前加分
    if 0 < rank_latest <= 5000:
        score += 5
    elif 0 < rank_latest <= 20000:
        score += 3
    elif rank_latest > 0:
        score += 1
    
    # 上升趋势加分
    if rank_change > 500:
        score += 10
        details.append("排名↑↑")
    elif rank_change > 100:
        score += 7
        details.append("排名↑")
    elif rank_change > 0:
        score += 4
        details.append("排名微升")
    elif rank_change == 0:
        score += 2
    else:
        details.append("排名↓")
    
    return min(score, 100), details

# ============================================================
# 3. 类别分析（基于品类组）
# ============================================================
def analyze_category_opportunity(df):
    """分析每个品类的机会"""
    category_stats = []
    
    for cat in df['品类组一'].dropna().unique():
        sub = df[df['品类组一'] == cat]
        
        stats = {
            '品类': cat,
            '关键词数': len(sub),
            '平均月搜': int(sub['20260113月搜'].mean()),
            '总月搜': int(sub['20260113月搜'].sum()),
            '平均竞价': round(sub['PCP竞价（美元）'].mean(), 2),
            '平均竞品数': int(sub['广告竞品数'].mean()),
            '平均价格': round(sub['价格（美元）'].mean(), 2),
            '平均需供比': round(sub['需供比'].mean(), 1),
            '平均转化集中度': round(sub['转化集中度'].mean() * 100, 1),
        }
        category_stats.append(stats)
    
    return pd.DataFrame(category_stats).sort_values('平均月搜', ascending=False)

# ============================================================
# 4. 主流程
# ============================================================
def main():
    print("=" * 70)
    print("【第1阶段】关键词层 — 关键词竞争力评分")
    print("                 卖家精灵式关键词分析引擎")
    print("=" * 70)
    
    # 加载
    print(f"\n[1/4] 加载关键词数据...")
    df = load_keyword_data()
    print(f"  有效关键词: {len(df):,} 个")
    
    # 评分
    print(f"\n[2/4] 计算竞争力评分...")
    results = df.apply(score_keyword_competitiveness, axis=1)
    df['竞争力评分'] = [r[0] for r in results]
    df['评分细节'] = ['; '.join(r[1][:4]) for r in results]
    
    # 排序
    df = df.sort_values('竞争力评分', ascending=False)
    
    # 分级（卖家精灵S/A/B/C风格）
    def grade(score):
        if score >= 80: return 'S'
        if score >= 65: return 'A'
        if score >= 50: return 'B'
        return 'C'
    df['等级'] = df['竞争力评分'].apply(grade)
    
    # 统计
    print(f"\n[3/4] 等级分布:")
    for g in ['S', 'A', 'B', 'C']:
        c = (df['等级'] == g).sum()
        if c > 0:
            avg = df[df['等级'] == g]['竞争力评分'].mean()
            print(f"  {g}级: {c:,} 个 (平均分 {avg:.0f})")
    
    # Top 30展示
    print(f"\n{'='*70}")
    print("🏆 Top 30 关键词（按竞争力评分）")
    print(f"{'='*70}")
    
    top30 = df.head(30)
    for i, (_, row) in enumerate(top30.iterrows()):
        kw = str(row['关键词(绿色建议进入，黄色找切入点，粉色观察)'])[:35]
        print(f"\n{i+1:2d}. [{row['等级']}] [{row['竞争力评分']:2d}分] {kw}")
        print(f"     月搜:{int(row['20260113月搜']):,} | 竞品:{int(row['广告竞品数']):,} | 竞价:${row['PCP竞价（美元）']:.2f}")
        print(f"     需供比:{row['需供比']:.1f} | 价格:${row['价格（美元）']:.2f} | 排名:{int(row['rank_latest']):,}")
        print(f"     {row['评分细节'][:60]}")
    
    # 品类分析
    print(f"\n{'='*70}")
    print("📊 品类机会分析")
    print(f"{'='*70}")
    cat_df = analyze_category_opportunity(df)
    for _, row in cat_df.head(15).iterrows():
        print(f"  {row['品类']:25s} 月搜{int(row['平均月搜']):>6,} | 竞品{row['平均竞品数']:>4d} | "
              f"竞价${row['平均竞价']:.2f} | 价格${row['平均价格']:.1f} | 需供比{row['平均需供比']:.1f}")
    
    # 输出S级关键词
    print(f"\n{'='*70}")
    print("🌟 S级关键词详细清单")
    print(f"{'='*70}")
    s_level = df[df['等级'] == 'S'].head(20)
    for i, (_, row) in enumerate(s_level.iterrows()):
        print(f"\n  {row['关键词(绿色建议进入，黄色找切入点，粉色观察)']}")
        print(f"  月搜{int(row['20260113月搜']):,} | 月购{int(row['月购']):,} | 需供比{row['需供比']:.1f}")
        print(f"  竞品{int(row['广告竞品数']):,} | 价格${row['价格（美元）']:.2f} | 竞价${row['PCP竞价（美元）']:.2f}")
        print(f"  集中度(转化){row['转化集中度']:.1%} | SPR{int(row['SPR'])} | {row['品类组一']}")
    
    # 保存
    print(f"\n[4/4] 保存结果...")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 关键输出列
    out_cols = ['等级', '竞争力评分', '关键词(绿色建议进入，黄色找切入点，粉色观察)',
                '品类组一', '20260113月搜', '月购', '需供比', '广告竞品数',
                '价格（美元）', 'PCP竞价（美元）', '转化集中度', '点击集中度',
                'SPR', '标题密度', '评分数', '评分值', '购买率',
                'rank_earliest', 'rank_latest', 'rank_change', '评分细节']
    out_cols = [c for c in out_cols if c in df.columns]
    
    output_file = os.path.join(OUTPUT_DIR, f"关键词竞争力_{len(df)}条_{ts}.xlsx")
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.head(1000)[out_cols].to_excel(writer, index=False, sheet_name='关键词竞争力')
        ws = writer.sheets['关键词竞争力']
        ws.freeze_panes = 'A2'
        from openpyxl.styles import Font
        for c in ws[1]: c.font = Font(name='Times New Roman', size=11, bold=True)
        for ro in ws.iter_rows(min_row=2):
            for c in ro: c.font = Font(name='Times New Roman', size=10)
    
    # 品类分析单独保存
    cat_out = os.path.join(OUTPUT_DIR, f"品类机会_{ts}.xlsx")
    cat_df.to_excel(cat_out, index=False)
    
    print(f"  ✅ 关键词竞争力: {output_file}")
    print(f"  ✅ 品类机会: {cat_out}")
    print(f"\n{'='*70}")
    print(f"📌 第1阶段完成")
    print(f"    S级关键词: {s_level.shape[0]:,} 个 → 进入第2阶段选品")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
