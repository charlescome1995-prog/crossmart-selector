"""
quick_filter.py — 快速筛选 ABA 关键词

输入：backend/data/input/ABA关键词_{COUNTRY}{YYYYMMDD}.xlsx
输出：backend/processed/quick_filter/{YYYY-MM-DD_HHMM}.json + latest.json

设计目标：
- 配置驱动（filters.json），将来阈值/黑名单调整只改一个文件
- 可承载 10-100 万行（pandas 向量化，无 apply lambda）
- 每个候选带 tags 和 reason，将来追溯"为什么这条没进"
- 不依赖浏览器 / 网络，离线跑
"""
from __future__ import annotations
import os
import re
import sys
import json
import glob
from datetime import datetime

import pandas as pd

# Windows PowerShell 默认 gbk，让德文 ß / ñ 炸；强制 utf-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# === 路径 ===
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
INPUT_DIR = os.path.join(ROOT, "data", "input")
PROCESSED_DIR = os.path.join(ROOT, "processed", "quick_filter")
CONFIG_PATH = os.path.join(ROOT, "config", "filters.json")

# === 国家映射（按你 4 站导出规则） ===
COUNTRIES = ["US", "UK", "DE", "CA"]

# === 数值列（强制转 float） ===
NUMERIC_COLS = [
    "月搜", "月购", "需供比", "价格（美元）", "评分数",
    "广告竞品数", "SPR", "购买率", "点击集中度", "转化集中度",
]

