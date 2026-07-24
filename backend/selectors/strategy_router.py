"""
strategy_router.py — Part B 推品策略
=====================================

输入 : backend/processed/triage/latest.json
输出 : backend/processed/strategy/{YYYY-MM-DD_HHMM}.json + latest.json
        frontend/data/strategy.json（给前端用）

核心职责：
- 把 triage.json 的 🟢🟡 候选按"评分数 × 广告竞品数"二维分到 4 桶
- 每桶配一个"推品动作模板"
- 不评判数据——Part A 已经做完，这层只回答"这个词怎么打"

4 桶定义（闫旭 7/24 确认）：
- 品牌创新: 评分数<200 且 广告竞品数<15
- newrelease: 评分数 200-800 且 广告竞品数<15
- 模仿跟风: 评分数 200-800 且 广告竞品数 15-50
- 老款延伸: 评分数<200 且 广告竞品数 15-50
"""
from __future__ import annotations
import os
import sys
import json
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIAGE_LATEST = os.path.join(ROOT, "processed", "triage", "latest.json")
STRATEGY_PROCESSED_DIR = os.path.join(ROOT, "processed", "strategy")
STRATEGY_FRONTEND_DIR = os.path.join(os.path.dirname(ROOT), "frontend", "data")
LEGACY_KW_PATH = os.path.join(ROOT, "config", "legacy_keywords.json")

# === 4 桶定义 ===
BUCKETS = {
    "品牌创新": {
        "rule": "评分数<200 且 广告竞品数<15",
        "filter": lambda m: (m["评分数"] or 0) < 200 and (m["广告竞品数"] or 0) < 15,
        "action_template": {
            "priority": "测款优先",
            "核心动作": [
                "低预算多 ASIN 铺，看哪个起量",
                "Listing 文案走品类教育（用户认知未建立）",
                "PPC 投品类大词 + 长尾变体",
                "3-5 个 ASIN A/B test，30 天定胜负"
            ],
            "风险提示": "用户认知弱，CTR 可能偏低，初期不要追 ROI",
            "预期 ROI": "6-12 个月起量，盈利曲线长"
        }
    },
    "newrelease": {
        "rule": "评分数 200-800 且 广告竞品数<15",
        "filter": lambda m: 200 <= (m["评分数"] or 0) < 800 and (m["广告竞品数"] or 0) < 15,
        "action_template": {
            "priority": "抢位优先",
            "核心动作": [
                "差异化主图 + 视频 + 早期 review 冲刺（Vine/早期评论）",
                "PPC 抢长尾词 + 竞品 ASIN",
                "前 30 天冲 BSR 排名（BD/LD 必要时上）",
                "Listing 标题/五点要带核心长尾词"
            ],
            "风险提示": "别人刚起跑，你有差异化时间窗口，错过就成红海",
            "预期 ROI": "3-6 个月回本，盈利曲线中"
        }
    },
    "模仿跟风": {
        "rule": "评分数 200-800 且 广告竞品数 15-50",
        "filter": lambda m: 200 <= (m["评分数"] or 0) < 800 and 15 <= (m["广告竞品数"] or 0) < 50,
        "action_template": {
            "priority": "优化优先",
            "核心动作": [
                "吃平均利润，卷 Listing 质量（标题/A+/视频/包装）",
                "PPC 拼转化率（精准词 + 高出价）",
                "履约必须 A+，避免被竞品用 FBA 速度压制",
                "价格战备好（毛利率 < 25% 慎入）"
            ],
            "风险提示": "已被验证有需求但竞争激烈，差异化空间小",
            "预期 ROI": "2-4 个月回本，盈利曲线短但稳"
        }
    },
    "老款延伸": {
        "rule": "评分数<200 且 广告竞品数 15-50",
        "filter": lambda m: (m["评分数"] or 0) < 200 and 15 <= (m["广告竞品数"] or 0) < 50,
        "action_template": {
            "priority": "关联优先",
            "核心动作": [
                "吃头部流量 + 变体延伸（颜色/尺寸/套餐/配件）",
                "PPC 拼关联坑位（竞品 ASIN + 类目节点）",
                "包装差异化（bundle 套装 + 礼品装）",
                "找头部竞品未覆盖的子场景"
            ],
            "风险提示": "头部在测款/老词延伸，你跟做差异化变体可分一杯羹",
            "预期 ROI": "2-3 个月回本，盈利曲线短"
        }
    },
}


def assign_bucket(metrics: dict) -> str | None:
    """根据 metrics 返回桶名，不匹配返回 None"""
    for name, cfg in BUCKETS.items():
        if cfg["filter"](metrics):
            return name
    return None


def _priority_score(it: dict) -> float:
    """桶内排序：月购 × √需供比（兼顾规模和增长空间）"""
    m = it["metrics"]
    yg = m.get("月购_calc") or 0
    xgb = m.get("需供比") or 1
    return yg * (xgb ** 0.5)


