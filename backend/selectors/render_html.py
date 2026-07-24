"""
render_html.py — Part B 末端：strategy.json → strategy.html
=============================================================

输入 : backend/processed/strategy/latest.json
输出 : frontend/data/strategy.html  (单文件 HTML，浏览器直接打开)

特性：
- 自包含：CSS / JS 全内嵌，离线打开即可
- 4 桶 Tab 切换
- 关键词 / 国家搜索过滤
- 列头点击排序（升降序）
- 摘要卡片（每桶数量 + 总计）
- 无外部依赖（vanilla JS，零 CDN）

使用：
  python backend/selectors/render_html.py
"""
from __future__ import annotations
import os
import sys
import json
import html
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY_LATEST = os.path.join(ROOT, "processed", "strategy", "latest.json")
HTML_OUT = os.path.join(os.path.dirname(ROOT), "frontend", "data", "strategy.html")

# 桶的固定顺序
BUCKET_ORDER = ["品牌创新", "newrelease", "模仿跟风", "老款延伸"]
BUCKET_TIER = {"品牌创新": "🟢", "newrelease": "🟡", "模仿跟风": "🟡", "老款延伸": "🟡"}


def render_table(bucket_name: str, items: list[dict]) -> str:
    """单个桶的表格 HTML"""
    rows = []
    for it in items:
        m = it["metrics"]
        yg = m.get("月购_calc") or 0
        xgb = m.get("需供比") or 0
        pfs = m.get("评分数") or 0
        spr = m.get("SPR") or 0
        ad = m.get("广告竞品数") or 0
        price = m.get("价格") or 0
        ps = it.get("priority_score") or 0
        kw = html.escape(it.get("keyword", "") or "")
        c = html.escape(it.get("country", "") or "")
        t = html.escape(it.get("tier_from_part_A", "") or "")
        rows.append(
            f'<tr data-kw="{kw.lower()}" data-country="{c.lower()}">'
            f'<td>{c}</td>'
            f'<td class="kw">{kw}</td>'
            f'<td>{t}</td>'
            f'<td class="num">{yg:.0f}</td>'
            f'<td class="num">{xgb:.1f}</td>'
            f'<td class="num">{pfs:.0f}</td>'
            f'<td class="num">{spr:.0f}</td>'
            f'<td class="num">{ad:.0f}</td>'
            f'<td class="num">{price:.2f}</td>'
            f'<td class="num">{ps:.1f}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data" data-bucket="{bucket_name}">'
        f'<thead><tr>'
        f'<th data-col="country" data-type="str">国</th>'
        f'<th data-col="keyword" data-type="str">关键词</th>'
        f'<th data-col="tier" data-type="str">tier</th>'
        f'<th data-col="yg" data-type="num">月购</th>'
        f'<th data-col="xgb" data-type="num">需供</th>'
        f'<th data-col="pfs" data-type="num">评分</th>'
        f'<th data-col="spr" data-type="num">SPR</th>'
        f'<th data-col="ad" data-type="num">广告竞品</th>'
        f'<th data-col="price" data-type="num">价</th>'
        f'<th data-col="score" data-type="num">score</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows) if rows else "<tr><td colspan=10 class=empty>（无）</td></tr>"}'
        f'</tbody></table>'
    )


