#!/usr/bin/env python3
"""Build the third final visualization: counties in the top 25% for 0-3 core measures."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path

from build_county_map import (
    BOUNDARY_ZIP,
    DATA_ROOT,
    DATA_PATH,
    ROOT,
    projected_paths,
    quantile,
    read_boundaries,
    sha256,
)


OUTPUT_DIR = ROOT / "03_visualisations/final/interactive_overlap"
STATIC_SVG = ROOT / "03_visualisations/final/upper_quartile_overlap_map.svg"
VALIDATION_PATH = ROOT / "02_analysis/outputs/final_overlap_validation.json"

METRICS = {
    "diabetes": {"column": "DIABETES_AdjPrev", "label": "Diabetes"},
    "obesity": {"column": "OBESITY_AdjPrev", "label": "Obesity"},
    "inactivity": {"column": "LPA_AdjPrev", "label": "Physical inactivity"},
}

CATEGORY_COLORS = {
    0: "#e8edf2",
    1: "#b9d6e8",
    2: "#4f91bd",
    3: "#d95f02",
}
MISSING_COLOR = "#f4f5f6"



def full_county_names() -> dict[str, str]:
    """Official names with the legal type (County, Parish, city, Borough...)."""
    path = DATA_ROOT / "reference/places_to_2023_gazetteer.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["CountyFIPS"].zfill(5): row["census_name"] for row in csv.DictReader(handle)}


FULL_NAMES = full_county_names()

def number(value: str) -> float | None:
    value = value.strip()
    return None if not value else float(value)


def read_records() -> tuple[dict[str, dict], dict[str, float], Counter]:
    records: dict[str, dict] = {}
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            item = {
                "fips": row["CountyFIPS"].zfill(5),
                "county": FULL_NAMES.get(row["CountyFIPS"].zfill(5), row["derived__CountyName_display"]),
                "state": row["StateDesc"],
                "abbr": row["StateAbbr"],
            }
            for key, spec in METRICS.items():
                item[key] = number(row[spec["column"]])
            records[item["fips"]] = item

    complete = [
        row for row in records.values() if all(row[key] is not None for key in METRICS)
    ]
    thresholds = {
        key: quantile(sorted(row[key] for row in complete), 0.75) for key in METRICS
    }
    counts: Counter = Counter()
    for row in records.values():
        if all(row[key] is not None for key in METRICS):
            row["flags"] = {
                key: row[key] >= thresholds[key] for key in METRICS
            }
            row["category"] = sum(row["flags"].values())
            counts[row["category"]] += 1
        else:
            row["flags"] = None
            row["category"] = None
    return records, thresholds, counts


def path_markup(paths: dict[str, str], records: dict[str, dict], interactive: bool) -> str:
    pieces = []
    for fips in sorted(paths):
        row = records.get(fips)
        category = row["category"] if row else None
        fill = CATEGORY_COLORS[category] if category is not None else MISSING_COLOR
        category_value = str(category) if category is not None else "missing"
        label = (
            f'{row["county"]}, {row["state"]}'
            if row
            else f"County FIPS {fips}; no PLACES row"
        )
        tab = ' tabindex="0"' if interactive else ""
        pieces.append(
            f'<path class="county" id="county-{fips}" data-fips="{fips}" '
            f'data-category="{category_value}" d="{paths[fips]}" fill="{fill}" '
            f'aria-label="{html.escape(label, quote=True)}"{tab}/>'
        )
    return "\n".join(pieces)


def bars_markup(counts: Counter, *, interactive: bool = False) -> str:
    max_count = max(counts.values())
    labels = {0: "0 measures", 1: "1 measure", 2: "2 measures", 3: "All 3"}
    pieces = []
    for category in range(4):
        y = 365 + category * 64
        width = 190 * counts[category] / max_count
        role = ' role="button" tabindex="0"' if interactive else ""
        pieces.append(
            f'<g class="bar-row" data-filter="{category}"{role}>'
            f'<text x="1090" y="{y}" class="bar-label">{labels[category]}</text>'
            f'<rect x="1090" y="{y + 12}" width="190" height="20" rx="4" fill="#eef2f6"/>'
            f'<rect x="1090" y="{y + 12}" width="{width:.1f}" height="20" rx="4" fill="{CATEGORY_COLORS[category]}"/>'
            f'<text x="1295" y="{y + 28}" class="bar-value">{counts[category]:,}</text></g>'
        )
    return "".join(pieces)


def static_svg(
    paths: dict[str, str], records: dict[str, dict], thresholds: dict[str, float], counts: Counter
) -> str:
    total = sum(counts.values())
    joint_pct = counts[3] / total * 100
    legend = "".join(
        f'<rect x="1088" y="{245 + category * 31}" width="22" height="18" rx="3" fill="{CATEGORY_COLORS[category]}"/>'
        f'<text x="1120" y="{259 + category * 31}" class="legend">{category if category < 3 else "All 3"} measure{"s" if category != 1 else ""} in the top 25%</text>'
        for category in range(4)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800" role="img" aria-labelledby="title desc">
<title id="title">377 U.S. counties are in the top 25% for all three measures</title>
<desc id="desc">County map showing how many of three model-based estimates are at or above their respective 75th percentile. Orange counties meet all three descriptive thresholds.</desc>
<rect width="1400" height="800" fill="#f4f7fa"/>
<text x="48" y="37" class="kicker">CDC PLACES · WHERE PROBLEMS OVERLAP</text>
<text x="48" y="73" class="title">377 counties are in the top 25% for all three measures</text>
<text x="48" y="100" class="subtitle">Diabetes ≥ {thresholds["diabetes"]:.1f}% · Obesity ≥ {thresholds["obesity"]:.1f}% · Physical inactivity ≥ {thresholds["inactivity"]:.1f}%</text>
<rect x="34" y="120" width="1000" height="650" rx="16" fill="#fff" stroke="#dce4ec"/>
<g transform="translate(16,126) scale(.86)">{path_markup(paths, records, interactive=False)}</g>
<text x="86" y="630" class="inset">Alaska</text><text x="335" y="654" class="inset">Hawaii</text>
<text x="600" y="720" class="note">Gray = incomplete estimates; county area does not represent population.</text>
<rect x="1052" y="120" width="314" height="650" rx="16" fill="#fff" stroke="#dce4ec"/>
<text x="1088" y="160" class="panel-label">TOP 25% ON ALL THREE</text>
<text x="1088" y="211" class="stat">{counts[3]:,}</text><text x="1190" y="210" class="stat-small">counties</text>
<text x="1088" y="235" class="note">{joint_pct:.1f}% of {total:,} complete counties</text>
{legend}<line x1="1088" y1="350" x2="1332" y2="350" stroke="#dce4ec"/>
{bars_markup(counts)}
<line x1="1088" y1="640" x2="1332" y2="640" stroke="#dce4ec"/>
<text x="1088" y="672" class="note">The top-25% cut-off is a descriptive</text><text x="1088" y="691" class="note">analysis threshold, not a clinical cutoff</text><text x="1088" y="710" class="note">or an overall county health ranking.</text>
<style>
text{{font-family:Inter,Arial,sans-serif;fill:#172331}}.kicker{{font-size:13px;font-weight:800;letter-spacing:1.3px;fill:#526b82}}.title{{font-size:31px;font-weight:800}}.subtitle{{font-size:15px;fill:#5b6c7e}}
.county{{stroke:#fff;stroke-width:.45;fill-rule:evenodd}}.panel-label{{font-size:11px;font-weight:850;letter-spacing:1.2px;fill:#65788a}}.stat{{font-size:42px;font-weight:850;fill:#d95f02}}.stat-small{{font-size:17px;font-weight:750}}.note{{font-size:12px;fill:#607386}}.legend{{font-size:12px;fill:#344b60}}.inset{{font-size:14px;font-weight:800}}.bar-label{{font-size:12px;font-weight:750}}.bar-value{{font-size:12px;font-weight:800}}
</style></svg>'''


HTML_TEMPLATE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Where problems overlap — CDC PLACES</title><style>
:root{--ink:#172331;--muted:#5b6c7e;--line:#dce4ec;--bg:#f3f6fa;--panel:#fff;--accent:#153e61;--orange:#d95f02;--focus:#f6a800}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.app{min-height:100vh;max-width:1500px;margin:auto;padding:20px 28px 16px;display:grid;grid-template-rows:auto auto 1fr auto;gap:13px}.kicker{font-size:12px;font-weight:850;letter-spacing:.12em;color:#526b82}.title{font-size:clamp(25px,2.35vw,37px);line-height:1.08;margin:5px 0 6px;letter-spacing:-.025em}.subtitle{font-size:14px;color:var(--muted)}.filters{display:flex;gap:8px;flex-wrap:wrap}.filter{border:1px solid #bcc9d5;border-radius:999px;background:#fff;padding:8px 13px;font-size:13px;font-weight:780;color:#294158;cursor:pointer}.filter[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}.filter[data-filter="3"][aria-pressed="true"]{background:var(--orange);border-color:var(--orange)}.filter:focus-visible,.county:focus-visible,.bar-row:focus-visible{outline:3px solid var(--focus);outline-offset:2px}.workspace{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 285px;gap:14px}.map-card,.side{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:0 9px 28px rgba(42,61,79,.07)}.map-card{position:relative;min-height:0;overflow:hidden;padding:5px}.map-card svg{display:block;width:100%;height:100%;min-height:465px}.county{stroke:#fff;stroke-width:.48;fill-rule:evenodd;cursor:pointer;transition:opacity .2s,stroke-width .15s}.county.is-dimmed{opacity:.09}.county.is-selected,.county:hover{opacity:1;stroke:#111827;stroke-width:2.1;paint-order:stroke;filter:drop-shadow(0 1px 1px rgba(0,0,0,.22))}.side{padding:18px;display:flex;flex-direction:column;gap:15px}.section-label{font-size:11px;font-weight:850;letter-spacing:.11em;color:#66788b}.hero{display:flex;align-items:baseline;gap:8px}.hero strong{font-size:42px;color:var(--orange)}.hero span{font-size:15px;font-weight:760}.hero-note{font-size:12px;color:var(--muted)}.legend{display:grid;gap:8px}.legend-item{display:flex;align-items:center;gap:8px;font-size:12px}.swatch{width:20px;height:15px;border-radius:3px}.bars{border-top:1px solid var(--line);padding-top:13px}.bar-row{margin:10px 0;cursor:pointer}.bar-head{display:flex;justify-content:space-between;font-size:12px;font-weight:760}.track{height:12px;background:#eef2f6;border-radius:4px;margin-top:5px;overflow:hidden}.bar{height:100%;border-radius:4px}.selection{border-top:1px solid var(--line);padding-top:13px;min-height:143px}.selection h2{font-size:18px;margin:5px 0 2px}.place,.empty,.method{font-size:12px;color:var(--muted);line-height:1.5}.metric-line{font-size:13px;margin-top:6px;display:flex;justify-content:space-between}.metric-line strong{font-size:14px}.status{font-weight:800;color:var(--orange)}.clear{border:0;background:none;color:#0c609f;font-weight:780;padding:7px 0;cursor:pointer}.method{margin-top:auto}.tooltip{position:fixed;z-index:10;pointer-events:none;background:#172331;color:#fff;border-radius:10px;padding:11px 13px;min-width:250px;box-shadow:0 12px 28px rgba(0,0,0,.22);opacity:0;transform:translate(12px,12px)}.tooltip.visible{opacity:1}.tooltip strong,.tooltip span{display:block}.tooltip span{font-size:12px;color:#d8e4ef;margin-top:4px}.inset-label{font-size:17px;font-weight:800;fill:#40566b}.map-note{font-size:13px;fill:#6a7b8c}footer{display:flex;justify-content:space-between;gap:16px;font-size:11px;color:var(--muted);line-height:1.4}footer p{margin:0;max-width:930px}@media(max-width:950px){.workspace{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr}.method{grid-column:1/-1}}@media(max-width:650px){.app{padding:15px}.side{display:flex}.map-card svg{min-height:380px}footer{flex-direction:column}}@media(prefers-reduced-motion:reduce){.county{transition:none}}
</style></head><body><main class="app"><header><div class="kicker">CDC PLACES · WHERE PROBLEMS OVERLAP</div><h1 class="title" id="headline">377 counties are in the top 25% for all three measures</h1><div class="subtitle">Diabetes ≥ @@DIABETES@@% · Obesity ≥ @@OBESITY@@% · Physical inactivity ≥ @@INACTIVITY@@% · top-25% cut-offs</div></header><nav class="filters" aria-label="Filter by number of top-25% measures">@@BUTTONS@@</nav><section class="workspace"><div class="map-card"><svg viewBox="0 0 1200 700" role="img" aria-labelledby="map-title map-desc"><title id="map-title">Counties in the top 25% for 0–3 measures</title><desc id="map-desc">Orange counties are in the top 25% for all three measures.</desc><g id="counties">@@PATHS@@</g><text x="82" y="552" class="inset-label">Alaska</text><text x="370" y="580" class="inset-label">Hawaii</text><text x="760" y="657" class="map-note">County area does not represent population.</text></svg><div class="tooltip" id="tooltip" role="status"></div></div><aside class="side"><div><div class="section-label">TOP 25% ON ALL THREE</div><div class="hero"><strong>@@JOINT_COUNT@@</strong><span>counties</span></div><div class="hero-note">@@JOINT_PCT@@% of @@TOTAL@@ counties with all three estimates</div></div><div class="legend">@@LEGEND@@</div><div class="bars"><div class="section-label">COUNTY DISTRIBUTION</div>@@BARS@@</div><div class="selection" id="selection"><div class="section-label">SELECTED COUNTY</div><p class="empty">Hover for details. Click a county to keep it highlighted.</p></div><p class="method"><strong>How to read:</strong> orange counties are among the highest 25% of U.S. counties for diabetes, obesity and physical inactivity at the same time. The cut-offs are simply the 75th percentile of each measure, not medical thresholds, and this is not a health ranking.</p></aside></section><footer><p><strong>Source:</strong> CDC PLACES 2025 release; 2023 estimates, adjusted for age. Kentucky and Pennsylvania are not published for these measures.</p><p>Cut-offs are calculated across the 2,956 counties with all three estimates.</p></footer></main><script>
const records=@@DATA@@,counts=@@COUNTS@@,tooltip=document.getElementById('tooltip'),selection=document.getElementById('selection'),paths=[...document.querySelectorAll('.county')];let current='all',selected=null;const thresholds={diabetes:@@DIABETES@@,obesity:@@OBESITY@@,inactivity:@@INACTIVITY@@};
function label(category){return category==null?'Incomplete estimates':category===3?'Top 25% on all 3 measures':`Top 25% on ${category} measure${category===1?'':'s'}`}
function showTip(row,x,y){if(!row){tooltip.innerHTML='<strong>No PLACES data row</strong>';tooltip.classList.add('visible');return}const values=row.category==null?'<span>Required 2023 estimates are incomplete.</span>':`<span>Diabetes: ${row.diabetes.toFixed(1)}% ${row.flags.diabetes?'✓':''}</span><span>Obesity: ${row.obesity.toFixed(1)}% ${row.flags.obesity?'✓':''}</span><span>Inactivity: ${row.inactivity.toFixed(1)}% ${row.flags.inactivity?'✓':''}</span>`;tooltip.innerHTML=`<strong>${row.county}</strong><span>${row.state} · ${label(row.category)}</span>${values}`;tooltip.style.left=`${Math.min(x,window.innerWidth-280)}px`;tooltip.style.top=`${Math.min(y,window.innerHeight-155)}px`;tooltip.classList.add('visible')}
function metricLine(name,value,flag){return `<div class="metric-line"><span>${name}</span><strong>${value.toFixed(1)}% ${flag?'<span class="status">✓</span>':''}</strong></div>`}
function renderSelection(row){if(!row){selection.innerHTML='<div class="section-label">SELECTED COUNTY</div><p class="empty">No PLACES data row is available for this county boundary.</p><button class="clear" id="clear">Clear selection</button>';document.getElementById('clear').onclick=clearSelection;return}let details=row.category==null?'<p class="empty">The three required estimates are incomplete.</p>':metricLine('Diabetes',row.diabetes,row.flags.diabetes)+metricLine('Obesity',row.obesity,row.flags.obesity)+metricLine('Physical inactivity',row.inactivity,row.flags.inactivity);selection.innerHTML=`<div class="section-label">SELECTED COUNTY</div><h2>${row.county}</h2><div class="place">${row.state} · FIPS ${row.fips}</div><div class="place">${label(row.category)}</div>${details}<button class="clear" id="clear">Clear selection</button>`;document.getElementById('clear').onclick=clearSelection}
function clearSelection(){selected=null;paths.forEach(p=>p.classList.remove('is-selected'));selection.innerHTML='<div class="section-label">SELECTED COUNTY</div><p class="empty">Hover for details. Click a county to keep it highlighted.</p>'}
function setFilter(filter){current=filter;tooltip.classList.remove('visible');document.querySelectorAll('.filter').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===filter)));paths.forEach(p=>p.classList.toggle('is-dimmed',filter!=='all'&&p.dataset.category!==filter));document.querySelectorAll('.bar-row').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));document.getElementById('headline').textContent=filter==='all'?'377 counties are in the top 25% for all three measures':filter==='3'?'377 counties are in the top 25% for all three measures':`${counts[filter].toLocaleString()} counties meet exactly ${filter} top-25% measure${filter==='1'?'':'s'}`}
paths.forEach(path=>{const row=records[path.dataset.fips]||null;path.addEventListener('pointermove',e=>showTip(row,e.clientX,e.clientY));path.addEventListener('pointerleave',()=>tooltip.classList.remove('visible'));path.addEventListener('focus',()=>{const r=path.getBoundingClientRect();showTip(row,r.left+r.width/2,r.top+r.height/2)});path.addEventListener('blur',()=>tooltip.classList.remove('visible'));path.addEventListener('click',()=>{selected=path.dataset.fips;paths.forEach(p=>p.classList.toggle('is-selected',p===path));renderSelection(row)})});document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>setFilter(b.dataset.filter)));document.querySelectorAll('.bar-row').forEach(b=>{b.addEventListener('click',()=>setFilter(b.dataset.filter));b.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setFilter(b.dataset.filter)}})});setFilter('all');
</script></body></html>'''


def interactive_html(
    paths: dict[str, str], records: dict[str, dict], thresholds: dict[str, float], counts: Counter
) -> str:
    total = sum(counts.values())
    buttons = '<button class="filter" data-filter="all" aria-pressed="false">All complete counties</button>' + "".join(
        f'<button class="filter" data-filter="{category}" aria-pressed="false">'
        f'{"All 3" if category == 3 else str(category)} in top 25%</button>'
        for category in range(4)
    )
    legend = "".join(
        f'<div class="legend-item"><span class="swatch" style="background:{CATEGORY_COLORS[category]}"></span>'
        f'<span>{"All 3" if category == 3 else category} measure{"s" if category != 1 else ""} in the top 25%</span></div>'
        for category in range(4)
    )
    max_count = max(counts.values())
    bars = "".join(
        f'<div class="bar-row" data-filter="{category}" role="button" tabindex="0"><div class="bar-head"><span>{"All 3" if category == 3 else category} measure{"s" if category != 1 else ""}</span><span>{counts[category]:,}</span></div><div class="track"><div class="bar" style="width:{counts[category] / max_count * 100:.1f}%;background:{CATEGORY_COLORS[category]}"></div></div></div>'
        for category in range(4)
    )
    data = {fips: row for fips, row in records.items()}
    replacements = {
        "@@DIABETES@@": f'{thresholds["diabetes"]:.1f}',
        "@@OBESITY@@": f'{thresholds["obesity"]:.1f}',
        "@@INACTIVITY@@": f'{thresholds["inactivity"]:.1f}',
        "@@BUTTONS@@": buttons,
        "@@PATHS@@": path_markup(paths, records, interactive=True),
        "@@JOINT_COUNT@@": f'{counts[3]:,}',
        "@@JOINT_PCT@@": f'{counts[3] / total * 100:.1f}',
        "@@TOTAL@@": f'{total:,}',
        "@@LEGEND@@": legend,
        "@@BARS@@": bars,
        "@@DATA@@": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        "@@COUNTS@@": json.dumps({str(k): counts[k] for k in range(4)}),
    }
    result = HTML_TEMPLATE
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records, thresholds, counts = read_records()
    expected_thresholds = {"diabetes": 12.5, "obesity": 40.6, "inactivity": 30.5}
    expected_counts = {0: 1788, 1: 471, 2: 320, 3: 377}
    if thresholds != expected_thresholds:
        raise ValueError(f"Threshold mismatch: {thresholds}")
    if {key: counts[key] for key in range(4)} != expected_counts:
        raise ValueError(f"Overlap count mismatch: {counts}")

    boundaries = read_boundaries()
    state_fips = {fips[:2] for fips in records}
    boundaries = [feature for feature in boundaries if feature["state_fips"] in state_fips]
    boundary_fips = {feature["fips"] for feature in boundaries}
    record_fips = set(records)
    missing_boundaries = sorted(record_fips - boundary_fips)
    if missing_boundaries:
        raise ValueError(f"PLACES rows without a boundary: {missing_boundaries}")
    paths = projected_paths(boundaries, state_fips)

    STATIC_SVG.write_text(static_svg(paths, records, thresholds, counts), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(
        interactive_html(paths, records, thresholds, counts), encoding="utf-8"
    )
    validation = {
        "status": "PASS",
        "input": str(DATA_PATH.relative_to(ROOT)),
        "input_sha256": sha256(DATA_PATH),
        "boundary": str(BOUNDARY_ZIP.relative_to(ROOT)),
        "boundary_sha256": sha256(BOUNDARY_ZIP),
        "places_rows": len(records),
        "matched_places_rows": len(record_fips & boundary_fips),
        "complete_counties": sum(counts.values()),
        "thresholds": thresholds,
        "category_counts": {str(key): counts[key] for key in range(4)},
        "all_three_counties": counts[3],
        "all_three_percent": counts[3] / sum(counts.values()) * 100,
        "places_rows_without_boundary": missing_boundaries,
        "boundary_counties_without_places_row": sorted(boundary_fips - record_fips),
        "outputs": [
            str(STATIC_SVG.relative_to(ROOT)),
            str((OUTPUT_DIR / "index.html").relative_to(ROOT)),
        ],
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