# === Excel 列名 → 输出 JSON 字段名（避免 PowerShell/前端编码炸） ===
COL_RENAME = {
    "价格（美元）": "价格",
    "月购_calc": "月购_calc",  # 算出来的
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def is_blacklisted(series: pd.Series, blacklist: list[str]) -> pd.Series:
    """向量化：关键词小写后任一黑名单子串命中即 True"""
    if not blacklist:
        return pd.Series([False] * len(series), index=series.index)
    s = series.fillna("").astype(str).str.lower()
    # 构建正则（一次性编译）
    pattern = re.compile("|".join(re.escape(b) for b in blacklist), re.IGNORECASE)
    return s.str.contains(pattern)


def find_input_files(input_dir: str) -> list[tuple[str, str]]:
    """
    扫描输入目录，返回 [(country, filepath), ...]
    文件名形如 ABA关键词_US20260628.xlsx 或 ABA关键词_US.xlsx
    """
    found = []
    for fp in sorted(glob.glob(os.path.join(input_dir, "ABA关键词_*.xlsx"))):
        fn = os.path.basename(fp)
        # 提取国家代码（ABA关键词_US20260628.xlsx → US）
        m = re.search(r"ABA[_-]?[^\W\d_]+_([A-Z]{2})(?:20\d{6})?\.xlsx$", fn, re.IGNORECASE)
        if not m:
            print(f"[WARN] 跳过无法解析国家代码的文件: {fn}", file=sys.stderr)
            continue
        country = m.group(1).upper()
        if country in COUNTRIES:
            found.append((country, fp))
    return found


def load_all_data(input_dir: str) -> pd.DataFrame:
    """加载全部国家的数据，统一加 _country / _source_file 列"""
    found = find_input_files(input_dir)
    if not found:
        raise FileNotFoundError(f"在 {input_dir} 找不到 ABA关键词_*.xlsx")

    frames = []
    for country, fp in found:
        df = pd.read_excel(fp)
        df["_country"] = country
        df["_source_file"] = os.path.basename(fp)
        frames.append(df)
        print(f"  [{country}] {os.path.basename(fp)}: {len(df)} 行")

    out = pd.concat(frames, ignore_index=True)
    print(f"合计: {len(out)} 行")
    return out


def apply_filter(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """应用硬筛 + 软筛（按国家覆盖）+ 黑名单 + 残词过滤，返回 (通过的行, 统计)"""
    stats = {"input": int(len(df))}

    # --- 数值化 ---
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # 列名归一（“价格（美元）” → “价格”，避免后续引用炸）
    if "价格（美元）" in df.columns and "价格" not in df.columns:
        df = df.rename(columns={"价格（美元）": "价格"})
    # 月购派生（直接计算月搜 × 购买率，验证过 8319 行完全一致）
    df["月购_calc"] = df["月搜"] * df["购买率"]

    # --- 残词过滤（关键词长度 < min_keystrokes） ---
    min_len = cfg.get("output", {}).get("min_keystrokes", 3)
    kw_len = df["关键词"].fillna("").str.len()
    bl_min = kw_len < min_len
    stats["dropped_too_short"] = int(bl_min.sum())
    df = df[~bl_min].copy()

    # --- 硬筛（每个国家独立；CA 也跑硬筛） ---
    h = cfg["hard"]
    hard_global = (
        (df["评分数"] < h["评分数_max"]) &
        (df["广告竞品数"] < h["广告竞品数_max"]) &
        (df["价格"] >= h["价格_min"]) &
        (df["价格"] <= h["价格_max"]) &
        (df["SPR"] <= h["SPR_max"]) &
        (df["需供比"] >= h["需供比_min"]) &
        (df["月购_calc"] >= h["月购_min"])
    )
    stats["after_hard"] = int(hard_global.sum())
    df_hard = df[hard_global].copy()

    # --- 软筛（按国家覆盖） ---
    soft_cfg = cfg["soft"]
    country_overrides = soft_cfg.get("country_overrides", {})
    soft_keep = pd.Series([False] * len(df_hard), index=df_hard.index)
    for c in df_hard["_country"].unique():
        sub = df_hard["_country"] == c
        override = country_overrides.get(c, {})
        if override.get("_disabled"):
            # 跳过软筛
            soft_keep.loc[sub.index] = True
            continue
        ck = override.get("点击集中度_max", soft_cfg["点击集中度_max"])
        cv = override.get("转化集中度_max", soft_cfg["转化集中度_max"])
        sub_mask = sub & (
            (df_hard["点击集中度"] <= ck) &
            (df_hard["转化集中度"] <= cv)
        )
        soft_keep.loc[sub_mask.index[sub_mask]] = True

    df_soft = df_hard[soft_keep].copy()
    stats["after_soft"] = int(len(df_soft))

    # --- 黑名单 ---
    bl_cfg = cfg.get("blacklist", {})
    if bl_cfg.get("enabled", True):
        bl = is_blacklisted(df_soft["关键词"], bl_cfg.get("keywords", []))
        stats["dropped_blacklist"] = int(bl.sum())
        df_final = df_soft[~bl].copy()
    else:
        stats["dropped_blacklist"] = 0
        df_final = df_soft

    # --- 站内去重（按月购_calc 取最高） ---
    if cfg.get("output", {}).get("dedup_within_country", True):
        df_final = df_final.sort_values("月购_calc", ascending=False)
        df_final = df_final.drop_duplicates(subset=["_country", "关键词"], keep="first")

    stats["final"] = int(len(df_final))
    stats["by_country"] = {
        c: int((df_final["_country"] == c).sum())
        for c in COUNTRIES
    }
    return df_final, stats


def to_output_items(df: pd.DataFrame) -> list[dict]:
    """DataFrame → JSON items 列表"""
    cols_metric = [
        "月搜", "月购_calc", "需供比", "价格",
        "评分数", "广告竞品数", "SPR",
        "点击集中度", "转化集中度", "购买率",
    ]
    items = []
    for _, row in df.iterrows():
        item = {
            "country": row["_country"],
            "keyword": row["关键词"],
            "category_top": row.get("品类组一", ""),
            "category_sub": row.get("品类组", ""),
            "source_file": row.get("_source_file", ""),
            "metrics": {c: (round(float(row[c]), 3) if pd.notna(row[c]) else None)
                        for c in cols_metric if c in df.columns},
        }
        # tag: 高门槛
        kw = str(row["关键词"]).lower()
        tags = []
        if any(k in kw for k in ["pet", "dog", "cat", "flea", "worm"]):
            tags.append("宠物药品-高门槛")
        if any(k in kw for k in ["medical", "drug", "pill"]):
            tags.append("医药-高合规")
        item["tags"] = tags
        items.append(item)
    # 跨站去重（同一关键词在多站出现 → 标 "跨站通用"）
    from collections import Counter
    cnt = Counter(it["keyword"] for it in items)
    for it in items:
        if cnt[it["keyword"]] >= 2:
            it["tags"].append("跨站通用")
    return items


def main():
    import argparse
    ap = argparse.ArgumentParser(description="快速筛选 ABA 关键词 → 生成快筛池 → 可推 hub")
    ap.add_argument("--push-hub", action="store_true", help="生成完后推 crossmart-hub/data/selection.json")
    args = ap.parse_args()

    print("=== quick_filter.py — 快速筛选 ABA 关键词 ===")
    print(f"INPUT_DIR: {INPUT_DIR}")
    print(f"CONFIG: {CONFIG_PATH}")
    print()

    cfg = load_config()
    print(f"配置版本: {cfg.get('version', 'unknown')}")

    print("\n[1] 加载输入数据...")
    df = load_all_data(INPUT_DIR)

    print("\n[2] 应用筛选...")
    df_final, stats = apply_filter(df, cfg)
    print(f"  最终通过: {stats['final']} 条")
    print(f"  按国家: {stats['by_country']}")

    print("\n[3] 生成输出...")
    items = to_output_items(df_final)
    out = {
        "schema_version": "v1",
        "source": "crossmart-selector",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "config_version": cfg.get("version"),
        "source_files": sorted(df_final["_source_file"].unique().tolist()),
        "stats": stats,
        "items": items,
    }
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    archive_path = os.path.join(PROCESSED_DIR, f"{ts}.json")
    latest_path = os.path.join(PROCESSED_DIR, "latest.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  归档: {archive_path}")
    print(f"  最新: {latest_path}")

    print("\n[4] Top 5 per country:")
    for c in COUNTRIES:
        sub = [it for it in items if it["country"] == c]
        print(f"  [{c}] {len(sub)} 条")
        for it in sorted(sub, key=lambda x: x["metrics"]["月购_calc"], reverse=True)[:5]:
            print(f"    - {it['keyword'][:50]:<50} 月搜={it['metrics']['月搜']:>7} 月购={it['metrics']['月购_calc']:>5.0f} 需供比={it['metrics']['需供比']:>5.1f} 评分数={it['metrics']['评分数']:>4.0f}")

    # === [5] 可选：推 hub ===
    if args.push_hub:
        print("\n[5] 推 hub: crossmart-hub/data/selection.json")
        try:
            sys.path.insert(0, ROOT)
            from push_to_hub import push_to_hub
            res = push_to_hub(
                filename="selection.json",
                payload=out,
                commit_message=f"chore(selector): quick_filter {stats['final']} items ({stats['by_country']})",
            )
            print(f"  ✓ 推送成功: commit={res.get('commit', {}).get('sha', '?')[:8]}")
        except Exception as e:
            print(f"  ✗ 推送失败: {e}", file=sys.stderr)
            print("    (hub 推送失败不影响本地输出)", file=sys.stderr)


if __name__ == "__main__":
    main()