def render_html(strategy: dict) -> str:
    """生成完整 HTML 字符串"""
    buckets = strategy.get("buckets", {})
    stats = strategy.get("stats", {})
    generated = strategy.get("generated_at", "")

    # 摘要卡片
    summary_cards = []
    total = 0
    for name in BUCKET_ORDER:
        b = buckets.get(name, {})
        cnt = b.get("count", 0)
        total += cnt
        tier = BUCKET_TIER.get(name, "")
        summary_cards.append(
            f'<div class="card" data-bucket-target="{name}">'
            f'<div class="card-tier">{tier}</div>'
            f'<div class="card-name">{name}</div>'
            f'<div class="card-count">{cnt}</div>'
            f'<div class="card-rule">{html.escape(b.get("rule", ""))}</div>'
            f'</div>'
        )
    summary_cards.append(
        f'<div class="card card-total">'
        f'<div class="card-tier">📊</div>'
        f'<div class="card-name">合计</div>'
        f'<div class="card-count">{total}</div>'
        f'<div class="card-rule">入桶 {stats.get("in_buckets", 0)} / 候选 {stats.get("eligible", 0)}</div>'
        f'</div>'
    )

    # 桶 Tab + 表格
    tabs = []
    tables = []
    for name in BUCKET_ORDER:
        b = buckets.get(name, {})
        cnt = b.get("count", 0)
        active = " active" if name == BUCKET_ORDER[1] else ""  # 默认显示 newrelease
        tabs.append(
            f'<button class="tab{active}" data-bucket="{name}">'
            f'{BUCKET_TIER.get(name, "")} {name} ({cnt})'
            f'</button>'
        )
        display = "block" if name == BUCKET_ORDER[1] else "none"
        tables.append(
            f'<div class="bucket-panel" data-bucket="{name}" style="display:{display}">'
            f'{render_table(name, b.get("items", []))}'
            f'</div>'
        )

    # 桶详细动作模板（展开区）
    bucket_details = []
    for name in BUCKET_ORDER:
        b = buckets.get(name, {})
        items = b.get("items", [])
        if not items:
            continue
        # 取第一项的 action_template（同一桶共用）
        tmpl = items[0].get("action_template", {}) if items else {}
        priority = tmpl.get("priority", "")
        actions = tmpl.get("核心动作", [])
        risk = tmpl.get("风险提示", "")
        roi = tmpl.get("预期 ROI", "")
        actions_html = "".join(f"<li>{html.escape(a)}</li>" for a in actions)
        bucket_details.append(
            f'<details class="bucket-detail" data-bucket="{name}">'
            f'<summary>📌 {name} · 推品动作模板（{priority}）</summary>'
            f'<ul>{actions_html}</ul>'
            f'<p><strong>风险提示</strong>: {html.escape(risk)}</p>'
            f'<p><strong>预期 ROI</strong>: {html.escape(roi)}</p>'
            f'</details>'
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>CrossMart 选品看板 · {html.escape(generated)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    margin: 0; padding: 16px 24px; background: #f5f6f8; color: #222;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px 0; }}
  .meta {{ color: #888; font-size: 12px; margin-bottom: 16px; }}
  .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }}
  .card {{
    background: #fff; border-radius: 8px; padding: 12px 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-left: 4px solid #ddd;
  }}
  .card-total {{ border-left-color: #6c5ce7; }}
  .card[data-bucket-target="品牌创新"] {{ border-left-color: #2ecc71; }}
  .card[data-bucket-target="newrelease"] {{ border-left-color: #f1c40f; }}
  .card[data-bucket-target="模仿跟风"] {{ border-left-color: #e67e22; }}
  .card[data-bucket-target="老款延伸"] {{ border-left-color: #9b59b6; }}
  .card-tier {{ font-size: 18px; }}
  .card-name {{ font-size: 13px; color: #666; margin-top: 2px; }}
  .card-count {{ font-size: 28px; font-weight: 600; margin: 4px 0; }}
  .card-rule {{ font-size: 11px; color: #999; }}

  .controls {{ display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }}
  .controls input {{
    flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px;
    font-size: 14px; background: #fff;
  }}
  .controls .hint {{ font-size: 11px; color: #888; }}

  .tabs {{ display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 2px solid #eee; }}
  .tab {{
    background: transparent; border: none; padding: 10px 16px; cursor: pointer;
    font-size: 14px; color: #666; border-bottom: 2px solid transparent;
    margin-bottom: -2px;
  }}
  .tab.active {{ color: #2c3e50; border-bottom-color: #3498db; font-weight: 600; }}
  .tab:hover {{ background: #f0f0f0; }}

  .bucket-detail {{
    background: #fffbf0; border: 1px solid #ffe082; border-radius: 6px;
    padding: 8px 12px; margin-bottom: 12px; font-size: 13px;
  }}
  .bucket-detail summary {{ cursor: pointer; font-weight: 600; }}
  .bucket-detail ul {{ margin: 6px 0; padding-left: 20px; }}
  .bucket-detail p {{ margin: 4px 0; font-size: 12px; color: #555; }}

  table.data {{
    width: 100%; border-collapse: collapse; background: #fff;
    border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    font-size: 13px;
  }}
  table.data th {{
    background: #fafafa; padding: 10px 8px; text-align: left;
    border-bottom: 2px solid #eee; cursor: pointer; user-select: none;
    font-weight: 600; color: #444; white-space: nowrap;
  }}
  table.data th:hover {{ background: #f0f0f0; }}
  table.data th::after {{ content: ' ⇅'; opacity: 0.3; font-size: 10px; }}
  table.data th.sort-asc::after {{ content: ' ▲'; opacity: 1; color: #3498db; }}
  table.data th.sort-desc::after {{ content: ' ▼'; opacity: 1; color: #3498db; }}
  table.data td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; }}
  table.data td.kw {{ font-family: ui-monospace, "Cascadia Code", "Consolas", monospace; font-size: 12px; }}
  table.data td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.data tr:hover {{ background: #f8fbff; }}
  table.data td.empty {{ text-align: center; color: #999; padding: 20px; }}

  footer {{ margin-top: 24px; padding-top: 12px; border-top: 1px solid #eee; color: #888; font-size: 11px; }}
</style>
</head>
<body>

<h1>🎯 CrossMart 选品看板</h1>
<div class="meta">生成时间: {html.escape(generated)} · 输入: strategy.json · 砍档未显示（看 triage.json）</div>

<div class="summary">
  {"".join(summary_cards)}
</div>

<div class="controls">
  <input id="search" type="text" placeholder="搜索关键词或国家 (例: dog / DE / US)...">
  <span class="hint">点击列头排序 · 点击 Tab 切桶 · 点击卡片跳桶</span>
</div>

<div class="tabs">
  {"".join(tabs)}
</div>

{"".join(bucket_details)}

{"".join(tables)}

<footer>
  数据源: <code>frontend/data/strategy.json</code> ·
  由 <code>backend/selectors/render_html.py</code> 生成 ·
  配套文件: <code>triage.json</code> (3 档分档) · <code>quick-pick.json</code> (候选池)
</footer>

<script>
(function() {{
  // === Tab 切换 ===
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.bucket-panel');
  const details = document.querySelectorAll('.bucket-detail');
  function showBucket(name) {{
    tabs.forEach(t => t.classList.toggle('active', t.dataset.bucket === name));
    panels.forEach(p => p.style.display = p.dataset.bucket === name ? 'block' : 'none');
    details.forEach(d => d.style.display = d.dataset.bucket === name ? 'block' : 'none');
    if (typeof applySearch === 'function') applySearch();
  }}
  tabs.forEach(t => t.addEventListener('click', () => showBucket(t.dataset.bucket)));

  // === 摘要卡片点击跳桶 ===
  document.querySelectorAll('.card[data-bucket-target]').forEach(c => {{
    c.addEventListener('click', () => showBucket(c.dataset.bucketTarget));
    c.style.cursor = 'pointer';
  }});

  // === 搜索过滤 ===
  const search = document.getElementById('search');
  function applySearch() {{
    const q = (search.value || '').toLowerCase().trim();
    document.querySelectorAll('table.data tbody tr').forEach(tr => {{
      const visiblePanel = tr.closest('.bucket-panel').style.display !== 'none';
      if (!visiblePanel) {{ tr.style.display = 'none'; return; }}
      if (!q) {{ tr.style.display = ''; return; }}
      const kw = tr.dataset.kw || '';
      const c = tr.dataset.country || '';
      tr.style.display = (kw.includes(q) || c.includes(q)) ? '' : 'none';
    }});
  }}
  search.addEventListener('input', applySearch);

  // === 列头排序 ===
  document.querySelectorAll('table.data th').forEach(th => {{
    th.addEventListener('click', () => {{
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      if (!rows.length || rows[0].querySelector('td.empty')) return;
      const idx = Array.from(th.parentNode.children).indexOf(th);
      const type = th.dataset.type;
      const asc = !th.classList.contains('sort-asc');
      table.querySelectorAll('th').forEach(x => x.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(asc ? 'sort-asc' : 'sort-desc');
      rows.sort((a, b) => {{
        const av = a.children[idx].innerText.trim();
        const bv = b.children[idx].innerText.trim();
        if (type === 'num') {{
          return asc ? parseFloat(av) - parseFloat(bv) : parseFloat(bv) - parseFloat(av);
        }}
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});
}})();
</script>

</body>
</html>
"""
    return html_doc


def main():
    print("=== render_html.py — strategy.json → strategy.html ===")
    print(f"读取: {STRATEGY_LATEST}")

    if not os.path.exists(STRATEGY_LATEST):
        print(f"[ERR] 找不到 {STRATEGY_LATEST}，请先跑 strategy_router.py", file=sys.stderr)
        sys.exit(1)

    with open(STRATEGY_LATEST, "r", encoding="utf-8") as f:
        strategy = json.load(f)

    html_doc = render_html(strategy)

    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)

    # 顺便归档一份带时间戳的（方便回看）
    ts_dir = os.path.join(os.path.dirname(ROOT), "frontend", "data", "_archive")
    os.makedirs(ts_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    archive = os.path.join(ts_dir, f"strategy_{ts}.html")
    with open(archive, "w", encoding="utf-8") as f:
        f.write(html_doc)

    size_kb = len(html_doc.encode("utf-8")) / 1024
    print(f"\n✓ 生成 {HTML_OUT}")
    print(f"  大小: {size_kb:.1f} KB")
    print(f"  归档: {archive}")
    print(f"\n直接双击 HTML 文件用浏览器打开即可。")


if __name__ == "__main__":
    main()