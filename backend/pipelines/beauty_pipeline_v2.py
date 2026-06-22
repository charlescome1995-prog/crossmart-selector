# -*- coding: utf-8 -*-
"""
美妆个护选品流水线 v2
直接在ASIN搜索数据中通过商品标题匹配美妆个护产品
"""
import sys, os, json, math, random
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from datetime import datetime

BASE = r"C:\Users\OPENPC\.openclaw\workspace\projects\amazon_ai_kit"
DATA_DIR = os.path.join(BASE, "0_latest_rawdata")
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 美妆个护精准词
# ============================================================
BEAUTY_WORDS = [
    # 美甲
    'nail', 'manicure', 'pedicure', 'cuticle', 'press on nails', 'false nail',
    'nail polish', 'nail art', 'nail file', 'nail clipper', 'nail drill',
    'gel nail', 'acrylic nail', 'nail tip', 'nail glue', 'nail buffer',
    
    # 护发/美发工具
    'hair brush', 'hairbrush', 'hair comb', 'hair dryer', 'hair straightener',
    'curling iron', 'hair curler', 'hair oil', 'hair mask', 'hair towel',
    'hair wrap', 'hair turban', 'hair clip', 'hair tie', 'hair band',
    'hair bonnet', 'dry shampoo', 'shampoo bar', 'conditioner',
    
    # 护肤
    'face moisturizer', 'face serum', 'eye cream', 'face mask', 'sheet mask',
    'sunscreen', 'spf', 'face toner', 'face cleanser', 'face wash',
    'vitamin c serum', 'hyaluronic', 'retinol', 'niacinamide',
    'face roller', 'jade roller', 'gua sha', 'derma roller',
    'face razor', 'face shaver', 'eyebrow razor',
    
    # 彩妆
    'makeup brush', 'makeup bag', 'makeup case', 'cosmetic bag',
    'eyelash', 'eyebrow', 'eyeliner', 'mascara', 'lip balm', 'lip gloss',
    'lip oil', 'foundation', 'concealer', 'blush', 'setting spray',
    'vanity mirror', 'lighted mirror', 'makeup mirror',
    'cushion foundation', 'pressed powder', 'loose powder',
    
    # 美容工具
    'eyebrow trimmer', 'face trimmer', 'nose trimmer',
    'tweezer', 'tweezers', 'magnifying mirror',
    'beauty blender', 'makeup sponge', 'puff',
    'brow kit', 'eyelash curler',
    
    # 身体
    'body wash', 'body lotion', 'body cream', 'body butter',
    'body scrub', 'hand cream', 'foot cream', 'foot file',
    'pumice stone', 'callus remover', 'pedicure tool',
    
    # 口腔
    'toothbrush', 'toothpaste', 'tongue scraper', 'dental floss',
]

EXCLUDE = [
    'baby', 'toy', 'food', 'snack', 'pet', 'dog', 'cat',
    'bluetooth', 'keyboard', 'mouse', 'flashlight', 'flash light',
    'charger', 'cable', 'battery', 'phone case',
    'laptop', 'computer', 'printer', 'toner',
]

# ============================================================
# 辅助
# ============================================================
def calc_fba(price):
    if price <= 0 or pd.isna(price): return 0, 0
    price = float(price)
    cost = price * 0.20
    commission = price * 0.15
    fba = 2.86 if price < 20 else (3.86 if price < 40 else 4.75)
    shipping = 0.3 * 4.0
    ad_cost = price * 0.12
    returns = price * 0.05 * 0.5
    storage = 0.50
    other = price * 0.03
    total = cost + commission + fba + shipping + ad_cost + returns + storage + other
    profit = price - total
    margin = profit / price * 100
    return round(profit, 2), round(margin, 1)

