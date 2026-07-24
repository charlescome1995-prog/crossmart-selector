"""
triage.py — Part A 卡数据（选品环节）
=====================================

输入 : backend/processed/quick_filter/latest.json
        backend/config/filters.json
        backend/config/flag_dicts/*.txt
输出 : backend/processed/triage/{YYYY-MM-DD_HHMM}.json + latest.json
        frontend/data/triage.json（给前端用）

核心职责：
- 把 quick-pick.json 的 48 条候选按硬指标 + 风险标签分档（🟢🟡🔴）
- 每条带 tier_score（每项打分明细）+ risk_flags（标准化标签）+ reason（15字理由）
- 显式落 thresholds，改一处重跑即重分档
- 不回答"怎么打"——那是 Part B 的事

与 quick_filter.py 的边界：
- quick_filter: ABA xlsx → 48 条候选（卡数据筛选）
- triage:       48 条候选 → 3 档分档 + 风险标签（卡数据归档）
"""
from __future__ import annotations
import os
import re
import sys
import json
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# === 路径 ===
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
QUICK_PICK_LATEST = os.path.join(ROOT, "processed", "quick_filter", "latest.json")
CONFIG_PATH = os.path.join(ROOT, "config", "filters.json")
FLAG_DICTS_DIR = os.path.join(ROOT, "config", "flag_dicts")
TRIAGE_PROCESSED_DIR = os.path.join(ROOT, "processed", "triage")
TRIAGE_FRONTEND_DIR = os.path.join(
    os.path.dirname(ROOT), "frontend", "data"  # crossmart-selector/frontend/data/
)

# === 分档阈值（独立可配，不与 quick_filter.hard 耦合） ===
# 7/24 第一次跑（1000/20/500/30）只过 1 条 → 太严。
# 调整为更现实的阈值（300/10/500/50），目标 🟢 落在 5-10 条可人工精修
TRIAGE_THRESHOLDS = {
    "A_月购_min": 300,
    "B_需供比_min": 10,
    "C_评分数_max_lt": 500,
    "D_SPR_max_lt": 50,
}


