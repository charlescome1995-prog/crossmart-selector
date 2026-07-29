# CrossMart Selector 选品引擎

独立的亚马逊**选品推荐**工具，与 `crossmart-monitor`（ASIN 监控）平级。
基于卖家精灵关键词数据 + 浏览器抓取 Amazon SRP，用「Part A 卡数据 + Part B 4 桶推品策略」筛选潜力产品。

🔗 在线页面：https://charlescome1995-prog.github.io/crossmart-selector/

---

## 每周使用流程

1. 从卖家精灵导出关键词 Excel（字段同 `1Amazon关键词_YYYYMMDD.xlsx`），放 `backend/data/input/`
2. Edge 浏览器已打开 + 卖家精灵扩展已加载（每次新开会话需手动登一次卖家精灵账号）
3. 跑一条命令（一键端到端 = Part A 卡数据 + Part A+ 浏览器抓 + Part B 4 桶）：
   ```powershell
   cd crossmart-selector
   python backend/run_all.py
   ```
   可选环境变量：
   - `set PART_A_PLUS=0`           跳过浏览器抓（只跑离线分析，10 秒）
   - `set PART_A_PLUS_MAX_ASINS=10` 每个关键词只抓 10 个 ASIN（默认 20）
   - `set PUSH_HUB=0`              跳过 crossmart-hub 同步

4. 写出的 JSON：
   - `frontend/data/triage.json`          48 条三档清单（🟢🟡🔴）
   - `frontend/data/strategy.json`        4 桶推品策略（🟢🟡 候选按 评分数 × 广告竞品数 分桶）
   - `frontend/data/keyword_asins.json`   Part A+ 抓到的 ASIN 详情（含卖家精灵 24 字段）
   - `frontend/data/selection-data.json`  全部候选打分备份
5. 推送部署：
   ```powershell
   git add -A; git commit -m "data: 本周选品 YYYYMMDD"; git push
   ```
6. 刷新页面查看推荐结果

---

## 选品逻辑

### Part A · 卡数据（基于 Excel）
- `quick_filter.py`  硬筛 + 软筛 + 黑名单 → 48 条候选
- `triage.py`        4 词典打分 → 🔴🟡🟢 三档

### Part A+ · 浏览器补抓（基于 Amazon SRP + 卖家精灵）
- 对 Excel 候选里月搜 Top 50 关键词，启 Edge + 卖家精灵扩展抓前 20 ASIN
- 抓取字段：品牌/卖家/BSR/月销量父体/上架天数/流量词/SPR/价格/评分/sponsored/自然位
- 失败重试 3 次（SS 注入不充分自动重抓）
- 关闭：环境变量 `PART_A_PLUS=0`

### Part B · 推品策略（4 桶）
| 桶 | 评分数 | 广告竞品数 | 推品动作 |
|---|---|---|---|
| 品牌创新 | <200 | <15 | 测款优先：低预算多 ASIN 铺 |
| newrelease | 200-800 | <15 | 抢位优先：打差异点 + 早期 review |
| 模仿跟风 | 200-800 | 15-50 | 优化优先：吃平均利润，卷 Listing |
| 老款延伸 | <200 | 15-50 | 关联优先：吃头部流量 + 变体延伸 |

### 16 核心指标（2025 亚马逊爆款思维）
价格 $10-50 / 月销 300-900 / 竞品评论 <10000 / 毛利率 >30% / 无大品牌垄断 /
非季节性 / 市场深度（前3 <60%）/ Listing 有优化空间 / 关键词月搜 >10K 等

### FBA 利润模型
产品成本 20% + 亚马逊佣金 15% + FBA 费 + 头程空运 + 广告 12% + 退货损耗 + 仓储 + 其他

---

## 目录结构

```
crossmart-selector/
├── index.html                  # Pages 入口（跳转 selection.html）
├── frontend/
│   ├── selection.html          # 选品推荐页（4 桶 + 卖家精灵字段）
│   ├── dev_runs.html           # ASIN 抓取试验台
│   └── data/
│       ├── triage.json
│       ├── keyword_asins.json  # Part A+ 抓的 ASIN 详情
│       └── strategy.json       # 4 桶推品
└── backend/
    ├── run_selection.py        # ★ 主入口：Excel → 浏览器抓 → JSON
    ├── config.py               # 选品规则 / 利润模型
    ├── selectors/
    │   ├── quick_filter.py     # Part A 卡数据
    │   ├── triage.py           # Part A 分档
    │   ├── strategy_router.py  # Part B 4 桶
    │   ├── fetch_keyword_asins.py  # Part A+ 浏览器抓（卖家精灵 24 字段）
    │   └── product_selector.py # 16 指标 / 5W1H（被 run_selection 调）
    ├── dev/
    │   └── asin_dev_scraper.py # 单关键词试验（走 fetch_keyword_asins）
    └── data/
        ├── input/              # 放每周 Excel（gitignore）
        └── output/             # 引擎 Excel 输出（gitignore）
```

详细 SOP 见 `SOP.md`。
