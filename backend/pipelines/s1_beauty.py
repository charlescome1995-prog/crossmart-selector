# -*- coding: utf-8 -*-
"""美妆个护精选分析"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from datetime import datetime

BASE = r"C:\Users\OPENPC\.openclaw\workspace\projects\amazon_ai_kit"
OUTPUT_DIR = os.path.join(BASE, "output")
DATA_DIR = os.path.join(BASE, "0_latest_rawdata")

# 美妆个护关键词
BEAUTY_KWS = [
    'nail', 'skincare', 'skin care', 'serum', 'moisturizer', 'sunscreen', 'spf',
    'face mask', 'eye cream', 'toner', 'cleanser', 'exfoliant', 'retinol',
    'hair', 'hairbrush', 'comb', 'scalp', 'shampoo', 'conditioner', 'hair mask',
    'dry shampoo', 'hair oil', 'hair growth', 'hair loss', 'eyelash', 'eyebrow',
    'lip balm', 'deodorant', 'body wash', 'lotion', 'body butter', 'body scrub',
    'self tan', 'spray tan', 'makeup', 'foundation', 'concealer', 'blush',
    'highlight', 'setting spray', 'brush set', 'beauty blender', 'jade roller',
    'gua sha', 'facial roller', 'electric nail', 'nail clipper', 'nail file',
    'cuticle', 'pedicure', 'manicure', 'collagen', 'vitamin c', 'hyaluronic',
    'niacinamide', 'lash', 'brow', 'nail polish', 'curling iron',
    'hair straightener', 'hair dryer', 'electric razor', 'shaver', 'trimmer',
    'waxing', 'bath bomb', 'hand cream', 'foot file', 'pumice stone', 'callus',
    'pedicure kit', 'cosmetic bag', 'makeup bag', 'makeup case',
    'vanity mirror', 'lighted mirror', 'makeup mirror',
]

# 加载数据
df = pd.read_excel(os.path.join(OUTPUT_DIR, "关键词竞争力_34447条_20260511_094404.xlsx"))
kw_col = '关键词(绿色建议进入，黄色找切入点，粉色观察)'
kw_lower = df[kw_col].astype(str).str.lower()

# 筛选美妆个护
mask = kw_lower.str.contains('|'.join(BEAUTY_KWS), na=False)
beauty = df[mask].sort_values('竞争力评分', ascending=False)

print(f"美妆个护相关关键词: {len(beauty):,} 个\n")

# 等级分布
for g in ['S', 'A', 'B', 'C']:
    c = (beauty['等级'] == g).sum()
    if c > 0:
        avg = beauty[beauty['等级'] == g]['竞争力评分'].mean()
        print(f"  {g}级: {c:,} 个 (平均分 {avg:.0f})")

print(f"\n{'='*70}")
print("🏆 美妆个护 Top 40 关键词（按竞争力评分）")
print(f"{'='*70}")

for i, (_, row) in enumerate(beauty.head(40).iterrows()):
    kw = str(row[kw_col])[:35]
    ms = int(row['20260113月搜'])
    comp = int(row['广告竞品数'])
    pcp = row['PCP竞价（美元）']
    sd = row['需供比']
    price = row['价格（美元）']
    rank = int(row['rank_latest'])
    spr = int(row['SPR'])
    
    print(f"\n{i+1:2d}. [{row['等级']}] [{row['竞争力评分']:2d}分] {kw}")
    print(f"     月搜{ms:,} | 竞品{comp:,} | 竞价${pcp:.2f} | 需供比{sd:.1f}")
    print(f"     ${price:.2f} | 排名{rank:,} | SPR{spr}")

# 导出美妆个护专用数据
out_file = os.path.join(OUTPUT_DIR, "美妆个护_关键词精选.xlsx")
cols = ['等级', '竞争力评分', kw_col, '品类组一', '20260113月搜', '月购',
        '需供比', '广告竞品数', '价格（美元）', 'PCP竞价（美元）',
        '转化集中度', 'SPR', '评分数', '评分值', '购买率',
        'rank_latest', '评分细节']
cols = [c for c in cols if c in beauty.columns]

from openpyxl.styles import Font
with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
    beauty[cols].to_excel(writer, index=False, sheet_name='美妆个护')
    ws = writer.sheets['美妆个护']
    ws.freeze_panes = 'A2'
    for c in ws[1]: c.font = Font(name='Times New Roman', size=11, bold=True)
    for ro in ws.iter_rows(min_row=2):
        for c in ro: c.font = Font(name='Times New Roman', size=10)

print(f"\n✅ 已保存: {out_file}")
print(f"\n{'='*70}")
print("📋 下一步计划")
print(f"{'='*70}")
print("""
从美妆个护 Top 40 中选取利润高+竞争低的产品，进入ASIN搜索数据验证。
数据已导出到美妆个护_关键词精选.xlsx，你可以直接看。
""")
