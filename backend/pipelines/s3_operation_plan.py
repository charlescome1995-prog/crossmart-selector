# -*- coding: utf-8 -*-
"""
第3阶段：运营模拟 + 上架方案
借鉴卖家精灵「销量预测+Listing优化」思路

对精选产品做:
1. 90天运营模拟（蒙特卡洛）
2. 完整上架方案（定价/广告/库存/策略）
3. 竞品策略推演
"""

import sys, os, json, random, math
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 蒙特卡洛运营模拟
# ============================================================
class ProductSimulator:
    """单个产品的90天运营模拟"""
    
    SCENARIOS = {
        'aggressive': {
            'name': '激进推广',
            'ad_start': 60,      # 每日广告费起步
            'ad_peak': 100,      # 广告高峰期
            'ad_day': 30,        # 高峰日
            'discount_max': 0.25, # 最大折扣
            'inventory_first': 500,
        },
        'balanced': {
            'name': '均衡推广',
            'ad_start': 40,
            'ad_peak': 70,
            'ad_day': 45,
            'discount_max': 0.15,
            'inventory_first': 300,
        },
        'steady': {
            'name': '稳健推广',
            'ad_start': 30,
            'ad_peak': 50,
            'ad_day': 60,
            'discount_max': 0.10,
            'inventory_first': 200,
        }
    }
    
    def __init__(self, product, scenario='balanced'):
        self.product = product
        self.scenario_key = scenario
        self.config = self.SCENARIOS[scenario]
        
    def simulate(self, days=90, iterations=100):
        """蒙特卡洛模拟"""
        results = []
        
        for seed in range(iterations):
            random.seed(seed * 1000 + hash(str(self.product.get('ASIN', ''))))
            
            state = self._init_state()
            daily_records = []
            
            for day in range(1, days + 1):
                self._update_daily(state, day)
                daily_records.append(dict(state))
            
            final_profit = state['cumulative_profit']
            results.append({
                'total_sales': state['cumulative_sales'],
                'total_revenue': state['cumulative_revenue'],
                'total_profit': final_profit,
                'final_bsr': state['bsr'],
                'final_inventory': state['inventory'],
                'success': final_profit > 0,
                'roi': (final_profit / max(state['cumulative_cost'], 1)) * 100 if state['cumulative_cost'] > 0 else 0,
            })
        
        # 统计分析
        profits = [r['total_profit'] for r in results]
        sales = [r['total_sales'] for r in results]
        
        stats = {
            'scenario': self.config['name'],
            'iterations': iterations,
            'profit_mean': round(sum(profits)/len(profits), 2),
            'profit_min': round(min(profits), 2),
            'profit_max': round(max(profits), 2),
            'profit_std': round(self._std(profits), 2),
            'profit_p5': round(self._percentile(profits, 5), 2),
            'profit_p95': round(self._percentile(profits, 95), 2),
            'sales_mean': round(sum(sales)/len(sales), 0),
            'success_rate': round(sum(1 for r in results if r['success'])/len(results)*100, 1),
            'roi_mean': round(sum(r['roi'] for r in results)/len(results), 1),
        }
        
        return stats
    
    def _init_state(self):
        price = self.product.get('当前价格', 25) or 25
        return {
            'day': 1, 'price': price,
            'bsr': random.randint(5000, 50000),
            'daily_sales': 0,
            'revenue': 0,
            'cost': 0,
            'profit': 0,
            'inventory': self.config['inventory_first'],
            'ad_spend': self.config['ad_start'],
            'cumulative_sales': 0,
            'cumulative_revenue': 0,
            'cumulative_cost': 0,
            'cumulative_profit': 0,
            'reviews': 0,
            'rating': 0,
        }
    
    def _update_daily(self, state, day):
        """更新每日状态"""
        price = state['price']
        
        # 广告策略按天变化
        if day <= self.config['ad_day']:
            ad_factor = 1 + (self.config['ad_day'] - day) / self.config['ad_day'] * 0.5
            state['ad_spend'] = self.config['ad_peak'] * ad_factor
        else:
            decay = max(0.5, 1 - (day - self.config['ad_day']) / 60)
            state['ad_spend'] = self.config['ad_peak'] * 0.5 * decay
        
        # 计算日销量
        base_sales = max(1, int(5000 / math.sqrt(max(1, state['bsr']))))
        ad_boost = 1 + math.log1p(state['ad_spend'] / 20) * 0.3
        review_boost = 1 + min(state['reviews'] / 50, 0.3)
        noise = random.gauss(0, 0.2)
        
        daily_sales = max(0, int(base_sales * ad_boost * review_boost * (1 + noise)))
        daily_sales = min(daily_sales, state['inventory'])
        
        # 价格折扣
        if day <= 15:
            daily_sales = int(daily_sales * 1.3)  # 新品促销
        
        # 财务
        revenue = daily_sales * price
        margin_factor = 0.55  # 扣除FBA+采购+广告后毛利约55%
        cost = revenue * (1 - margin_factor) + state['ad_spend']
        profit = revenue - cost
        
        state['daily_sales'] = daily_sales
        state['revenue'] = revenue
        state['cost'] = cost
        state['profit'] = profit
        state['cumulative_sales'] += daily_sales
        state['cumulative_revenue'] += revenue
        state['cumulative_cost'] += cost
        state['cumulative_profit'] += profit
        state['inventory'] -= daily_sales
        
        # BSR动态
        if daily_sales > 3:
            state['bsr'] = max(100, int(state['bsr'] * 0.92))
        else:
            state['bsr'] = int(state['bsr'] * 1.08)
        
        # 评论积累
        if daily_sales > 0 and random.random() < 0.03:
            state['reviews'] += 1
            if random.random() < 0.7:
                state['rating'] = min(5.0, state['rating'] + 0.02)
    
    def _std(self, values):
        m = sum(values)/len(values)
        return math.sqrt(sum((x-m)**2 for x in values)/len(values))
    
    def _percentile(self, values, p):
        s = sorted(values)
        i = int(len(s) * p / 100)
        return s[min(i, len(s)-1)]

