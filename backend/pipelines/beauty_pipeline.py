# -*- coding: utf-8 -*-
"""
美妆个护专用选品流水线
自动完成：关键词筛选 → ASIN交叉 → 评分 → 模拟 → 推荐
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
# 美妆个护精准词库
# ============================================================
BEAUTY_KEYWORDS = [
    # 美甲
    'nail', 'press on nails', 'nail polish', 'nail file', 'nail clipper',
    'nail art', 'nail drill', 'nail tips', 'nail glue', 'nail buffer',
    'gel nails', 'acrylic nails', 'false nails', 'fake nails',
    'manicure', 'pedicure', 'cuticle',
    
    # 护肤
    'skincare', 'skin care', 'serum', 'moisturizer', 'sunscreen', 'spf',
    'face mask', 'eye cream', 'toner', 'cleanser', 'exfoliant',
    'retinol', 'vitamin c serum', 'hyaluronic', 'niacinamide',
    'collagen', 'face roller', 'jade roller', 'gua sha',
    'facial roller', 'beauty roller', 'face tool',
    
    # 彩妆
    'makeup', 'foundation', 'concealer', 'blush', 'highlight',
    'setting spray', 'brush set', 'makeup brush', 'makeup bag',
    'makeup case', 'cosmetic bag', 'vanity mirror', 'makeup mirror',
    'cushion foundation', 'lip balm', 'lip gloss', 'lip oil',
    'eyelash', 'eyebrow', 'brow', 'lash', 'mascara', 'eyeliner',
    
    # 护发
    'hairbrush', 'hair brush', 'comb', 'shampoo', 'conditioner',
    'hair mask', 'hair oil', 'hair growth', 'hair curler',
    'hair straightener', 'hair dryer', 'hair towel', 'hair wrap',
    'hair turban', 'hair clip', 'hair ties', 'hair accessories',
    
    # 身体护理
    'body wash', 'body lotion', 'body butter', 'body scrub',
    'deodorant', 'hand cream', 'foot cream', 'foot file',
    'pumice stone', 'callus remover',
    
    # 美容工具
    'face razor', 'eyebrow trimmer', 'facial hair removal',
    'tweezer', 'magnifying mirror', 'lighted mirror',
    'beauty blender', 'makeup sponge', 'brush cleaner',
]

# 排除词（避免非美妆产品混入）
EXCLUDE_KEYWORDS = [
    'baby', 'toy', 'food', 'snack', 'pet', 'dog', 'cat', 'book',
    'bluetooth', 'keyboard', 'mouse', 'flashlight', 'flash light',
    'charger', 'cable', 'battery', 'phone case', 'screen protector',
]

# ============================================================
# 第1步：关键词筛选
# ============================================================
def step1_keywords():
    print(f"\n{'='*50}")
    print("【第1步】美妆个护关键词筛选")
    print(f"{'='*50}")
    
    df = pd.read_excel(os.path.join(OUTPUT_DIR, "关键词竞争力_34447条_20260511_094404.xlsx"))
    kw_col = '关键词(绿色建议进入，黄色找切入点，粉色观察)'
    kw_lower = df[kw_col].astype(str).str.lower()
    
    # 美妆匹配
    beauty_mask = kw_lower.str.contains('|'.join(BEAUTY_KEYWORDS), na=False)
    # 排除误入
    exclude_mask = kw_lower.str.contains('|'.join(EXCLUDE_KEYWORDS), na=False)
    
    beauty = df[beauty_mask & ~exclude_mask].copy()
    print(f"  原始美妆个护关键词: {beauty_mask.sum()}")
    print(f"  排除后: {len(beauty)}")
    
    # 仅保留S/A级
    beauty = beauty[beauty['等级'].isin(['S', 'A'])].sort_values('竞争力评分', ascending=False)
    
    # 更严格：竞品<200, 竞价<$2, 需供比>3
    beauty = beauty[
        (beauty['广告竞品数'] < 200) &
        (beauty['PCP竞价（美元）'] < 2.0) &
        (beauty['需供比'] > 3)
    ].head(30)
    
    print(f"  严格筛选后: {len(beauty)} 个")
    
    for _, row in beauty.iterrows():
        kw = str(row[kw_col])[:35]
        print(f"    [{row['竞争力评分']}分] {kw:35s} 月搜{int(row['20260113月搜']):,} 竞品{int(row['广告竞品数'])}")
    
    return beauty

# ============================================================
# 第2步：ASIN交叉
# ============================================================
def step2_asin_cross(beauty_kws):
    print(f"\n{'='*50}")
    print("【第2步】ASIN搜索数据交叉验证")
    print(f"{'='*50}")
    
    df_asin = pd.read_excel(os.path.join(DATA_DIR, "search_全部关键词_4067条_20260331_081906.xlsx"))
    
    for col in ['当前价格', '星级评分', '评论数', 'BSR排名', '卖家数量']:
        if col in df_asin.columns:
            df_asin[col] = pd.to_numeric(df_asin[col], errors='coerce').fillna(0)
    
    kw_col = '关键词(绿色建议进入，黄色找切入点，粉色观察)'
    top_kws = beauty_kws[kw_col].dropna().unique()[:50]
    
    matched = df_asin[df_asin['关键词'].isin(top_kws)].copy()
    print(f"  匹配ASIN: {len(matched)} 条")
    
    # 严格过滤：价格$10-50, 有评分, 评论<500
    matched = matched[
        (matched['当前价格'] >= 10) & (matched['当前价格'] <= 50) &
        (matched['星级评分'] > 0) &
        (matched['评论数'] <= 500)
    ]
    print(f"  过滤后: {len(matched)} 条")
    
    if len(matched) == 0:
        print("  ⚠️ 无匹配ASIN，回退直接使用关键词数据（构建虚拟产品）")
        # 从关键词数据构建模拟产品
        fallback = []
        for _, row in beauty_kws.head(10).iterrows():
            price = row['价格（美元）']
            profit, margin = calc_fba(price)
            fallback.append({
                '综合评分': row['竞争力评分'],
                '关键词': row['关键词(绿色建议进入，黄色找切入点，粉色观察)'],
                'ASIN': '',
                '商品标题': row['关键词(绿色建议进入，黄色找切入点，粉色观察)'],
                '品牌': '',
                '当前价格': price,
                '星级评分': row['评分值'],
                '评论数': row['评分数'],
                '卖家数量': 5,
                '毛利率': margin,
                '预估利润': profit,
                '是否广告': '否',
                '配送类型': 'FBA',
            })
        return pd.DataFrame(fallback)
    
    # 综合评分
    results = []
    for _, row in matched.iterrows():
        price = row['当前价格']
        rating = row['星级评分']
        reviews = row['评论数']
        sellers = row['卖家数量']
        kw = str(row.get('关键词', ''))
        
        score = 0
        
        # 价格
        if 15 <= price <= 40: score += 20
        elif 10 <= price < 15: score += 12
        else: score += 6
        
        # 评论少=机会
        if reviews == 0: score += 20
        elif reviews < 20: score += 17
        elif reviews < 100: score += 13
        elif reviews < 300: score += 8
        else: score += 4
        
        # 评分
        if 4.0 <= rating <= 4.5: score += 15
        elif rating > 4.5: score += 10
        elif rating >= 3.5: score += 6
        else: score += 2
        
        # 卖家少
        if sellers == 0: score += 8
        elif sellers <= 2: score += 15
        elif sellers <= 5: score += 10
        elif sellers <= 10: score += 5
        
        # FBA利润
        profit, margin = calc_fba(price)
        if margin >= 25: score += 15
        elif margin >= 15: score += 10
        else: score += 4
        
        # 自然排名
        is_ad = str(row.get('是否广告', ''))
        if is_ad != '是': score += 7
        
        results.append({
            '综合评分': score,
            '关键词': kw,
            'ASIN': row.get('ASIN', ''),
            '商品标题': str(row.get('商品标题', ''))[:70],
            '品牌': row.get('品牌', ''),
            '当前价格': price,
            '星级评分': rating,
            '评论数': reviews,
            '卖家数量': sellers,
            '毛利率': margin,
            '预估利润': profit,
            '是否广告': is_ad,
            '配送类型': row.get('配送类型', ''),
        })
    
    df_result = pd.DataFrame(results).sort_values('综合评分', ascending=False)
    df_result = df_result.drop_duplicates(subset=['关键词'], keep='first').head(10)
    
    print(f"  最终推荐: {len(df_result)} 个")
    for i, (_, row) in enumerate(df_result.iterrows()):
        print(f"\n    #{i+1} [{row['综合评分']}分] {row['关键词'][:30]}")
        print(f"    {row['商品标题'][:50]}")
        print(f"    ${row['当前价格']:.2f} | ★{row['星级评分']:.1f} | {int(row['评论数'])}评论 | 毛利{row['毛利率']:.1f}% | 利润${row['预估利润']:.2f}")
    
    return df_result

# ============================================================
# 第3步：蒙特卡洛模拟
# ============================================================
def step3_simulation(df_products):
    print(f"\n{'='*50}")
    print("【第3步】蒙特卡洛运营模拟")
    print(f"{'='*50}")
    
    if df_products is None or len(df_products) == 0:
        print("  无产品可模拟")
        return None
    
    scenarios = [
        ('激进推广', 60, 100, 30, 0.25, 500),
        ('均衡推广', 40, 70, 45, 0.15, 300),
        ('稳健推广', 30, 50, 60, 0.10, 200),
    ]
    
    results = []
    
    for _, product in df_products.head(5).iterrows():
        price = product.get('当前价格', 25) or 25
        kw = str(product.get('关键词', ''))[:25]
        title = str(product.get('商品标题', ''))[:40]
        
        print(f"\n  📦 {kw}")
        
        for name, ad_start, ad_peak, ad_day, disc_max, inv in scenarios:
            total = 0
            success = 0
            profits = []
            
            for seed in range(100):
                random.seed(seed * 100 + hash(str(product.get('ASIN', ''))))
                bsr = random.randint(5000, 50000)
                cumulative = 0
                cumulative_cost = 0
                inventory = inv
                ad = ad_start
                
                for day in range(1, 91):
                    if day <= ad_day:
                        ad = ad_peak * (1 + (ad_day - day) / ad_day * 0.3)
                    else:
                        ad = ad_peak * 0.5 * max(0.5, 1 - (day - ad_day) / 60)
                    
                    base = max(1, int(5000 / math.sqrt(max(1, bsr))))
                    boost = 1 + math.log1p(ad / 20) * 0.3
                    noise = random.gauss(0, 0.25)
                    daily = max(0, int(base * boost * (1 + noise)))
                    daily = min(daily, inventory)
                    
                    revenue = daily * price
                    cost = revenue * 0.45 + ad
                    profit_today = revenue - cost
                    
                    cumulative += profit_today
                    cumulative_cost += cost
                    inventory -= daily
                    
                    if daily > 3:
                        bsr = max(100, int(bsr * 0.92))
                    else:
                        bsr = int(bsr * 1.08)
                
                profits.append(cumulative)
                if cumulative > 0:
                    success += 1
            
            mean_p = sum(profits) / 100
            profits.sort()
            p5 = profits[4]
            p95 = profits[94]
            roi = (mean_p / cumulative_cost * 100) if cumulative_cost > 0 else 0
            total += mean_p
            
            print(f"    {name:8s} | 利润:${mean_p:>7.2f} (${p5:.0f}~${p95:.0f}) | 成功:{success}% | ROI:{roi:.0f}%")
            
            results.append({
                '产品': kw,
                '标题': title,
                '策略': name,
                '利润均值': round(mean_p, 2),
                '利润下限': round(p5, 2),
                '利润上限': round(p95, 2),
                '成功率': success,
                'ROI': round(roi, 1),
            })
    
    return results

# ============================================================
# 第4步：最终推荐
# ============================================================
def step4_recommend(sim_results, df_products):
    print(f"\n{'='*50}")
    print("【第4步】最终上架推荐")
    print(f"{'='*50}")
    
    if not sim_results:
        print("  无模拟数据")
        return
    
    # 按激进策略利润排序
    aggressive = [r for r in sim_results if r['策略'] == '激进推广']
    aggressive.sort(key=lambda x: x['利润均值'], reverse=True)
    
    print(f"\n🏆 美妆个护 - 最佳上品推荐（按激进策略利润排序）")
    print(f"{'='*50}")
    
    for i, r in enumerate(aggressive):
        tag = "🔥" if i < 2 else ""
        print(f"\n  {tag} #{i+1} {r['产品']}")
        print(f"    {r['标题'][:55]}")
        print(f"    激进: $ {r['利润均值']:>7.2f} (${r['利润下限']:.0f}~${r['利润上限']:.0f}) | 成功率{r['成功率']}% | ROI{r['ROI']}%")
        
        # 找对应均衡策略
        bal = [s for s in sim_results if s['产品'] == r['产品'] and s['策略'] == '均衡推广']
        if bal:
            b = bal[0]
            print(f"    均衡: $ {b['利润均值']:>7.2f} | 成功率{b['成功率']}% | ROI{b['ROI']}%")
    
    # 保存完整报告
    print(f"\n  生成完整报告...")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    report = f"""美妆个护选品运营方案
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}

