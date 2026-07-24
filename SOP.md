# CrossMart Selector SOP（2026-07-24 落地版）

> **一个 SOP = 两部分**：Part A 卡数据（选品） + Part B 推品策略（怎么打）。两部分用契约（triage.json 字段）刚性对接，不能拆开用。

---

## 完整流程图

```
┌──────────────────────────────────────────────────────────────┐
│ ABA xlsx × 4 国                                              │
│ (US/UK/DE/CA, 月度导出)                                       │
└──────────────────────────────────────────────────────────────┘
   ↓
┌──────────────────────────────────────────────────────────────┐
│ Part A · 卡数据（选品环节）                                    │
│                                                               │
│  1. quick_filter.py                                           │
│     • 硬筛（filters.json/hard: 月购/需供比/SPR/价格/评分）     │
│     • 软筛（filters.json/soft: 点击/转化集中度，按国家覆盖）   │
│     • 黑名单（filters.json/blacklist + flag_dicts/）           │
│     • 残词过滤（min_keystrokes=3）                             │
│     输出: processed/quick_filter/latest.json (48 条)          │
│                                                               │
│  2. triage.py                                                 │
│     • 跑 flag_dicts/ 4 个词典打 risk_flags                    │
│     • 按 TRIAGE_THRESHOLDS 算 tier_score                      │
│     • 判档位: 🔴 砍 / 🟡 待观察 / 🟢 深挖                     │
│     输出: processed/triage/latest.json (48 条全档)             │
│            + frontend/data/triage.json                         │
└──────────────────────────────────────────────────────────────┘
   ↓
   ↑↑↑ 契约字段（triage.json 必带）↑↑↑
   ↑  country, category_top, metrics(12 字段), tier, tier_score, risk_flags, reason ↑
   ↓
┌──────────────────────────────────────────────────────────────┐
│ Part B · 推品策略（怎么打）                                    │
│                                                               │
│  strategy_router.py                                           │
│  • 只接 🟢🟡，🔴 不进 Part B                                  │
│  • 按"评分数 × 广告竞品数"二维分 4 桶                          │
│  • 每桶套一个 action_template（推品动作模板）                  │
│  输出: processed/strategy/latest.json                         │
│         + frontend/data/strategy.json                          │
└──────────────────────────────────────────────────────────────┘
   ↓
┌──────────────────────────────────────────────────────────────┐
│ 单品说明卡（按需，🟢 才做）                                     │
│  7 段固定模板：                                                │
│   1. 品类与定位                                                │
│   2. 搜索词矩阵（母词/长尾/竞品 ASIN）                          │
│   3. SERP 截图位                                              │
│   4. 月销/毛利估算                                             │
│   5. 合规 checklist                                            │
│   6. Listing 卖点                                              │
│   7. 下一步动作                                                │
└──────────────────────────────────────────────────────────────┘
   ↓
   ↑↑↑ 反馈环（推品验证后回流）↑↑↑
   ↑ 推品后看实际 CVR/ACOS，回流到 filters.json 调阈值 ↑
   ↑
```

---

## 关键文件

| 文件 | 作用 | 何时改 |
|---|---|---|
| `backend/config/filters.json` | 硬筛/软筛阈值 + 总黑名单 | 数据变化、调严/调松 |
| `backend/config/flag_dicts/*.txt` | 4 类细粒度词典 | 漏网词发现时追加 |
| `backend/selectors/quick_filter.py` | ABA → 候选 | 几乎不改 |
| `backend/selectors/triage.py` | 候选 → 分档 | 改 TRIAGE_THRESHOLDS |
| `backend/selectors/strategy_router.py` | 分档 → 4 桶 | 改 BUCKETS |

## 4 桶判定（Part B 核心）

| 桶 | 评分数 | 广告竞品数 | 推品动作 |
|---|---|---|---|
| 品牌创新 | <200 | <15 | 测款优先：低预算多 ASIN 铺 |
| newrelease | 200-800 | <15 | 抢位优先：差异化主图 + 早期 review |
| 模仿跟风 | 200-800 | 15-50 | 优化优先：吃平均利润，卷 Listing |
| 老款延伸 | <200 | 15-50 | 关联优先：吃头部流量 + 变体延伸 |

## 3 档判定（Part A 核心）

| 档 | 条件 |
|---|---|
| 🔴 砍 | 命中 brand_words / ip_names / adult / truncated 任一词典 |
| 🟢 深挖 | 4 项 ABCD 全过 + 无 regulated + 非 CA |
| 🟡 待观察 | 其余 |

## 跑一次完整流程

```bash
# Part A
python backend/selectors/quick_filter.py
python backend/selectors/triage.py

# Part B
python backend/selectors/strategy_router.py
```

## 维护节奏

- **每次新 ABA 月度数据出来**：跑一次完整 SOP（10 分钟）
- **每次推品验证（30 天）后**：回流到 filters.json 调阈值
- **每次发现漏网词**：追加到对应 flag_dicts/*.txt
- **每月一次**：review 4 桶分布，看哪个桶占比异常

## 这次的关键决策（2026-07-24 落地）

1. **filters.json / blacklist 拆出去**：通用黑名单留 filters.json；细粒度词典（品牌词/IP/残词/强监管）落 `flag_dicts/` 子目录
2. **新增 6 个品牌词漏网**：gaviscon / atrixo / braun / ninja / nespresso / toplux / sweed / omni / healora / pretty litter / snuzpod
3. **新增 8 个 IP 漏网**：bad bunny / bebe rexha / tate mcrae / judas priest / enhypen / cowboy bebop / schimanski / wonky donkey
4. **4 桶定义确认**：见上表
5. **CA 站今天没货**（软筛后归零），下次 ABA 数据先看 CA 是否恢复