def load_flag_dicts() -> dict[str, list[str]]:
    """加载 flag_dicts/ 下所有 .txt 文件，返回 {文件名: [词条]}"""
    dicts = {}
    if not os.path.isdir(FLAG_DICTS_DIR):
        return dicts
    for fn in sorted(os.listdir(FLAG_DICTS_DIR)):
        if not fn.endswith(".txt"):
            continue
        cat = fn[:-4]  # 去 .txt
        words = []
        with open(os.path.join(FLAG_DICTS_DIR, fn), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # regulated.txt 用 yaml-like 结构，跳过缩进行
                if line.endswith(":") or line.startswith("  -"):
                    continue
                words.append(line.lower())
        dicts[cat] = words
    return dicts


def match_flags(keyword: str, flag_dicts: dict[str, list[str]]) -> list[str]:
    """对单条 keyword 跑所有词典，返回命中的 flag 列表"""
    kw = (keyword or "").lower()
    if not kw:
        return []
    hits = []
    for cat, words in flag_dicts.items():
        for w in words:
            if w and w in kw:
                hits.append(cat)
                break  # 一类只记一次
    return hits


def score_one(item: dict, th: dict) -> dict:
    """对单条 item 算 tier_score（不判档位，只算各项明细）"""
    m = item["metrics"]
    yg = m.get("月购_calc") or 0
    xgb = m.get("需供比") or 0
    pfs = m.get("评分数") or 0
    spr = m.get("SPR") or 0
    price = m.get("价格") or 0
    click_c = m.get("点击集中度") or 0

    passes = {
        "A_月购": yg >= th["A_月购_min"],
        "B_需供比": xgb >= th["B_需供比_min"],
        "C_评分数_lt": pfs < th["C_评分数_max_lt"],
        "D_SPR_lt": spr < th["D_SPR_max_lt"],
    }
    return {
        "月购_calc": yg,
        "需供比": xgb,
        "评分数": pfs,
        "SPR": spr,
        "价格": price,
        "点击集中度": click_c,
        "passes_A": passes["A_月购"],
        "passes_B": passes["B_需供比"],
        "passes_C": passes["C_评分数_lt"],
        "passes_D": passes["D_SPR_lt"],
        "passes_ABCs": passes["A_月购"] and passes["B_需供比"] and passes["C_评分数_lt"],
    }


def tier_from_score(score: dict, flags: list[str]) -> str:
    """
    档位判定：
    - 🔴 砍：命中 brand_words / ip_names / adult / truncated 任意一个（这些是硬红线）
    - 🟢 深挖：4 项 ABCD 全过 + 无 regulated 强监管 + 国家非 CA
    - 🟡 待观察：其他
    """
    hard_red_flags = {"brand_words", "ip_names", "adult", "truncated"}
    if hard_red_flags & set(flags):
        return "🔴"
    if (
        score["passes_ABCs"]
        and score["passes_D"]
        and "regulated" not in flags
    ):
        return "🟢"
    return "🟡"


def reason_from_score(score: dict, flags: list[str], tier: str) -> str:
    """生成 15 字内的归类理由"""
    if "brand_words" in flags:
        return "品牌词漏网，砍"
    if "ip_names" in flags:
        return "IP 词，砍"
    if "adult" in flags:
        return "成人用品，砍"
    if "truncated" in flags:
        return "残词/截断，砍"
    if tier == "🟢":
        return "ABCD 全过，可深挖"
    # 🟡 的细分
    if not score["passes_A"]:
        return "月购未达线"
    if not score["passes_B"]:
        return "需供比未达线"
    if not score["passes_C"]:
        return "评分数偏高"
    if not score["passes_D"]:
        return "广告竞争激烈"
    if "regulated" in flags:
        return "强监管品类，待核"
    return "部分达标，待观察"


def main():
    print("=== triage.py — Part A 卡数据分档 ===")
    print(f"读取: {QUICK_PICK_LATEST}")

    if not os.path.exists(QUICK_PICK_LATEST):
        print(f"[ERR] 找不到 {QUICK_PICK_LATEST}，请先跑 quick_filter.py", file=sys.stderr)
        sys.exit(1)

    with open(QUICK_PICK_LATEST, "r", encoding="utf-8") as f:
        quick = json.load(f)

    flag_dicts = load_flag_dicts()
    print(f"加载 {len(flag_dicts)} 个词典: {list(flag_dicts.keys())}")

    items_out = []
    tier_count = {"🟢": 0, "🟡": 0, "🔴": 0}

    for rank, it in enumerate(quick["items"], start=1):
        flags = match_flags(it["keyword"], flag_dicts)
        score = score_one(it, TRIAGE_THRESHOLDS)
        tier = tier_from_score(score, flags)
        reason = reason_from_score(score, flags, tier)
        tier_count[tier] += 1

        items_out.append({
            "rank": rank,
            "country": it["country"],
            "keyword": it["keyword"],
            "category_top": it["category_top"],
            "metrics": it["metrics"],
            "tier": tier,
            "tier_score": score,
            "risk_flags": flags,
            "reason": reason,
        })

    out = {
        "schema_version": "triage.v1",
        "source_pool": f"quick-pick.json#{quick.get('config_version', 'unknown')}",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "thresholds": TRIAGE_THRESHOLDS,
        "flag_dicts": list(flag_dicts.keys()),
        "stats": {
            "input": len(quick["items"]),
            "tier_count": tier_count,
            "by_country_tier": _by_country_tier(items_out),
        },
        "items": items_out,
    }

    os.makedirs(TRIAGE_PROCESSED_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    archive_path = os.path.join(TRIAGE_PROCESSED_DIR, f"{ts}.json")
    latest_path = os.path.join(TRIAGE_PROCESSED_DIR, "latest.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 同步给前端
    os.makedirs(TRIAGE_FRONTEND_DIR, exist_ok=True)
    frontend_path = os.path.join(TRIAGE_FRONTEND_DIR, "triage.json")
    with open(frontend_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n分档完成:")
    for t, n in tier_count.items():
        print(f"  {t} {n} 条")
    print(f"\n归档: {archive_path}")
    print(f"最新: {latest_path}")
    print(f"前端: {frontend_path}")


def _by_country_tier(items: list[dict]) -> dict:
    out = {}
    for it in items:
        c = it["country"]
        t = it["tier"]
        out.setdefault(c, {"🟢": 0, "🟡": 0, "🔴": 0})
        out[c][t] += 1
    return out


if __name__ == "__main__":
    main()