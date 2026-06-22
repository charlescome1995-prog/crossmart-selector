# -*- coding: utf-8 -*-
"""
第2阶段：ASIN层 - 关键词+ASIN交叉选品
借鉴卖家精灵「选产品」思路

从S级关键词出发，关联ASIN搜索数据，综合评估可操作产品
输出：可上架的产品清单 + 运营策略建议
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
# 加载数据
# ============================================================
def load_data():
    """加载关键词+ASIN数据"""
    # 关键词竞争力数据（上一阶段输出）
    kw_file = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("关键词竞争力") and f.endswith(".xlsx")]
    if kw_file:
        kw_file = os.path.join(OUTPUT_DIR, sorted(kw_file)[-1])
        print(f"  读取关键词数据: {os.path.basename(kw_file)}")
        df_kw = pd.read_excel(kw_file)
    else:
        # 直接从原始关键词文件
        raw_file = os.path.join(DATA_DIR, "1Amazon关键词_20260322.xlsx")
        df_kw = pd.read_excel(raw_file)
        # 简化评分
        ms = pd.to_numeric(df_kw['20260113月搜'], errors='coerce')
        price = pd.to_numeric(df_kw['价格（美元）'], errors='coerce')
        comp = pd.to_numeric(df_kw['广告竞品数'], errors='coerce')
        df_kw['竞争力评分'] = 50  # placeholder
        df_kw['等级'] = 'B'
    
    # ASIN搜索数据
    asin_file = os.path.join(DATA_DIR, "search_全部关键词_4067条_20260331_081906.xlsx")
    df_asin = pd.read_excel(asin_file)
    
    # 数值化
    for col in ['当前价格', '星级评分', '评论数', 'BSR排名', '卖家数量', '变体数量', '库存剩余']:
        if col in df_asin.columns:
            df_asin[col] = pd.to_numeric(df_asin[col], errors='coerce').fillna(0)
    
    return df_kw, df_asin

# ============================================================
# 产品综合评分
# ============================================================
def score_product(row, kw_score=50):
    """
    产品综合评分 (满分100)
    
    维度：
    - 关键词竞争力 (20分) - 来自第1阶段
    - 产品价格利润 (20分) - FBA利润模型
    - 评论竞争 (15分) - 评论越少机会越大
    - 评分改进空间 (10分) - 4.0-4.5有优化空间
    - 卖家竞争 (10分) - 卖家多=竞争大
    - 配送/变体 (10分) - FBA优先
    - BSR排名 (10分) - 排名好说明已验证
    - 自然排名 (5分) - 非广告产品优先
    """
    score = 0
    details = []
    
    # 0. 关键词竞争力基础分
    score += min(kw_score * 0.2, 20)
    
    price = row.get('当前价格', 0) or 0
    rating = row.get('星级评分', 0) or 0
    reviews = row.get('评论数', 0) or 0
    sellers = row.get('卖家数量', 0) or 0
    bsr = row.get('BSR排名', 0) or 0
    is_ad = str(row.get('是否广告', ''))
    delivery = str(row.get('配送类型', ''))
    variants = row.get('变体数量', 0) or 0
    
    # 1. 价格与利润 (20分)
    if 15 <= price <= 40:
        score += 20
        details.append(f"价格${price:.0f}(优)")
    elif 10 <= price < 15 or 40 < price <= 60:
        score += 13
        details.append(f"价格${price:.0f}(可)")
    elif price > 0:
        score += 6
        details.append(f"价格${price:.0f}(边缘)")
    
    # 2. 评论数 (15分)
    if reviews == 0:
        score += 15
        details.append("0评论")
    elif reviews < 50:
        score += 13
        details.append(f"{int(reviews)}评论(低)")
    elif reviews < 200:
        score += 10
        details.append(f"{int(reviews)}评论(可)")
    elif reviews < 1000:
        score += 6
        details.append(f"{int(reviews)}评论(多)")
    else:
        score += 2
        details.append(f"{int(reviews)}评论(红海)")
    
    # 3. 评分 (10分)
    if 4.0 <= rating <= 4.5:
        score += 10
        details.append(f"★{rating}(可优化)")
    elif rating > 4.5:
        score += 6
        details.append(f"★{rating}(优)")
    elif rating >= 3.5:
        score += 4
        details.append(f"★{rating}(一般)")
    elif rating > 0:
        score += 2
    
    # 4. 卖家数 (10分)
    if sellers == 0:
        score += 5
    elif sellers <= 2:
        score += 10
        details.append(f"卖家{int(sellers)}(少)")
    elif sellers <= 5:
        score += 7
        details.append(f"卖家{int(sellers)}(可)")
    elif sellers <= 10:
        score += 4
    else:
        score += 1
    
    # 5. FBA配送 (10分)
    if 'FBA' in delivery or 'Prime' in delivery:
        score += 10
        details.append("FBA")
    elif '免运费' in delivery or 'Free' in delivery:
        score += 6
    
    # 6. BSR排名 (10分)
    if bsr > 0:
        if bsr <= 5000:
            score += 10
            details.append(f"BSR{int(bsr)}(优)")
        elif bsr <= 20000:
            score += 7
            details.append(f"BSR{int(bsr)}(可)")
        elif bsr <= 50000:
            score += 4
    
    # 7. 自然排名 (5分)
    if is_ad != '是':
        score += 5
    else:
        details.append("广告产品")
    
    # 8. 变体少加分 (5分)
    if 0 < variants <= 3:
        score += 5
    
    # 9. 库存加分 (5分)
    stock = row.get('库存剩余', 0) or 0
    if stock > 0:
        score += 5
    
    # FBA利润估算
    if price > 0:
        margin, profit = calc_fba(price)
    else:
        margin, profit = 0, 0
    
    return int(min(score, 100)), details, margin, profit

def calc_fba(price):
    """FBA利润"""
    cost = price * 0.20
    commission = price * 0.15
    fba = 2.86 if price < 20 else (3.86 if price < 40 else 4.75)
    shipping = 0.3 * 4.0
    ad_cost = price * 0.12
    returns = price * 0.05 * 0.5
    storage = 0.50
    other = price * 0.03
    total = cost + commission + fba + shipping + ad_cost + returns + storage + other
    margin = (price - total) / price * 100
    profit = price - total
    return round(margin, 1), round(profit, 2)

# ============================================================
# 品类风险评估
# ============================================================
RISK_CATEGORIES = {
    'food': '❌ 食品',
    'snack': '❌ 食品',
    'candy': '❌ 食品',
    'supplement': '⚠️ 补充剂(审核)',
    'vitamin': '⚠️ 补充剂(审核)',
    'baby': '⚠️ 母婴(安全)',
    'toy': '⚠️ 玩具(认证)',
}

def check_risk(keyword):
    """检查品类风险"""
    kw_lower = str(keyword).lower()
    for word, risk in RISK_CATEGORIES.items():
        if word in kw_lower:
            return risk
    return '✅ 正常'

# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 70)
    print("【第2阶段】ASIN层 — 关键词+ASIN交叉选品")
    print("                 卖家精灵式选产品引擎")
    print("=" * 70)
    
    # 加载
    print(f"\n[1/4] 加载数据...")
    df_kw, df_asin = load_data()
    print(f"  关键词: {len(df_kw):,} 条")
    print(f"  ASIN数据: {len(df_asin):,} 条")
    
    # 取S/A级关键词
    s_kw = df_kw[df_kw['等级'].isin(['S', 'A'])].copy()
    print(f"\n[2/4] 交叉分析 S/A级关键词 × ASIN数据...")
    print(f"  S/A级关键词: {len(s_kw):,} 个")
    
    # 取关键词名
    kw_col = '关键词(绿色建议进入，黄色找切入点，粉色观察)'
    top_keywords = s_kw[kw_col].dropna().unique()[:200]  # 取前200个S/A关键词
    
    # 从ASIN数据中匹配这些关键词
    matched = df_asin[df_asin['关键词'].isin(top_keywords)].copy()
    print(f"  匹配到ASIN: {len(matched):,} 条")
    
    if len(matched) == 0:
        print("  ⚠️ 关键词不匹配，回退到全量ASIN评分")
        matched = df_asin.copy()
    
    # 评分
    print(f"\n[3/4] 产品综合评分...")
    kw_score_map = dict(zip(s_kw[kw_col], s_kw['竞争力评分']))
    
    results = []
    for _, row in matched.iterrows():
        kw = row.get('关键词', '')
        kw_score = kw_score_map.get(kw, 50)
        score, details, margin, profit = score_product(row, kw_score)
        
        results.append({
            '综合评分': score,
            '关键词': kw,
            'ASIN': row.get('ASIN', ''),
            '商品标题': str(row.get('商品标题', ''))[:80],
            '品牌': row.get('品牌', ''),
            '当前价格': row.get('当前价格', 0),
            '星级评分': row.get('星级评分', 0),
            '评论数': row.get('评论数', 0),
            'BSR排名': row.get('BSR排名', 0),
            '卖家数量': row.get('卖家数量', 0),
            '配送类型': row.get('配送类型', ''),
            '是否广告': row.get('是否广告', ''),
            '变体数量': row.get('变体数量', 0),
            '毛利率': margin,
            '预估利润': profit,
            '评分细节': '; '.join(details[:5]),
            '品类风险': check_risk(kw),
            '关键词竞争力': kw_score,
        })
    
    df_result = pd.DataFrame(results).sort_values('综合评分', ascending=False)
    
    # 按关键词去重保留最佳
    df_result = df_result.drop_duplicates(subset=['关键词'], keep='first')
    
    print(f"  评分完成: {len(df_result)} 个产品")
    
    # 统计
    for label, lo, hi in [('S级 强烈推荐', 80, 200), ('A级 推荐', 65, 80), ('B级 可考虑', 50, 65), ('C级 谨慎', 0, 50)]:
        c = ((df_result['综合评分'] >= lo) & (df_result['综合评分'] < hi)).sum()
        if c > 0:
            avg_p = df_result[(df_result['综合评分'] >= lo) & (df_result['综合评分'] < hi)]['预估利润'].mean()
            print(f"  {label}: {c} 个 (平均利润 ${avg_p:.2f})")
    
    # Top 20
    print(f"\n{'='*70}")
    print("🏆 Top 20 精选可上架产品")
    print(f"{'='*70}")
    
    top = df_result.head(20)
    for i, (_, row) in enumerate(top.iterrows()):
        kw = str(row['关键词'])[:30]
        title = str(row['商品标题'])[:40]
        risk = row['品类风险']
        print(f"\n{i+1:2d}. [{row['综合评分']}分] {risk} {kw}")
        print(f"    {title}")
        print(f"    ${row['当前价格']:.2f} | ★{row['星级评分']:.1f} | {int(row['评论数']):,}评论 | BSR:{int(row['BSR排名']):,}")
        print(f"    毛利:{row['毛利率']:.1f}% | 利润:${row['预估利润']:.2f} | 卖家:{int(row['卖家数量'])} | {row['配送类型'][:10]}")
        print(f"    {row['评分细节'][:60]}")
    
    # 保存
    print(f"\n[4/4] 保存结果...")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    out_cols = ['综合评分', '关键词', 'ASIN', '商品标题', '品牌', '当前价格',
                '星级评分', '评论数', 'BSR排名', '卖家数量', '毛利率', '预估利润',
                '配送类型', '是否广告', '变体数量', '评分细节', '品类风险', '关键词竞争力']
    
    out_file = os.path.join(OUTPUT_DIR, f"精选上架产品_{len(df_result)}条_{ts}.xlsx")
    from openpyxl.styles import Font
    with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
        df_result[out_cols].to_excel(writer, index=False, sheet_name='精选上架')
        ws = writer.sheets['精选上架']
        ws.freeze_panes = 'A2'
        for c in ws[1]: c.font = Font(name='Times New Roman', size=11, bold=True)
        for ro in ws.iter_rows(min_row=2):
            for c in ro: c.font = Font(name='Times New Roman', size=10)
    
    print(f"  ✅ {out_file}")
    
    # 按品类风险评估
    print(f"\n{'='*70}")
    print("⚠️ 品类风险评估")
    print(f"{'='*70}")
    risk_counts = df_result['品类风险'].value_counts()
    for r, c in risk_counts.items():
        print(f"  {r}: {c} 个")
    
    print(f"\n{'='*70}")
    print("📌 第2阶段完成 → 进入第3阶段：运营模拟+上架方案")
    print(f"   可重点关注: 低风险+高评分的前10个产品")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