def calc_score(row):
    """ASIN综合评分"""
    price = float(row.get('当前价格', 0) or 0)
    rating = float(row.get('星级评分', 0) or 0)
    reviews = float(row.get('评论数', 0) or 0)
    sellers = float(row.get('卖家数量', 0) or 0)
    bsr = float(row.get('BSR排名', 0) or 0)
    is_ad = str(row.get('是否广告', ''))
    
    score = 0
    
    # 价格 $12-45 最佳区间
    if 15 <= price <= 40: score += 20
    elif 12 <= price < 15: score += 14
    elif 40 < price <= 50: score += 12
    else: score += 5
    
    # 评论少=机会大
    if reviews == 0: score += 20
    elif reviews < 10: score += 18
    elif reviews < 30: score += 15
    elif reviews < 100: score += 10
    elif reviews < 300: score += 6
    elif reviews < 500: score += 3
    
    # 评分正常即可
    if 4.0 <= rating <= 4.6: score += 15
    elif rating > 4.6: score += 10
    elif rating >= 3.5: score += 5
    
    # 卖家少=竞争少
    if sellers <= 2: score += 15
    elif sellers <= 5: score += 10
    elif sellers <= 10: score += 5
    
    # BSR高=有机会冲
    if bsr > 100000: score += 8
    elif bsr > 50000: score += 6
    elif bsr > 10000: score += 4
    elif bsr == 0: score += 5
    
    # 自然位=不用抢广告
    if is_ad != '是': score += 7
    else: score += 3
    
    # FBA利润
    profit, margin = calc_fba(price)
    if margin >= 30: score += 15
    elif margin >= 20: score += 10
    elif margin >= 12: score += 5
    
    return score, profit, margin

