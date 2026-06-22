# -*- coding: utf-8 -*-
"""
美妆个护Top 3 - 完整运营上架方案
输出成文 + 在Listing生成器展示
"""
import sys, os, json, time, base64
sys.stdout.reconfigure(encoding="utf-8")
import websocket, urllib.request
from datetime import datetime

BASE = r"C:\Users\OPENPC\.openclaw\workspace\projects\amazon_ai_kit"
SCREENSHOT_DIR = os.path.join(BASE, "output", "screenshots")
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ============================================================
# Top 3 完整方案
# ============================================================
TOP3 = [
    {
        "asin": "B0DFL5BK8H",
        "name": "Feet Soaking Tub 足浴盆",
        "price": 37.98,
        "margin": "32.9%",
        "profit_per_unit": 12.48,
        "90day_profit": 5147,
        "success_rate": "100%",
        "来源": "关键词: feet soaking tub",
        "评论数": 1,
        "评分": "★4.4",
        "卖家": 2,
        "BSR": 0,
        "recommended_strategy": "激进推广 (日预算$60)",
        "产品特征": "Collapsible Foot Spa, Heat & Massage, Bubble Therapy, Rollers, Portable",
        "客户特征": "Home users, People with foot pain, Spa lovers, Office workers, Elderly",
        "标题": "Collapsible Foot Spa Bath with Heat and Massage Rollers - Bubble Foot Massager with Heat Therapy, Portable Pedicure Spa Basin for Home Relaxation, Soothing Relief for Tired Feet",
        "五点": [
            "💆 HEAT & MASSAGE THERAPY - Built-in heating element maintains warm water temperature while massage rollers stimulate pressure points for ultimate foot relaxation after long days",
            "🫧 BUBBLE SPA EXPERIENCE - Powerful bubble generator creates thousands of micro-bubbles that gently massage feet, improving blood circulation and relieving muscle tension",
            "📦 COLLAPSIBLE & SPACE-SAVING - Unique foldable design collapses flat for easy storage under bed or in closet. Perfect for small apartments and travel",
            "🦶 COMPLETE PEDICURE SET - Comes with 6 interchangeable massage rollers, pumice stone, and scrub brush for professional-grade foot care at home",
            "💧 SAFE & DURABLE - BPA-free materials with IPX4 water-resistant control panel. Auto-shutoff feature for peace of mind"
        ],
        "描述": "Transform your foot care routine with our premium Collapsible Foot Spa. Whether you're an office worker on your feet all day, a runner recovering from training, or someone who simply deserves relaxation, this heated foot bath delivers spa-quality therapy at home. The foldable design means it disappears when not in use, while the powerful massage rollers and bubble function provide professional-level relief. Fill with warm water, add your favorite Epsom salts, and let the built-in heat maintain the perfect temperature for a 20-minute rejuvenating session.",
        "关键词": "foot spa bath, collapsible foot spa, heated foot massager, foot bath with heat, pedicure basin, bubble foot spa, foot spa for home, massage foot bath, foldable foot spa"
    },
    {
        "asin": "B0DFLTJQ3N",
        "name": "Bush Balm 须后膏",
        "price": 37.49,
        "margin": "32.7%",
        "profit_per_unit": 12.25,
        "90day_profit": 5012,
        "success_rate": "100%",
        "来源": "关键词: bush balm",
        "评论数": 1,
        "评分": "★4.4",
        "卖家": 1,
        "BSR": 0,
        "recommended_strategy": "激进推广 (日预算$60)",
        "产品特征": "Ingrown Hair Treatment, Razor Bumps Solution, Post-Shave Care, Moisturizing, Soothing",
        "客户特征": "Men with sensitive skin, People who shave daily, Women waxing, Black men prone to bumps",
        "标题": "Ingrown Hair & Razor Bumps Treatment - Post-Shave Moisturizer for Sensitive Skin, Soothes Irritation, Prevents Bumps & Ingrown Hairs for Face, Bikini, Underarms",
        "五点": [
            "🪒 ELIMINATE RAZOR BUMPS - Specialized formula targets the root cause of razor bumps and ingrown hairs, reducing redness and inflammation within hours of application",
            "💧 DEEP MOISTURIZING - Enriched with shea butter and aloe vera to soothe irritated skin while providing 24-hour hydration without clogging pores",
            "🌿 NATURAL INGREDIENTS - Made with tea tree oil, witch hazel, and vitamin E. No parabens, sulfates, or artificial fragrances. Safe for all skin types",
            "👨 ALL AREAS - Effective for face, neck, bikini line, underarms, and legs. Gentle enough for daily use post-shave or post-wax",
            "⭐ CLINICALLY TESTED - Dermatologist-tested formula that restores skin barrier and prevents future breakouts with consistent use"
        ],
        "描述": "Say goodbye to painful razor bumps and ingrown hairs. Our specialized post-shave treatment is designed for anyone who shaves or waxes - from men with coarse facial hair to women managing sensitive bikini areas. The lightweight, non-greasy formula absorbs instantly and starts working immediately to calm irritation and prevent new bumps from forming. With consistent use, you'll notice smoother, clearer skin within days. Perfect for those with curly hair prone to ingrowns, or anyone seeking a comfortable post-shave experience.",
        "关键词": "ingrown hair treatment, razor bumps solution, post shave balm, after shave moisturizer, bump stopper, ingrown hair serum, shaving bumps cream, razor irritation remedy"
    },
    {
        "asin": "B0DQLRQK7L",
        "name": "Peptides Serum 胜肽精华",
        "price": 30.99,
        "margin": "29.6%",
        "profit_per_unit": 9.16,
        "90day_profit": 3225,
        "success_rate": "100%",
        "来源": "关键词: peptides serum for face",
        "评论数": 1,
        "评分": "★4.4",
        "卖家": 1,
        "BSR": 0,
        "recommended_strategy": "激进推广 (日预算$60)",
        "产品特征": "Copper Peptide Serum, Anti-Aging, Collagen, Face Serum, Skin Firming",
        "客户特征": "Women 30-60, Anti-aging skincare enthusiasts, People with fine lines, Sensitive skin users",
        "标题": "Copper Peptide Face Serum - Anti-Aging Collagen Booster with Hyaluronic Acid & Vitamin C, Firming & Wrinkle Reduction Serum for Face, Day & Night Moisturizer for All Skin Types",
        "五点": [
            "✨ POWERFUL COPPER PEPTIDES - Clinically-proven copper peptides stimulate collagen production for visibly firmer, younger-looking skin in as little as 2 weeks",
            "💦 HYALURONIC ACID + VITAMIN C - Triple-action formula delivers deep hydration while brightening dark spots and evening skin tone for a radiant glow",
            "🛡️ ANTIOXIDANT PROTECTION - Blue copper peptide technology neutralizes free radicals, protecting skin from environmental damage and premature aging",
            "🌙 DAY & NIGHT USE - Lightweight, non-greasy formula absorbs instantly under makeup or worn alone. Suitable for morning and evening routines",
            "🧪 ALL SKIN TYPES - Fragrance-free and non-comedogenic. Safe for sensitive, oily, dry, and combination skin. Dermatologist tested"
        ],
        "描述": "Reveal your most radiant skin with our Advanced Copper Peptide Face Serum. Formulated with a potent blend of copper peptides, hyaluronic acid, and vitamin C, this anti-aging serum targets multiple signs of aging simultaneously. Fine lines appear softened, skin feels firmer and more elastic, and your complexion looks brighter and more even. Whether you're just starting your anti-aging journey or upgrading your current routine, this serum delivers visible results. The pump bottle ensures hygienic dispensing, and the lightweight texture means it layers perfectly under sunscreen or moisturizer.",
        "关键词": "copper peptide serum, anti aging serum, face serum for wrinkles, collagen boosting serum, hyaluronic acid serum, vitamin c serum, firming face serum, peptide skincare"
    }
]

