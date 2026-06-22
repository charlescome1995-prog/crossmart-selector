# CrossMart Selector 选品引擎

独立的亚马逊**选品推荐**工具，与 `crossmart-monitor`（ASIN 监控）平级。
基于卖家精灵关键词数据，用「16 核心指标 + 4 策略 + FBA 利润模型」筛选潜力产品。

🔗 在线页面：https://charlescome1995-prog.github.io/crossmart-selector/

---

## 每周使用流程

1. 从卖家精灵导出关键词 Excel（字段同 `1Amazon关键词_YYYYMMDD.xlsx`）
2. 把 Excel 放到 `backend/data/input/`
3. 运行：
   ```powershell
   cd crossmart-selector
   python backend/run_selection.py
   ```
4. 自动生成 `frontend/data/selection-data.json`
5. 推送部署：
   ```powershell
   git add -A; git commit -m "data: 本周选品 YYYYMMDD"; git push
   ```
6. 刷新页面查看推荐结果

---

## 选品逻辑

### 16 核心指标（2025 亚马逊爆款思维）
价格 $10-50 / 月销 300-900 / 竞品评论 <10000 / 毛利率 >30% / 无大品牌垄断 /
非季节性 / 市场深度（前3 <60%）/ Listing 有优化空间 / 关键词月搜 >10K 等

### 4 种策略
| 策略 | 特征 |
|------|------|
| 🔵 蓝海 | 小众市场、低竞争、高利润 |
| 🔴 红海 | 成熟大市场、高销量 |
| 🟡 差异化 | 细分市场、有改进空间 |
| 🟢 跟随 | 已验证市场、稳定收益 |

### 综合评分（0-100）
指标通过率 40% + 毛利率 25% + 市场热度 20% + 竞争宽松度 15%
- ≥85 🔥 强烈推荐
- ≥70 ⚡ 可以考虑
- <70 👀 观察

### FBA 利润模型
产品成本 20% + 亚马逊佣金 15% + FBA 费 + 头程空运 + 广告 12% + 退货损耗 + 仓储 + 其他

---

## 目录结构

```
crossmart-selector/
├── index.html                  # Pages 入口（跳转 selection.html）
├── frontend/
│   ├── selection.html          # 选品推荐页（列表/卡片视图 + 策略筛选）
│   └── data/
│       └── selection-data.json # 选品结果（run_selection.py 生成）
└── backend/
    ├── run_selection.py        # ★ 主入口：Excel → JSON
    ├── config.py               # 策略参数 / 利润模型 / 选品规则
    ├── selectors/
    │   └── product_selector.py # 选品引擎核心（16指标/策略/利润）
    ├── pipelines/              # 四阶段流水线 S1-S4（备用）
    └── data/
        ├── input/              # 放每周 Excel（gitignore）
        └── output/             # 引擎 Excel 输出（gitignore）
```

逻辑迁移自 `amazon_ai_kit`（旧项目）。