# ============================================================
# 模拟
# ============================================================
def simulate(product, scenario_name, ad_start, ad_peak, ad_day, inv):
    price = float(product.get('当前价格', 25) or 25)
    asin_key = str(product.get('ASIN', ''))
    
    total_profit = 0
    successes = 0
    profits = []
    
    for seed in range(100):
        random.seed(seed * 100 + hash(asin_key))
        bsr = random.randint(5000, 50000)
        cumulative = 0
        inventory = inv
        ad = ad_start
        
        for day in range(1, 91):
            if day <= ad_day:
                ad = ad_peak * (1 + (ad_day - day) / ad_day * 0.3)
            else:
                ad = ad_peak * 0.5 * max(0.5, 1 - (day - ad_day) / 60)
            
            base = max(1, int(5000 / math.sqrt(max(1, bsr))))
            boost = 1 + math.log1p(ad / 20) * 0.3
            noise = random.gauss(0, 0.3)
            daily = max(0, int(base * boost * (1 + noise)))
            daily = min(daily, inventory)
            
            revenue = daily * price
            cost = revenue * 0.45 + ad
            cumulative += revenue - cost
            inventory -= daily
            
            if daily > 3:
                bsr = max(100, int(bsr * 0.92))
            else:
                bsr = int(bsr * 1.08)
        
        profits.append(cumulative)
        if cumulative > 0: successes += 1
        total_profit += cumulative
    
    profits.sort()
    mean_p = total_profit / 100
    return {
        '利润均值': round(mean_p, 2),
        '利润下限': round(profits[4], 2),
        '利润上限': round(profits[94], 2),
        '成功率': successes,
    }


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("美妆个护选品流水线 v2")
    print(f"时间: {datetime.now().strftime('%H:%M')}")
    print("=" * 60)
    
    # 1. 加载ASIN数据
    print(f"\n{'='*50}")
    print("【第1步】ASIN数据中识别美妆个护产品")
    print(f"{'='*50}")
    
    df = pd.read_excel(os.path.join(DATA_DIR, "search_全部关键词_4067条_20260331_081906.xlsx"))
    
    for col in ['当前价格', '星级评分', '评论数', 'BSR排名', '卖家数量']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 通过商品标题匹配美妆个护
    title_col = '商品标题'
    title_lower = df[title_col].astype(str).str.lower()
    kw_lower = df['关键词'].astype(str).str.lower()
    
    # 词库匹配（标题或关键词有一个匹配就算）
    beauty_mask = (
        title_lower.str.contains('|'.join(BEAUTY_WORDS), na=False) |
        kw_lower.str.contains('|'.join(BEAUTY_WORDS), na=False)
    )
    # 排除
    exclude_mask = (
        title_lower.str.contains('|'.join(EXCLUDE), na=False) |
        kw_lower.str.contains('|'.join(EXCLUDE), na=False)
    )
    
    beauty = df[beauty_mask & ~exclude_mask].copy()
    
    if len(beauty) == 0:
        print("  ⚠️ 标题匹配无结果，降级为关键词匹配")
        beauty = df[kw_lower.str.contains('|'.join(BEAUTY_WORDS), na=False)].copy()
    
    print(f"  识别美妆个护ASIN: {len(beauty)} 条")
    
    # 统计品类分布
    print(f"\n  品类分布:")
    brand_counts = beauty['品牌'].value_counts().head(15)
    for b, c in brand_counts.items():
        print(f"    {str(b)[:25]:25s} {c}个")
    
    # 2. 评分筛选
    print(f"\n{'='*50}")
    print("【第2步】综合评分")
    print(f"{'='*50}")
    
    scored = []
    for _, row in beauty.iterrows():
        score, profit, margin = calc_score(row)
        scored.append({
            '综合评分': score,
            '关键词': row.get('关键词', ''),
            'ASIN': row.get('ASIN', ''),
            '商品标题': str(row.get('商品标题', ''))[:80],
            '品牌': row.get('品牌', ''),
            '当前价格': float(row.get('当前价格', 0) or 0),
            '星级评分': float(row.get('星级评分', 0) or 0),
            '评论数': int(row.get('评论数', 0) or 0),
            '卖家数量': int(row.get('卖家数量', 0) or 0),
            'BSR排名': int(row.get('BSR排名', 0) or 0),
            '预估利润': profit,
            '毛利率': margin,
            '是否广告': row.get('是否广告', ''),
            '配送类型': row.get('配送类型', ''),
        })
    
    df_score = pd.DataFrame(scored).sort_values('综合评分', ascending=False)
    df_score = df_score.drop_duplicates(subset=['关键词'], keep='first')
    
    # Top 10
    top10 = df_score.head(10)
    
    print(f"\n🏆 美妆个护 Top 10 可上架ASIN")
    print(f"{'='*50}")
    for i, (_, row) in enumerate(top10.iterrows()):
        print(f"\n  #{i+1} [{row['综合评分']}分] {row['关键词'][:30]}")
        print(f"    {row['商品标题'][:70]}")
        print(f"    ${row['当前价格']:.2f} | ★{row['星级评分']:.1f} | {row['评论数']}评论 | {row['卖家数量']}卖家")
        print(f"    利润${row['预估利润']:.2f}/件 | 毛利率{row['毛利率']:.1f}% | BSR {row['BSR排名']}")
    
    # 3. 蒙特卡洛
    print(f"\n{'='*50}")
    print("【第3步】蒙特卡洛运营模拟")
    print(f"{'='*50}")
    
    sim_results = []
    
    for _, product in top10.iterrows():
        kw = str(product['关键词'])[:25]
        title = str(product['商品标题'])[:40]
        price = product['当前价格']
        
        print(f"\n  📦 {kw}")
        print(f"     {title}")
        
        scenarios = [
            ('激进推广', 60, 100, 30, 500),
            ('均衡推广', 40, 70, 45, 300),
            ('稳健推广', 30, 50, 60, 200),
        ]
        
        for name, ad_start, ad_peak, ad_day, inv in scenarios:
            sim = simulate(product, name, ad_start, ad_peak, ad_day, inv)
            print(f"    {name:8s} | 利润:${sim['利润均值']:>7.2f} ${sim['利润下限']:>7.2f}~${sim['利润上限']:>7.2f} | 成功率{sim['成功率']}%")
            sim_results.append({**sim, '产品': kw, '标题': title, '策略': name, '价格': price,
                                '利润率': product['毛利率'], '品牌': str(product['品牌'])[:20]})
    
    # 4. 最终推荐
    print(f"\n{'='*50}")
    print("【第4步】最终上架推荐")
    print(f"{'='*50}")
    
    aggressive = [r for r in sim_results if r['策略'] == '激进推广']
    aggressive.sort(key=lambda x: x['利润均值'], reverse=True)
    
    print(f"\n🏆 美妆个护最佳上品（按激进推广90天利润）")
    print(f"{'='*50}")
    
    for i, r in enumerate(aggressive):
        tag = "🔥" if i < 2 else "  "
        bal = next((s for s in sim_results if s['产品']==r['产品'] and s['策略']=='均衡推广'), None)
        bal_str = f"均衡${bal['利润均值']:.0f}" if bal else ""
        print(f"\n  {tag} #{i+1} {r['产品']}")
        print(f"     品牌:{r['品牌']:15s} 价格:${r['价格']:.2f} 毛利率:{r['利润率']}%")
        print(f"     激进: $ {r['利润均值']:>7.2f} (${r['利润下限']:.0f}~${r['利润上限']:.0f}) 成功率{r['成功率']}%")
        if bal_str:
            print(f"     均衡: {bal_str} 成功率{bal['成功率']}%")
    
    # 保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report = f"""美妆个护选品运营方案 v2
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}