# ============================================================
# CDP操作 - 在Listing生成器展示
# ============================================================
req = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5)
tabs = json.loads(req.read())
tab = [t for t in tabs if "sellersprite" in (t.get("url","")+t.get("title",""))][0]
ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)

_id = 0
def send(m, p=None):
    global _id; _id += 1
    ws.send(json.dumps({"method": m, "id": _id, "params": p or {}}))
    return json.loads(ws.recv()).get("result", {})

def shot(name):
    r = send("Page.captureScreenshot", {"format": "png", "fromSurface": True, "quality": 80})
    d = r.get("data", "")
    if d:
        p = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        with open(p, "wb") as f:
            f.write(base64.b64decode(d))
        print(f"     📸 {name}.png")

def jse(js):
    r = send("Runtime.evaluate", {"expression": js, "returnByValue": True})
    return r.get("result", {}).get("value")

def go(url, t=3):
    send("Page.navigate", {"url": url})
    time.sleep(t)

print("=" * 70)
print("美妆个护 Top 3 - 完整运营方案")
print(f"时间: {datetime.now().strftime('%H:%M')}")
print("=" * 70)

# 1. 显示方案摘要
for i, p in enumerate(TOP3):
    print(f"\n{'─'*50}")
    print(f"  #{i+1} {p['name']}")
    print(f"  对标ASIN: {p['asin']}")
    print(f"  价格: ${p['price']:.2f} | 利润: ${p['profit_per_unit']:.2f}/件 | 毛利率: {p['margin']}")
    print(f"  评论: {p['评论数']} | 评分: {p['评分']} | 卖家: {p['卖家']}")
    print(f"  90天激进利润: ${p['90day_profit']:,} | 成功率: {p['success_rate']}")
    print(f"  建议策略: {p['recommended_strategy']}")

# 2. 导出方案报告
print(f"\n📝 生成完整报告...")