def load_legacy_keywords() -> list[dict]:
    """从 legacy_keywords.json 读前置老品库"""
    if not os.path.exists(LEGACY_KW_PATH):
        return []
    with open(LEGACY_KW_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("legacy_keywords", [])


def match_legacy(item: dict, legacy_list: list[dict]) -> dict:
    """
    给单条候选算前置老品匹配（3 档：strong / medium / none）
    - strong: 关键词直接包含老品词（如 shea butter 在 shea butter cream 中）
    - medium: 同 category（beauty/health/home/pet/baby/outdoors）
    - none:   无关联
    """
    kw = (item.get("keyword") or "").lower()
    cat = (item.get("category_top") or "").lower()
    best = {"strength": "none", "legacy_kw": "", "legacy_zh": "", "legacy_category": ""}
    for leg in legacy_list:
        lkw = (leg.get("kw") or "").lower().strip()
        lcat = (leg.get("category") or "").lower().strip()
        if not lkw:
            continue
        # 强：关键词里包含老品词，或老品词包含关键词首词
        first_word = kw.split(" ")[0] if kw else ""
        if lkw in kw or (first_word and first_word in lkw):
            if best["strength"] != "strong":
                best = {
                    "strength": "strong",
                    "legacy_kw": leg["kw"],
                    "legacy_zh": leg.get("zh", ""),
                    "legacy_category": lcat,
                }
            continue
        # 中：category 命中老品词的 category 映射
        cat_match = False
        if lcat == "beauty" and any(k in cat for k in ["beauty", "health", "personal care"]):
            cat_match = True
        elif lcat == "health" and any(k in cat for k in ["health", "personal care"]):
            cat_match = True
        elif lcat == "home" and any(k in cat for k in ["home", "kitchen", "garden"]):
            cat_match = True
        elif lcat == "pet" and "pet" in cat:
            cat_match = True
        elif lcat == "baby" and "baby" in cat:
            cat_match = True
        elif lcat == "outdoors" and any(k in cat for k in ["sport", "outdoor", "garden"]):
            cat_match = True
        if cat_match and best["strength"] == "none":
            best = {
                "strength": "medium",
                "legacy_kw": leg["kw"],
                "legacy_zh": leg.get("zh", ""),
                "legacy_category": lcat,
            }
    return best


def main():
    print("=== strategy_router.py — Part B 推品策略 ===")
    print(f"读取: {TRIAGE_LATEST}")

    if not os.path.exists(TRIAGE_LATEST):
        print(f"[ERR] 找不到 {TRIAGE_LATEST}，请先跑 triage.py", file=sys.stderr)
        sys.exit(1)

    with open(TRIAGE_LATEST, "r", encoding="utf-8") as f:
        triage = json.load(f)

    # 只接 🟢🟡，🔴 不进 Part B
    eligible = [it for it in triage["items"] if it["tier"] in ("🟢", "🟡")]
    print(f"🟢🟡 候选: {len(eligible)} 条（🔴 {len(triage['items']) - len(eligible)} 条不进策略）")

    # 4 桶分流
    legacy_list = load_legacy_keywords()
    print(f"加载 {len(legacy_list)} 个老品关键词")

    buckets = {name: [] for name in BUCKETS}
    no_bucket = []
    for it in eligible:
        b = assign_bucket(it["metrics"])
        if b:
            buckets[b].append(it)
        else:
            no_bucket.append(it)

    # 桶内排序 + 套动作模板
    out_buckets = {}
    for name, items in buckets.items():
        items_sorted = sorted(items, key=_priority_score, reverse=True)
        out_buckets[name] = {
            "rule": BUCKETS[name]["rule"],
            "count": len(items_sorted),
            "items": [
                {
                    "rank": it["rank"],
                    "country": it["country"],
                    "keyword": it["keyword"],
                    "tier_from_part_A": it["tier"],
                    "metrics": it["metrics"],
                    "risk_flags": it["risk_flags"],
                    "priority_score": round(_priority_score(it), 1),
                    "action_template": BUCKETS[name]["action_template"],
                    "legacy_match": match_legacy(it, legacy_list),
                }
                for it in items_sorted
            ],
        }

    out = {
        "schema_version": "strategy.v1",
        "source_triage": triage.get("source_pool", "unknown"),
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "legacy_keywords": legacy_list,
        "buckets": out_buckets,
        "no_bucket_eligible": [
            {
                "rank": it["rank"],
                "country": it["country"],
                "keyword": it["keyword"],
                "reason": "评分/广告竞品数都不在 4 桶区间"
            } for it in no_bucket
        ],
        "stats": {
            "eligible": len(eligible),
            "in_buckets": sum(len(v) for v in buckets.values()),
            "no_bucket": len(no_bucket),
        }
    }

    os.makedirs(STRATEGY_PROCESSED_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    archive_path = os.path.join(STRATEGY_PROCESSED_DIR, f"{ts}.json")
    latest_path = os.path.join(STRATEGY_PROCESSED_DIR, "latest.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 同步前端
    os.makedirs(STRATEGY_FRONTEND_DIR, exist_ok=True)
    frontend_path = os.path.join(STRATEGY_FRONTEND_DIR, "strategy.json")
    with open(frontend_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n4 桶分布:")
    for name, b in out_buckets.items():
        print(f"  {name}: {b['count']} 条")
    print(f"  未进桶: {len(no_bucket)} 条")
    print(f"\n归档: {archive_path}")
    print(f"最新: {latest_path}")
    print(f"前端: {frontend_path}")


if __name__ == "__main__":
    main()