🔍 数据来源:
  ASIN搜索数据: 4,067 条
  识别美妆个护: {len(beauty)} 条
  筛选Top: {len(top10)} 个

🏆 推荐产品 (Top 10):

"""
    for _, row in top10.iterrows():
        report += f"\n  [{row['综合评分']}分] {row['关键词'][:30]}\n"
        report += f"    {row['商品标题'][:70]}\n"
        report += f"    ASIN:{row['ASIN']} 品牌:{str(row['品牌'])[:20]}\n"
        report += f"    ${row['当前价格']:.2f} 毛利率{row['毛利率']:.1f}% 利润${row['预估利润']:.2f}/件\n"
        report += f"    ★{row['星级评分']:.1f} ({row['评论数']}评) 卖家{row['卖家数量']} BSR{row['BSR排名']}\n"
    
    report += f"""
{'='*60}
📊 蒙特卡洛模拟 (90天 × 100次):
"""
    for r in sim_results:
        report += f"\n  {r['产品'][:25]:25s} {r['策略']:8s} 利润${r['利润均值']:>7.2f} [{r['利润下限']:>7.2f}~{r['利润上限']:>7.2f}] 成功率{r['成功率']}%"
    
    report += f"""
{'='*60}
🏆 上架优先级（稳健推荐）:
"""
    for i, r in enumerate(aggressive[:5]):
        bal = next((s for s in sim_results if s['产品']==r['产品'] and s['策略']=='均衡推广'), None)
        profit_r = bal['利润均值'] if bal else r['利润均值']
        rec = "激进推广" if r['利润率'] >= 20 else "均衡推广"
        report += f"\n  #{i+1} {r['产品']} | 品牌:{r['品牌']} | ${r['价格']:.2f} | 毛利率{r['利润率']}%"
        report += f"\n     策略: {rec} | 预期盈利: ${profit_r:.0f} | 成功率{bal['成功率'] if bal else r['成功率']}%"
    
    report += f"""
{'='*60}
行动清单:
  1. 从Top 3选1-2个产品开始操作
  2. 1688找相似供应商打样
  3. 品牌备案(TM标) + UPC码
  4. 准备Listing图文（主图/A+/视频）
  5. 首批300-500件空运
  6. 按3阶段推广（上架→冲排名→稳定盈利）
{'='*60}
    """
    
    report_file = os.path.join(OUTPUT_DIR, f"美妆个护_推荐方案_v2_{ts}.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    # 导出Excel
    excel_file = os.path.join(OUTPUT_DIR, f"美妆个护_Top10_{ts}.xlsx")
    top10.to_excel(excel_file, index=False)
    
    print(f"\n  ✅ 报告: {report_file}")
    print(f"  ✅ 数据: {excel_file}")
    print(f"\n{'='*60}")
    print(f"美妆个护选品 v2 完成 - 程序自动筛选出 {len(top10)} 个推荐产品")

if __name__ == "__main__":
    main()