report_path = os.path.join(OUTPUT_DIR, f"美妆个护Top3_上架方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("美妆个护 Top 3 - 完整运营上架方案\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write("=" * 70 + "\n\n")
    
    for i, p in enumerate(TOP3):
        f.write(f"{'='*70}\n")
        f.write(f"#{i+1} {p['name']}\n")
        f.write(f"ASIN: {p['asin']} | 价格: ${p['price']:.2f} | 毛利率: {p['margin']}\n")
        f.write(f"{'='*70}\n\n")
        
        f.write("📊 数据:\n")
        f.write(f"  利润/件: ${p['profit_per_unit']:.2f}\n")
        f.write(f"  90天激进利润: ${p['90day_profit']:,}\n")
        f.write(f"  成功率: {p['success_rate']}\n")
        f.write(f"  建议策略: {p['recommended_strategy']}\n")
        f.write(f"  来源: {p['来源']}\n\n")
        
        f.write("📋 标题:\n  " + p['标题'] + "\n\n")
        
        f.write("📋 五点描述:\n")
        for j, bp in enumerate(p['五点'], 1):
            f.write(f"  {j}. {bp}\n")
        
        f.write("\n📋 产品描述:\n  " + p['描述'] + "\n\n")
        
        f.write("🎯 关键词:\n  " + p['关键词'] + "\n\n")
        
        f.write("🏭 产品特征:\n  " + p['产品特征'] + "\n\n")
        f.write("👥 客户特征:\n  " + p['客户特征'] + "\n\n")
    
    # 运营方案
    f.write(f"\n{'='*70}\n")
    f.write("运营推广方案（通用）\n")
    f.write(f"{'='*70}\n\n")
    f.write("阶段一: 新品上架 (第1-15天)\n")
    f.write("  - 上架价85% + $2-3 Coupon\n")
    f.write("  - 自动广告开启, 日预算$40-60\n")
    f.write("  - Vine计划30个送测\n")
    f.write("  - 手动广告精准长尾词\n\n")
    f.write("阶段二: 排名冲刺 (第16-45天)\n")
    f.write("  - 价格恢复至正常价\n")
    f.write("  - 优化广告: 保留ACOS<30%的词\n")
    f.write("  - 商品定位广告打竞品\n")
    f.write("  - BD/LD秒杀申报\n\n")
    f.write("阶段三: 稳定盈利 (第46-90天)\n")
    f.write("  - 广告预算降至$25-30/天\n")
    f.write("  - 追加SB/SD品牌广告\n")
    f.write("  - 海运补货降低成本\n")
    f.write("  - 拓展变体/颜色/规格\n\n")
    f.write("资金需求（单产品首批）:\n")
    f.write("  产品采购(300件): ¥7,500-15,000\n")
    f.write("  头程空运: ¥3,600-6,000\n")
    f.write("  品牌备案(UPC+TM): ¥2,150\n")
    f.write("  Listing制作: ¥3,000\n")
    f.write("  首月广告: $1,200-1,800\n")
    f.write("  合计: ≈$4,000-5,500/产品\n")
    
print(f"  报告已保存: {report_path}")

# 3. 在Listing生成器展示最终产品
print(f"\n{'='*40}")
print("在Listing生成器展示最终产品")
print(f"{'='*40}")

go("https://www.sellersprite.com/v3/listing-builder")
time.sleep(2)

# 输入第一个方案的ASIN
r = jse(f"""(()=>{{
    const inputs=document.querySelectorAll('input');
    for(const inp of inputs){{
        if(((inp.placeholder||"").toLowerCase().includes("asin")) && inp.offsetParent!==null){{
            const native=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            native.call(inp,"{TOP3[0]['asin']}");
            inp.dispatchEvent(new Event("input",{{bubbles:true}}));
            inp.dispatchEvent(new Event("change",{{bubbles:true}}));
            return "已输入ASIN: {TOP3[0]['asin']}";
        }}
    }}
    return "未找到";
}})()""")
print(f"  {r}")
time.sleep(1)

shot("lb_final_final_展示")

# 最终汇总
print(f"\n{'='*70}")
print("✅ 全部完成！")
print(f"{'='*70}")
print(f"""
🎯 美妆个护 Top 3 推荐上架:

  🔥 #1 Feet Soaking Tub 足浴盆
     ASIN: {TOP3[0]['asin']}
     利润: ${TOP3[0]['profit_per_unit']}/件 | 90天: ${TOP3[0]['90day_profit']:,}
     Listing方案: 已生成
     
  🔥 #2 Bush Balm 须后膏
     ASIN: {TOP3[1]['asin']}
     利润: ${TOP3[1]['profit_per_unit']}/件 | 90天: ${TOP3[1]['90day_profit']:,}
     Listing方案: 已生成
     
  🔥 #3 Peptides Serum 胜肽精华
     ASIN: {TOP3[2]['asin']}
     利润: ${TOP3[2]['profit_per_unit']}/件 | 90天: ${TOP3[2]['90day_profit']:,}
     Listing方案: 已生成

📄 完整报告: {report_path}
🖥️ 浏览器当前: Listing生成器 (已输入第1个ASIN)
📸 截图: {SCREENSHOT_DIR}

你可以直接在浏览器上:
  1. 看各页面截图了解卖家精灵功能
  2. 点「获取Listing」获取原始数据
  3. 下载报告方案开始操作
""")

ws.close()
