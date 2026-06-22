# -*- coding: utf-8 -*-
"""
第4阶段：最终推荐 - 可执行的上品推进方案
基于3阶段数据，输出最终的可执行决策方案
"""

import sys, os, json, random, math
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE, "output")
DATA_DIR = os.path.join(BASE, "0_latest_rawdata")

def get_fba_cost(price):
    """FBA费用+成本"""
    product_cost = price * 0.20
    commission = price * 0.15
    fba = 2.86 if price < 20 else (3.86 if price < 40 else 4.75)
    shipping = 0.3 * 4.0
    ad_ratio = 0.12
    ad_cost = price * ad_ratio
    returns = price * 0.05 * 0.5
    storage = 0.50
    other = price * 0.03
    total = product_cost + commission + fba + shipping + ad_cost + returns + storage + other
    profit = price - total
    margin = profit / price * 100
    return round(profit, 2), round(margin, 1)

def generate_business_plan():
    """生成最终商业计划"""
    
    print("=" * 70)
    print("Amazon 选品运营 - 最终推荐方案")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # 读取已有数据
    selection_file = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("精选上架产品") and f.endswith(".xlsx")]
    kw_file = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("关键词竞争力") and f.endswith(".xlsx")]
    
    df_selection = pd.read_excel(os.path.join(OUTPUT_DIR, sorted(selection_file)[-1])) if selection_file else pd.DataFrame()
    df_kw = pd.read_excel(os.path.join(OUTPUT_DIR, sorted(kw_file)[-1])) if kw_file else pd.DataFrame()
    
    print(f"\n📊 数据概览:")
    print(f"  关键词库: {len(df_kw):,} 个")
    print(f"  精选上架产品: {len(df_selection)} 个")
    
    # 核心推荐
    print(f"\n{'='*70}")
    print("🏆 核心推荐上架产品（按综合评分排序）")
    print(f"{'='*70}")
    
    for i, (_, row) in enumerate(df_selection.head(5).iterrows()):
        price = row['当前价格']
        profit, margin = get_fba_cost(price)
        kw = str(row['关键词'])[:35]
        
        print(f"\n{'─'*50}")
        print(f"  #{i+1} [{row['综合评分']}分] {row['品类风险']} | {kw}")
        print(f"  对标: {row.get('ASIN','')} - {str(row.get('商品标题',''))[:50]}")
        print(f"  价格: ${price} | 利润: ${profit}/件 | 毛利率: {margin}%")
        print(f"  评论: {int(row['评论数'])} | 评分: ★{row['星级评分']} | 卖家: {int(row['卖家数量'])}")
        
        # 上品推荐
        print(f"\n  ▶ 上品方案:")
        
        if 'candles' in str(kw).lower() or 'candel' in str(kw).lower():
            print(f"    品名: 香薰蜡烛套装 / 无烟蜡烛")
            print(f"    建议1688采购价: ¥15-25/个")
            print(f"    差异化: 礼盒包装+多香味可选")
            print(f"    广告策略: 激进推广 (90天预估利润$4300)")
        elif 'light' in str(kw).lower() and 'cover' in str(kw).lower():
            print(f"    品名: 荧光灯罩装饰板")
            print(f"    建议1688采购价: ¥20-35/套")
            print(f"    差异化: 多种图案/尺寸可选")
            print(f"    广告策略: 激进推广 (90天预估利润$1835)")
        elif 'recorder' in str(kw).lower() or 'voice' in str(kw).lower():
            print(f"    品名: 数字录音笔")
            print(f"    建议1688采购价: ¥40-60/个")
            print(f"    差异化: 加大内存+AI转录功能")
            print(f"    广告策略: 激进推广 (90天预估利润$3485)")
        elif 'yoga' in str(kw).lower() or 'towel' in str(kw).lower():
            print(f"    品名: 防滑瑜伽毛巾")
            print(f"    建议1688采购价: ¥15-25/条")
            print(f"    差异化: 超吸水+速干面料")
            print(f"    广告策略: 谨慎 (利润空间小)")
        else:
            print(f"    建议1688采购价: ¥20-40")
            print(f"    广告策略: 激进推广")
    
    # 整体策略
    print(f"\n{'='*70}")
    print("📋 整体运营策略")
    print(f"{'='*70}")
    
    print("""
┌─ 第一阶段：选品上架 (第1-2周) ──────────────────────┐
│ 1. 从推荐清单中选择1-2个产品开始                     │
│ 2. 1688/阿里国际站找供应商，打样3-5家               │
│ 3. 确定包装方案（带LOGO的品牌包装）                  │
│ 4. 申请UPC码 + 品牌备案                              │
│ 5. 准备Listing图文（主图/A+/视频）                   │
└────────────────────────────────────────────────────┘

┌─ 第二阶段：新品推广 (第1-30天) ─────────────────────┐
│ 1. 低价上架（建议价85%）+ $2-3 Coupon               │
│ 2. 自动广告开启（日预算$40-50）                      │
│ 3. Vine计划送测（送30个换取基础评论）                 │
│ 4. 手动广告精准匹配（核心长尾词）                     │
│ 5. 目标：日销3-5单，积累10+评论                      │
└────────────────────────────────────────────────────┘

┌─ 第三阶段：排名冲刺 (第31-60天) ────────────────────┐
│ 1. 价格恢复至正常价                                  │
│ 2. 优化广告：保留ACOS<30%的词，暂停高ACOS词           │
│ 3. 增加商品定位广告（打竞品）                         │
│ 4. BD/LD秒杀申报（如果有）                           │
│ 5. 目标：日销8-12单，BSR进入Top 20000                │
└────────────────────────────────────────────────────┘

┌─ 第四阶段：稳定盈利 (第61-90天) ────────────────────┐
│ 1. 广告预算降至$25-30/天                             │
│ 2. 追加SB/SD品牌广告                                 │
│ 3. 补货计划：海运降低成本                            │
│ 4. 拓展变体（新颜色/新规格）                         │
│ 5. 目标：日销15+单，月利润$1000+                     │
└────────────────────────────────────────────────────┘
""")
    
    # 合规建议
    print(f"\n{'='*70}")
    print("⚖️ 合规建议")
    print(f"{'='*70}")
    print("""
  1. 品牌备案（必须）
     - 美国商标注册( USPTO ): $250-350/类，6-8个月
     - 可以先申请TM标（1-2周）就备案
     
  2. 产品合规
     - 电子产品: FCC认证
     - 儿童用品: CPC认证
     - 化妆品: FDA注册
     - 一般产品: 不需要强制认证，但建议做UL测试
     
  3. 专利检查
     - 上架前查美国外观设计专利
     - 卖家精灵有专利查重功能
     
  4. 账号安全
     - 新账号前3个月不要大量刷单
     - 合规索评（Request a Review按钮）
     - 注意IP隔离（不要一个IP登多个账号）
""")
    
    # 风险提示
    print(f"\n{'='*70}")
    print("⚠️ 风险预警")
    print(f"{'='*70}")
    print("""
  🔴 高风险：
     • 食品/补充剂/母婴/玩具 — 审核严，不建议新卖家碰
     
  🟡 中风险：
     • 电子类 — 退货率高(15-20%)，挤掉利润
     • 服装类 — 尺寸退货问题
     
  🟢 低风险（推荐新手）：
     • 家居/厨房/办公 — 退货率<5%
     • 宠物用品 — 增长快
     • 美妆个护工具 — 非消耗品类
     
  💡 避坑指南：
     • 不要做低价品($<10)，利润不够广告费
     • 不要做超大件(FBA费用吃掉利润)
     • 不要做季节性产品（新手期来不及清货）
     • 不要碰大牌周边（侵权风险）
""")
    
    # 资金计划
    print(f"\n{'='*70}")
    print("💰 资金需求预估（单产品）")
    print(f"{'='*70}")
    print("""
  首批成本估算:
  产品采购(500件×¥25)         = ¥12,500
  头程空运(500件×¥12)          = ¥6,000
  UPC码(1个)                   = ¥150
  品牌注册(TM标)               = ¥2,000
  Listing制作(图+视频)         = ¥3,000
  ─────────────────────────────────
  首批总投入                   ≈ ¥23,650 (≈$3,300)
  
  运营储备:
  广告费30天×50/天             = $1,500
  补货备货                      = $2,000
  ─────────────────────────────────
  总资金需求                   ≈ $6,800/产品
  
  利润预期（90天）:
  激进策略下利润$1,800-$4,300
  回本周期: 60-90天
""")
    
    # 下一步
    print(f"{'='*70}")
    print("🎯 下阶段建议")
    print(f"{'='*70}")
    print("""
  1. 选1-2个产品，开始1688找供应商打样
  2. 申请品牌备案（TM标即可）
  3. 准备Listing图文
  4. 确定首批库存数量，安排空运
  5. 上架后按上述3阶段推品
  6. 90天后复盘数据，决定是否扩品
""")
    
    # 保存
    report_file = os.path.join(OUTPUT_DIR, f"最终推荐方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("Amazon 选品运营 - 最终推荐方案\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 70 + "\n\n")
        
        f.write("数据概览:\n")
        f.write(f"  关键词库: {len(df_kw):,} 个\n")
        f.write(f"  精选上架产品: {len(df_selection)} 个\n\n")
        
        f.write("核心推荐上架产品:\n")
        for i, (_, row) in enumerate(df_selection.head(10).iterrows()):
            price = row['当前价格']
            profit, margin = get_fba_cost(price)
            f.write(f"\n  #{i+1} [{row['综合评分']}分] {row['品类风险']}\n")
            f.write(f"  {row['关键词']}\n")
            f.write(f"  价格: ${price} | 利润: ${profit}/件 | 毛利率: {margin}%\n")
            f.write(f"  评论: {int(row['评论数'])} | 评分: ★{row['星级评分']}\n")
        
        f.write("\n\n" + "=" * 70 + "\n")
        f.write("完整运营策略\n")
        f.write("=" * 70 + "\n")
        f.write("第一阶段：选品上架 (第1-2周)\n")
        f.write("第二阶段：新品推广 (第1-30天)\n")
        f.write("第三阶段：排名冲刺 (第31-60天)\n")
        f.write("第四阶段：稳定盈利 (第61-90天)\n\n")
        
        f.write("合规建议\n")
        f.write("风险预警\n")
        f.write("资金需求预估\n")
    
    print(f"\n✅ 已保存: {report_file}")

if __name__ == "__main__":
    generate_business_plan()
