#!/usr/bin/env python3
"""Build the second final visualization: diabetes vs physical inactivity.

Outputs a presentation-ready SVG and a dependency-free interactive HTML page.
The analysis is descriptive and ecological; no causal claim is made.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / ("01_data" if (ROOT / "01_data").exists() else "data")
DATA_PATH = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
OUTPUT_DIR = ROOT / "03_visualisations/final/interactive_relationship"
STATIC_SVG = ROOT / "03_visualisations/final/diabetes_inactivity_relationship.svg"
VALIDATION_PATH = ROOT / "02_analysis/outputs/final_relationship_validation.json"

X_DOMAIN = (10.0, 50.0)
Y_DOMAIN = (5.0, 25.0)
PLOT = {"left": 92.0, "top": 48.0, "width": 1015.0, "height": 602.0}

REGION_STATES = {
    "Northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "Midwest": {"IN", "IL", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"},
    "South": {"DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"},
    "West": {"AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"},
}
REGION_COLORS = {
    "Northeast": "#0072B2",
    "Midwest": "#009E73",
    "South": "#D55E00",
    "West": "#CC79A7",
}


def number(value: str) -> float | None:
    value = value.strip()
    return None if not value else float(value)


def region_for(state: str) -> str:
    for region, states in REGION_STATES.items():
        if state in states:
            return region
    raise ValueError(f"No Census region mapping for state: {state}")


def read_data() -> list[dict]:
    records = []
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            diabetes = number(row["DIABETES_AdjPrev"])
            inactivity = number(row["LPA_AdjPrev"])
            if diabetes is None or inactivity is None:
                continue
            records.append(
                {
                    "fips": row["CountyFIPS"].zfill(5),
                    "county": row["derived__CountyName_display"],
                    "state": row["StateDesc"],
                    "abbr": row["StateAbbr"],
                    "region": region_for(row["StateAbbr"]),
                    "x": inactivity,
                    "xLow": number(row["derived__LPA_Adj95CI_Low"]),
                    "xHigh": number(row["derived__LPA_Adj95CI_High"]),
                    "y": diabetes,
                    "yLow": number(row["derived__DIABETES_Adj95CI_Low"]),
                    "yHigh": number(row["derived__DIABETES_Adj95CI_High"]),
                }
            )
    return records


def scale_x(value: float) -> float:
    return PLOT["left"] + (value - X_DOMAIN[0]) / (X_DOMAIN[1] - X_DOMAIN[0]) * PLOT["width"]


def scale_y(value: float) -> float:
    return PLOT["top"] + (Y_DOMAIN[1] - value) / (Y_DOMAIN[1] - Y_DOMAIN[0]) * PLOT["height"]


def pearson(records: list[dict]) -> float:
    xs = [row["x"] for row in records]
    ys = [row["y"] for row in records]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
    )
    return numerator / denominator


def lowess(records: list[dict], span: float = 0.25, evaluations: int = 120) -> list[tuple[float, float]]:
    points = sorted((row["x"], row["y"]) for row in records)
    neighbour_count = max(12, math.ceil(len(points) * span))
    grid_min, grid_max = min(x for x, _ in points), max(x for x, _ in points)
    result = []
    for step in range(evaluations):
        x0 = grid_min + (grid_max - grid_min) * step / (evaluations - 1)
        distances = sorted(abs(x - x0) for x, _ in points)
        bandwidth = max(distances[min(neighbour_count - 1, len(distances) - 1)], 1e-9)
        sw = sx = sy = sxx = sxy = 0.0
        for x, y in points:
            ratio = abs(x - x0) / bandwidth
            if ratio >= 1:
                continue
            weight = (1 - ratio**3) ** 3
            dx = x - x0
            sw += weight
            sx += weight * dx
            sy += weight * y
            sxx += weight * dx * dx
            sxy += weight * dx * y
        denominator = sw * sxx - sx * sx
        fitted = sy / sw if abs(denominator) < 1e-12 else (sy * sxx - sx * sxy) / denominator
        result.append((x0, fitted))
    return result


def trend_path(points: list[tuple[float, float]]) -> str:
    commands = []
    for index, (x, y) in enumerate(points):
        command = "M" if index == 0 else "L"
        commands.append(f"{command}{scale_x(x):.2f},{scale_y(y):.2f}")
    return "".join(commands)


def subset_statistics(records: list[dict]) -> dict[str, dict]:
    groups = {"All counties": records}
    groups.update(
        {
            region: [row for row in records if row["region"] == region]
            for region in REGION_STATES
        }
    )
    result = {}
    for label, rows in groups.items():
        correlation = pearson(rows)
        result[label] = {
            "n": len(rows),
            "pearson": correlation,
            "rSquared": correlation**2,
            "xMedian": statistics.median(row["x"] for row in rows),
            "yMedian": statistics.median(row["y"] for row in rows),
            "trend": trend_path(lowess(rows)),
        }
    return result


def axes_markup() -> str:
    lines = []
    bottom = PLOT["top"] + PLOT["height"]
    right = PLOT["left"] + PLOT["width"]
    for tick in range(10, 51, 5):
        x = scale_x(tick)
        lines.append(f'<line x1="{x:.1f}" y1="{PLOT["top"]}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
        lines.append(f'<text x="{x:.1f}" y="{bottom + 29}" text-anchor="middle" class="tick">{tick}%</text>')
    for tick in range(5, 26, 5):
        y = scale_y(tick)
        lines.append(f'<line x1="{PLOT["left"]}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="grid"/>')
        lines.append(f'<text x="{PLOT["left"] - 15}" y="{y + 5:.1f}" text-anchor="end" class="tick">{tick}%</text>')
    lines.append(f'<rect x="{PLOT["left"]}" y="{PLOT["top"]}" width="{PLOT["width"]}" height="{PLOT["height"]}" class="frame"/>')
    lines.append(f'<text x="{PLOT["left"] + PLOT["width"] / 2:.1f}" y="{bottom + 68}" text-anchor="middle" class="axis-title">No leisure-time physical activity, age-adjusted prevalence</text>')
    lines.append(f'<text x="28" y="{PLOT["top"] + PLOT["height"] / 2:.1f}" transform="rotate(-90 28,{PLOT["top"] + PLOT["height"] / 2:.1f})" text-anchor="middle" class="axis-title">Diagnosed diabetes, age-adjusted prevalence</text>')
    return "\n".join(lines)


def point_markup(records: list[dict], interactive: bool = True) -> str:
    pieces = []
    for row in records:
        label = html.escape(f'{row["county"]} County, {row["state"]}', quote=True)
        tab = ' tabindex="0"' if interactive else ""
        pieces.append(
            f'<circle class="county-point" data-fips="{row["fips"]}" data-region="{row["region"]}" '
            f'cx="{scale_x(row["x"]):.2f}" cy="{scale_y(row["y"]):.2f}" r="3.05" '
            f'fill="{REGION_COLORS[row["region"]]}" aria-label="{label}"{tab}/>'
        )
    return "\n".join(pieces)


def static_svg(records: list[dict], stats: dict[str, dict]) -> str:
    overall = stats["All counties"]
    legend = []
    for index, (region, color) in enumerate(REGION_COLORS.items()):
        y = 491 + index * 36
        count = stats[region]["n"]
        legend.append(f'<circle cx="1190" cy="{y}" r="7" fill="{color}"/>')
        legend.append(f'<text x="1208" y="{y + 5}" class="legend">{region} · {count:,}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800" role="img" aria-labelledby="title desc">
<title id="title">Counties with more physical inactivity tend to have higher diabetes estimates</title>
<desc id="desc">Scatter plot of 2,956 U.S. counties using 2023 age-adjusted CDC PLACES estimates. Each point is a county. A LOWESS curve summarizes a strong positive association; it is not causal.</desc>
<rect width="1400" height="800" fill="#f4f7fa"/>
<text x="48" y="37" class="kicker">CDC PLACES · 2023 MODEL-BASED ESTIMATES</text>
<text x="48" y="73" class="title">More physical inactivity, higher diabetes estimates</text>
<text x="48" y="100" class="subtitle">Each point is one county; the LOWESS curve summarizes the pattern without implying causation.</text>
<rect x="34" y="120" width="1094" height="650" rx="16" fill="#fff" stroke="#dce4ec"/>
<g transform="translate(0,100)">{axes_markup()}<g class="points">{point_markup(records, interactive=False)}</g><path d="{overall["trend"]}" class="trend"/><text x="945" y="163" class="trend-label">LOWESS trend</text></g>
<rect x="1146" y="120" width="220" height="650" rx="16" fill="#fff" stroke="#dce4ec"/>
<text x="1172" y="161" class="panel-label">ASSOCIATION</text>
<text x="1172" y="210" class="stat">r = {overall["pearson"]:.3f}</text><text x="1172" y="235" class="note">Pearson correlation</text>
<text x="1172" y="286" class="stat">R² = {overall["rSquared"]:.3f}</text><text x="1172" y="311" class="note">Descriptive linear fit</text>
<text x="1172" y="362" class="stat">n = {overall["n"]:,}</text><text x="1172" y="387" class="note">Complete counties</text>
<line x1="1172" y1="426" x2="1340" y2="426" stroke="#dce4ec"/>
<text x="1172" y="460" class="panel-label">CENSUS REGION</text>{''.join(legend)}
<line x1="1172" y1="656" x2="1340" y2="656" stroke="#dce4ec"/>
<text x="1172" y="688" class="note">County-level association;</text><text x="1172" y="708" class="note">not an individual-level effect.</text>
<text x="1172" y="738" class="note">KY and PA are absent because</text><text x="1172" y="758" class="note">2023 estimates are unpublished.</text>
<style>
text{{font-family:Inter,Arial,sans-serif;fill:#172331}}.kicker{{font-size:13px;font-weight:800;letter-spacing:1.3px;fill:#526b82}}.title{{font-size:31px;font-weight:800}}.subtitle{{font-size:15px;fill:#5b6c7e}}
.grid{{stroke:#e7edf3;stroke-width:1}}.frame{{fill:none;stroke:#aebdca;stroke-width:1}}.tick{{font-size:12px;fill:#607386}}.axis-title{{font-size:14px;font-weight:700;fill:#344b60}}
.county-point{{fill-opacity:.43;stroke:#fff;stroke-width:.25}}.trend{{fill:none;stroke:#172331;stroke-width:4;stroke-linecap:round;stroke-linejoin:round}}.trend-label{{font-size:13px;font-weight:800;fill:#172331}}
.panel-label{{font-size:11px;font-weight:850;letter-spacing:1.2px;fill:#65788a}}.stat{{font-size:27px;font-weight:830}}.note{{font-size:12px;fill:#607386}}.legend{{font-size:13px;fill:#344b60}}
</style></svg>'''


HTML_TEMPLATE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Diabetes and physical inactivity — county relationship</title>
<style>
:root{--ink:#172331;--muted:#5b6c7e;--line:#dce4ec;--bg:#f3f6fa;--panel:#fff;--accent:#153e61;--focus:#f6a800}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.app{min-height:100vh;max-width:1500px;margin:auto;padding:20px 28px 16px;display:grid;grid-template-rows:auto auto 1fr auto;gap:13px}.kicker{font-size:12px;font-weight:850;letter-spacing:.12em;color:#526b82}.title{font-size:clamp(25px,2.35vw,37px);line-height:1.08;margin:5px 0 6px;letter-spacing:-.025em}.subtitle{color:var(--muted);font-size:14px}.filters{display:flex;gap:8px;flex-wrap:wrap}.filter{border:1px solid #bcc9d5;border-radius:999px;background:#fff;padding:8px 13px;font-size:13px;font-weight:780;color:#294158;cursor:pointer}.filter[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}.filter:focus-visible,.county-point:focus-visible{outline:3px solid var(--focus);outline-offset:2px}.workspace{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:14px}.chart-card,.side{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:0 9px 28px rgba(42,61,79,.07)}.chart-card{position:relative;min-height:0;overflow:hidden;padding:4px}.chart-card svg{width:100%;height:100%;min-height:470px;display:block}.grid{stroke:#e7edf3;stroke-width:1}.frame{fill:none;stroke:#aebdca}.tick{font-size:13px;fill:#607386}.axis-title{font-size:16px;font-weight:750;fill:#344b60}.county-point{fill-opacity:.48;stroke:#fff;stroke-width:.25;cursor:pointer;transition:opacity .18s,r .18s}.county-point.is-hidden{display:none}.county-point:hover,.county-point.is-selected{r:7;fill-opacity:1;stroke:#111827;stroke-width:2;paint-order:stroke}.trend{fill:none;stroke:#172331;stroke-width:4.5;stroke-linecap:round;stroke-linejoin:round;transition:d .35s ease}.trend-label{font-size:14px;font-weight:800;fill:#172331}.side{padding:18px;display:flex;flex-direction:column;gap:16px}.section-label{font-size:11px;font-weight:850;letter-spacing:.11em;color:#66788b}.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.stat{background:#f5f8fb;border-radius:10px;padding:11px}.stat strong{display:block;font-size:21px}.stat span{font-size:11px;color:var(--muted)}.region-legend{display:grid;grid-template-columns:1fr 1fr;gap:9px;font-size:12px;color:#43576a}.legend-item{display:flex;align-items:center;gap:7px}.dot{width:10px;height:10px;border-radius:50%}.selection{border-top:1px solid var(--line);padding-top:14px;min-height:150px}.selection h2{font-size:18px;margin:5px 0 2px}.place{font-size:12px;color:var(--muted)}.measure{font-size:14px;margin-top:9px}.measure strong{font-size:21px}.ci{font-size:11px;color:var(--muted)}.empty,.method{font-size:13px;line-height:1.5;color:var(--muted)}.clear{border:0;background:none;color:#0c609f;font-weight:780;padding:8px 0;cursor:pointer}.method{margin-top:auto}.tooltip{position:fixed;z-index:10;pointer-events:none;background:#172331;color:#fff;border-radius:10px;padding:11px 13px;min-width:235px;box-shadow:0 12px 28px rgba(0,0,0,.22);opacity:0;transform:translate(12px,12px)}.tooltip.visible{opacity:1}.tooltip strong,.tooltip span{display:block}.tooltip span{font-size:12px;color:#d8e4ef;margin-top:4px}footer{display:flex;justify-content:space-between;gap:16px;font-size:11px;color:var(--muted);line-height:1.4}footer p{margin:0;max-width:920px}@media(max-width:950px){.workspace{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr}.method{grid-column:1/-1}}@media(max-width:650px){.app{padding:15px}.side{display:flex}.chart-card svg{min-height:390px}footer{flex-direction:column}}@media(prefers-reduced-motion:reduce){.county-point,.trend{transition:none}}
</style></head><body><main class="app"><header><div class="kicker">CDC PLACES · COUNTY RELATIONSHIP</div><h1 class="title" id="headline">More physical inactivity, higher diabetes estimates</h1><div class="subtitle">2023 model-based, age-adjusted county estimates · descriptive association, not causation</div></header><nav class="filters" aria-label="Filter by Census region">@@BUTTONS@@</nav><section class="workspace"><div class="chart-card"><svg viewBox="0 0 1200 735" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">Diabetes and physical inactivity by county</title><desc id="chart-desc">Each point is one county. The LOWESS curve summarizes the positive association.</desc>@@AXES@@<g id="points">@@POINTS@@</g><path id="trend" class="trend"/><text x="950" y="98" class="trend-label">LOWESS trend</text></svg><div class="tooltip" id="tooltip" role="status"></div></div><aside class="side"><div><div class="section-label">DISPLAYED COUNTIES</div><div class="stat-grid"><div class="stat"><strong id="correlation"></strong><span>Pearson r</span></div><div class="stat"><strong id="r-squared"></strong><span>R²</span></div><div class="stat"><strong id="count"></strong><span>Counties</span></div><div class="stat"><strong id="median-pair"></strong><span>Median inactivity / diabetes</span></div></div></div><div><div class="section-label">CENSUS REGION</div><div class="region-legend">@@LEGEND@@</div></div><div class="selection" id="selection"><div class="section-label">SELECTED COUNTY</div><p class="empty">Hover for details. Click a point to keep the county highlighted.</p></div><p class="method"><strong>How to read:</strong> points moving from lower-left to upper-right indicate that counties with more physical inactivity tend to have higher diabetes estimates. The LOWESS line checks the shape without forcing a straight line.</p></aside></section><footer><p><strong>Source:</strong> CDC PLACES 2025 release; 2023 model-based estimates. Kentucky and Pennsylvania are absent because these measures are unpublished.</p><p>County-level correlation does not establish an individual-level or causal effect.</p></footer></main>
<script>
const records=@@DATA@@,stats=@@STATS@@,tooltip=document.getElementById('tooltip'),selection=document.getElementById('selection'),points=[...document.querySelectorAll('.county-point')];let current='All counties',selected=null;const byFips=Object.fromEntries(records.map(r=>[r.fips,r]));
function detail(fips){return byFips[fips]}function ci(low,high){return low==null?'95% CI not published':`95% CI ${low.toFixed(1)}–${high.toFixed(1)}%`}
function showTip(row,x,y){tooltip.innerHTML=`<strong>${row.county} County</strong><span>${row.state} · ${row.region}</span><span>Inactivity: ${row.x.toFixed(1)}% · ${ci(row.xLow,row.xHigh)}</span><span>Diabetes: ${row.y.toFixed(1)}% · ${ci(row.yLow,row.yHigh)}</span>`;tooltip.style.left=`${Math.min(x,window.innerWidth-265)}px`;tooltip.style.top=`${Math.min(y,window.innerHeight-145)}px`;tooltip.classList.add('visible')}
function renderSelection(row){selection.innerHTML=`<div class="section-label">SELECTED COUNTY</div><h2>${row.county} County</h2><div class="place">${row.state} · ${row.region} · FIPS ${row.fips}</div><div class="measure"><strong>${row.x.toFixed(1)}%</strong> inactivity<div class="ci">${ci(row.xLow,row.xHigh)}</div></div><div class="measure"><strong>${row.y.toFixed(1)}%</strong> diabetes<div class="ci">${ci(row.yLow,row.yHigh)}</div></div><button class="clear" id="clear">Clear selection</button>`;document.getElementById('clear').onclick=clearSelection}
function clearSelection(){selected=null;points.forEach(p=>p.classList.remove('is-selected'));selection.innerHTML='<div class="section-label">SELECTED COUNTY</div><p class="empty">Hover for details. Click a point to keep the county highlighted.</p>'}
function setRegion(region){current=region;tooltip.classList.remove('visible');if(selected&&region!=='All counties'&&byFips[selected].region!==region)clearSelection();document.querySelectorAll('.filter').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.region===region)));points.forEach(p=>p.classList.toggle('is-hidden',region!=='All counties'&&p.dataset.region!==region));const s=stats[region];document.getElementById('trend').setAttribute('d',s.trend);document.getElementById('correlation').textContent=s.pearson.toFixed(3);document.getElementById('r-squared').textContent=s.rSquared.toFixed(3);document.getElementById('count').textContent=s.n.toLocaleString();document.getElementById('median-pair').textContent=`${s.xMedian.toFixed(1)} / ${s.yMedian.toFixed(1)}`;document.getElementById('headline').textContent=region==='All counties'?'More physical inactivity, higher diabetes estimates':`${region}: inactivity and diabetes remain positively associated`}
points.forEach(point=>{const row=detail(point.dataset.fips);point.addEventListener('pointermove',e=>showTip(row,e.clientX,e.clientY));point.addEventListener('pointerleave',()=>tooltip.classList.remove('visible'));point.addEventListener('focus',()=>{const r=point.getBoundingClientRect();showTip(row,r.left+r.width/2,r.top+r.height/2)});point.addEventListener('blur',()=>tooltip.classList.remove('visible'));point.addEventListener('click',()=>{selected=row.fips;points.forEach(p=>p.classList.toggle('is-selected',p===point));renderSelection(row)})});document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>setRegion(b.dataset.region)));setRegion('All counties');
</script></body></html>'''


def interactive_html(records: list[dict], stats: dict[str, dict]) -> str:
    labels = ["All counties", *REGION_STATES]
    buttons = "".join(
        f'<button class="filter" data-region="{label}" aria-pressed="false">{label}</button>'
        for label in labels
    )
    legend = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{color}"></span>{region}</div>'
        for region, color in REGION_COLORS.items()
    )
    replacements = {
        "@@BUTTONS@@": buttons,
        "@@AXES@@": axes_markup(),
        "@@POINTS@@": point_markup(records),
        "@@LEGEND@@": legend,
        "@@DATA@@": json.dumps(records, ensure_ascii=False, separators=(",", ":")),
        "@@STATS@@": json.dumps(stats, ensure_ascii=False, separators=(",", ":")),
    }
    result = HTML_TEMPLATE
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = read_data()
    if len(records) != 2956:
        raise ValueError(f"Expected 2,956 complete counties, found {len(records):,}")
    if len({row["fips"] for row in records}) != len(records):
        raise ValueError("CountyFIPS is not unique in the relationship input")
    stats = subset_statistics(records)
    expected_r = 0.873318
    if abs(stats["All counties"]["pearson"] - expected_r) > 0.000001:
        raise ValueError("Pearson correlation does not match accepted relationship output")

    STATIC_SVG.write_text(static_svg(records, stats), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(interactive_html(records, stats), encoding="utf-8")
    validation = {
        "status": "PASS",
        "input": str(DATA_PATH.relative_to(ROOT)),
        "input_sha256": sha256(DATA_PATH),
        "complete_counties": len(records),
        "unique_fips": len({row["fips"] for row in records}),
        "pearson_r": stats["All counties"]["pearson"],
        "r_squared": stats["All counties"]["rSquared"],
        "lowess_span": 0.25,
        "region_counts": {region: stats[region]["n"] for region in REGION_STATES},
        "outputs": [
            str(STATIC_SVG.relative_to(ROOT)),
            str((OUTPUT_DIR / "index.html").relative_to(ROOT)),
        ],
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