🔍 数据来源:
  关键词库: 34,447 个
  美妆个护关键词: 82 个 (S级)
  ASIN搜索数据: 4,067 条

📊 蒙特卡洛模拟 (90天 × 100次):

"""
    for r in sim_results:
        report += f"  {r['产品'][:25]:25s} | {r['策略']:8s} | 利润${r['利润均值']:>7.2f} | ${r['利润下限']:>7.2f}~${r['利润上限']:>7.2f} | 成功率{r['成功率']}% | ROI{r['ROI']:.0f}%\n"
    
    report += f"""
{'='*60}
🏆 上架优先级:
"""
    for i, r in enumerate(aggressive):
        report += f"\n  #{i+1} {r['产品']}\n"
        report += f"    标题: {r['标题']}\n"
        report += f"    90天激进利润: ${r['利润均值']:.2f} (成功率{r['成功率']}%)\n"
        report += f"    建议策略: {'激进推广(广告预算$60/天)' if i < 2 else '均衡推广($40/天)'}\n"
    
    report += f"""
{'='*60}
行动清单:
  1. 从推荐中选择1个产品开始
  2. 1688找供应商打样
  3. 品牌备案(TM标) + UPC码
  4. 准备Listing图文
  5. 首批备货+空运
  6. 按90天计划推品
{'='*60}
"""
    
    report_file = os.path.join(OUTPUT_DIR, f"美妆个护_推荐方案_{ts}.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"  ✅ 已保存: {report_file}")
    print(report)

# ============================================================
# 辅助
# ============================================================
def calc_fba(price):
    if price <= 0: return 0, 0
    cost = price * 0.20
    commission = price * 0.15
    fba = 2.86 if price < 20 else (3.86 if price < 40 else 4.75)
    shipping = 0.3 * 4.0
    ad = price * 0.12
    returns = price * 0.05 * 0.5
    storage = 0.50
    other = price * 0.03
    total = cost + commission + fba + shipping + ad + returns + storage + other
    profit = price - total
    margin = profit / price * 100
    return round(profit, 2), round(margin, 1)

# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("美妆个护选品流水线")
    print(f"时间: {datetime.now().strftime('%H:%M')}")
    print("=" * 60)
    
    kw = step1_keywords()
    products = step2_asin_cross(kw)
    sims = step3_simulation(products)
    step4_recommend(sims, products)
    
    print(f"\n{'='*60}")
    print("✅ 美妆个护选品完成")

if __name__ == "__main__":
    main()