# ============================================================
# 上架方案生成
# ============================================================
def generate_launch_plan(product, scenario='balanced'):
    """生成完整上架方案"""
    price = product.get('当前价格', 25) or 25
    margin, profit = calc_fba(price)
    kw = str(product.get('关键词', ''))
    title = str(product.get('商品标题', ''))[:60]
    asin = str(product.get('ASIN', ''))
    
    # 价格策略
    launch_price = round(price * 0.85, 2)   # 上架价85%
    normal_price = price                     # 正常价
    target_price = round(price * 0.95, 2)    # 稳定期价
    
    # 广告策略
    ad_budget_day1_30 = 50
    ad_budget_day31_60 = 35
    ad_budget_day61_90 = 25
    
    # 库存计划
    first_ship = 300 if scenario == 'steady' else 500
    
    return {
        '产品': kw,
        '对标ASIN': asin,
        '对标产品': title,
        
        '💰 定价方案': {
            '上架价格': f"${launch_price} (建议85%低价冲排名)",
            '恢复价格': f"${normal_price}",
            'Coupon策略': "$2-3 Coupon持续30天",
        },
        
        '📦 库存计划': {
            '首批备货': f"{first_ship}件 (空运, 7-10天到货)",
            '补货触发': "库存<100件时补货, 海运(25天)",
            '小包数量': "150-200件/次 (海运降低成本)",
        },
        
        '📢 广告策略': {
            '第1-30天': f"日预算${ad_budget_day1_30}, 自动广告+精准匹配, 出价建议=竞价的120%",
            '第31-60天': f"日预算${ad_budget_day31_60}, 精准关键词+商品定位广告",
            '第61-90天': f"日预算${ad_budget_day61_90}, 优化低ACOS词, 追加SB广告",
            '建议ACOS': "初期<50%, 稳定期<30%",
        },
        
        '🎯 核心关键词': extract_keywords(kw),
        
        '📊 预期目标': {
            '第1月': "日销3-5单, BSR进入Top 50000",
            '第2月': "日销8-12单, BSR进入Top 20000",
            '第3月': "日销15-25单, BSR进入Top 10000",
        },
        
        '⚠️ 风险提示': [
            "同类产品可能跟进降价",
            "广告竞价可能上涨",
            "差评可能导致BSR骤降",
            "供应链中断风险"
        ]
    }

def calc_fba(price):
    cost = price * 0.20
    commission = price * 0.15
    fba = 2.86 if price < 20 else (3.86 if price < 40 else 4.75)
    shipping = 0.3 * 4.0
    ad_cost = price * 0.12
    returns = price * 0.05 * 0.5
    storage = 0.50
    other = price * 0.03
    total = cost + commission + fba + shipping + ad_cost + returns + storage + other
    return round((price-total)/price*100,1), round(price-total,2)

def extract_keywords(kw):
    """从关键词提取核心词"""
    words = str(kw).lower().split()
    if len(words) <= 3:
        return [kw]
    # 取2-3词组合
    result = []
    for i in range(len(words)-1):
        result.append(' '.join(words[i:i+2]))
    return result[:5]

# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 70)
    print("【第3阶段】运营模拟 + 上架方案")
    print("                 卖家精灵式运营推演引擎")
    print("=" * 70)
    
    # 加载第2阶段结果
    selection_file = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("精选上架产品") and f.endswith(".xlsx")]
    if not selection_file:
        print("❌ 未找到第2阶段输出，请先运行 s2_asin_layer.py")
        return
    
    df = pd.read_excel(os.path.join(OUTPUT_DIR, sorted(selection_file)[-1]))
    print(f"\n[1/3] 加载精选产品: {len(df)} 个")
    
    # 取Top 5做模拟
    top5 = df.head(5)
    
    print(f"\n[2/3] 运行蒙特卡洛模拟 (3种策略 × 5个产品 × 100次迭代)...")
    all_sims = []
    
    for _, product in top5.iterrows():
        prod_dict = dict(product)
        kw = str(prod_dict.get('关键词', ''))
        price = prod_dict.get('当前价格', 0)
        
        print(f"\n  📦 {kw[:30]} (${price})")
        
        for sce in ['aggressive', 'balanced', 'steady']:
            sim = ProductSimulator(prod_dict, sce)
            stats = sim.simulate(days=90, iterations=100)
            all_sims.append({**stats, 'product': kw[:30], 'price': price})
            
            profit_range = f"${stats['profit_p5']}~${stats['profit_p95']}"
            print(f"    {stats['scenario']:8s} | 利润均值:${stats['profit_mean']:>7.2f} | 范围:{profit_range:>15s} | "
                  f"成功率:{stats['success_rate']:>5.1f}% | ROI:{stats['roi_mean']:>5.1f}%")
    
    # 生成上架方案
    print(f"\n[3/3] 生成上架方案...")
    
    report_path = os.path.join(OUTPUT_DIR, "运营方案_完整报告.txt")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("Amazon 运营上架方案 - 完整报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 70 + "\n\n")
        
        for _, product in top5.iterrows():
            plan = generate_launch_plan(dict(product), 'balanced')
            kw = plan['产品']
            
            f.write(f"{'='*70}\n")
            f.write(f"📦 {kw}\n")
            f.write(f"对标: {plan['对标ASIN']} - {plan['对标产品']}\n")
            f.write(f"{'='*70}\n\n")
            
            f.write("💰 定价方案:\n")
            for k, v in plan['💰 定价方案'].items():
                f.write(f"  {k}: {v}\n")
            
            f.write("\n📦 库存计划:\n")
            for k, v in plan['📦 库存计划'].items():
                f.write(f"  {k}: {v}\n")
            
            f.write("\n📢 广告策略:\n")
            for k, v in plan['📢 广告策略'].items():
                f.write(f"  {k}: {v}\n")
            
            f.write(f"\n🎯 核心关键词: {', '.join(plan['🎯 核心关键词'][:5])}\n")
            
            f.write("\n📊 预期目标:\n")
            for k, v in plan['📊 预期目标'].items():
                f.write(f"  {k}: {v}\n")
            
            f.write("\n⚠️ 风险提示:\n")
            for r in plan['⚠️ 风险提示']:
                f.write(f"  • {r}\n")
            
            f.write("\n\n")
        
        # 模拟结果汇总
        f.write("\n" + "=" * 70 + "\n")
        f.write("📊 蒙特卡洛模拟汇总\n")
        f.write("=" * 70 + "\n\n")
        
        # 表格
        f.write(f"{'产品':25s} {'策略':10s} {'利润均值':>10s} {'利润下限':>10s} {'利润上限':>10s} "
                f"{'成功率':>8s} {'ROI':>8s}\n")
        f.write("-" * 80 + "\n")
        for sim in all_sims:
            f.write(f"{sim['product']:25s} {sim['scenario']:10s} "
                    f"${sim['profit_mean']:>7.2f} ${sim['profit_p5']:>7.2f} ${sim['profit_p95']:>7.2f} "
                    f"{sim['success_rate']:>7.1f}% {sim['roi_mean']:>7.1f}%\n")
        
        f.write("\n\n📌 最终推荐:\n")
        f.write("  1. 优先选择: 成功率>60% 且 利润均值>0 的产品\n")
        f.write("  2. 推荐策略: 激进→均衡→稳健 分阶段切换\n")
        f.write("  3. 关键指标: 前30天日销目标直接影响最终结果\n")
        f.write("  4. 止损线: 30天累计亏损超过预算50%则考虑调整策略\n")
    
    print(f"\n  ✅ 运营报告: {report_path}")
    
    # 控制台输出汇总
    print(f"\n{'='*70}")
    print("📊 推荐上架优先级")
    print(f"{'='*70}")
    
    sim_summary = {}
    for sim in all_sims:
        p = sim['product']
        if p not in sim_summary:
            sim_summary[p] = {}
        sim_summary[p][sim['scenario']] = sim
    
    for i, (prod, scenarios) in enumerate(sim_summary.items()):
        # 取balance策略作为基准
        bal = scenarios.get('balanced', scenarios.get(list(scenarios.keys())[0], {}))
        print(f"\n{i+1:2d}. {prod}")
        print(f"    均衡策略: 利润${bal['profit_mean']:.2f} (${bal['profit_p5']:.0f}~${bal['profit_p95']:.0f}) | "
              f"成功率{bal['success_rate']:.0f}% | ROI {bal['roi_mean']:.0f}%")
    
    print(f"\n{'='*70}")
    print("📌 第3阶段完成！")
    print(f"   完整运营方案 → {report_path}")
    print(f"   数据文件 → {OUTPUT_DIR}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
