#!/usr/bin/env python3
"""Build the final county-level interactive choropleth from validated PLACES data.

The implementation intentionally uses only Python's standard library so the
artifact can be reproduced without installing GIS or JavaScript packages.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import struct
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / ("01_data" if (ROOT / "01_data").exists() else "data")
DATA_PATH = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
BOUNDARY_ZIP = DATA_ROOT / "reference/census_boundaries/cb_2023_us_county_5m.zip"
OUTPUT_DIR = ROOT / "03_visualisations/final/interactive_county_map"
STATIC_SVG = ROOT / "03_visualisations/final/county_diabetes_choropleth.svg"
VALIDATION_PATH = ROOT / "02_analysis/outputs/map_validation.json"

BOUNDARY_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2023/shp/"
    "cb_2023_us_county_5m.zip"
)

METRICS = {
    "diabetes": {
        "value": "DIABETES_AdjPrev",
        "low": "derived__DIABETES_Adj95CI_Low",
        "high": "derived__DIABETES_Adj95CI_High",
        "button": "Diabetes",
        "title": "Diagnosed diabetes",
        "headline": "Diabetes rates are highest in the South, led by Mississippi, Louisiana, Georgia and South Carolina.",
    },
    "obesity": {
        "value": "OBESITY_AdjPrev",
        "low": "derived__OBESITY_Adj95CI_Low",
        "high": "derived__OBESITY_Adj95CI_High",
        "button": "Obesity",
        "title": "Obesity",
        "headline": "Obesity is most common in the Deep South and Appalachia; lowest in Colorado, Hawaii and parts of New England.",
    },
    "inactivity": {
        "value": "LPA_AdjPrev",
        "low": "derived__LPA_Adj95CI_Low",
        "high": "derived__LPA_Adj95CI_High",
        "button": "Physical inactivity",
        "title": "No leisure-time physical activity",
        "headline": "Physical inactivity is highest in the lower Mississippi valley and Appalachia.",
    },
}

# ColorBrewer Blues: ordered, perceptually monotonic, and color-vision friendly.
COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
MISSING_COLOR = "#d7dce2"



def full_county_names() -> dict[str, str]:
    """Official names with the legal type (County, Parish, city, Borough...)."""
    path = DATA_ROOT / "reference/places_to_2023_gazetteer.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["CountyFIPS"].zfill(5): row["census_name"] for row in csv.DictReader(handle)}


FULL_NAMES = full_county_names()

def clean_number(value: str) -> float | None:
    value = value.strip()
    return None if not value else float(value)


def read_places() -> dict[str, dict]:
    records: dict[str, dict] = {}
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            fips = row["CountyFIPS"].zfill(5)
            item = {
                "fips": fips,
                "county": FULL_NAMES.get(row["CountyFIPS"].zfill(5), row["derived__CountyName_display"]),
                "state": row["StateDesc"],
                "abbr": row["StateAbbr"],
                "population": int(row["TotalPopulation"]),
            }
            for key, spec in METRICS.items():
                item[key] = {
                    "value": clean_number(row[spec["value"]]),
                    "low": clean_number(row[spec["low"]]),
                    "high": clean_number(row[spec["high"]]),
                }
            records[fips] = item
    return records


def read_dbf(blob: bytes) -> list[dict[str, str]]:
    record_count = struct.unpack_from("<I", blob, 4)[0]
    header_length = struct.unpack_from("<H", blob, 8)[0]
    record_length = struct.unpack_from("<H", blob, 10)[0]
    fields: list[tuple[str, int]] = []
    cursor = 32
    while cursor < header_length and blob[cursor] != 0x0D:
        descriptor = blob[cursor : cursor + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii")
        fields.append((name, descriptor[16]))
        cursor += 32

    rows: list[dict[str, str]] = []
    for index in range(record_count):
        start = header_length + index * record_length
        record = blob[start : start + record_length]
        if not record or record[0:1] == b"*":
            rows.append({})
            continue
        offset = 1
        row: dict[str, str] = {}
        for name, width in fields:
            row[name] = record[offset : offset + width].decode("latin-1").strip()
            offset += width
        rows.append(row)
    return rows


def read_polygon_shapes(blob: bytes) -> list[list[list[tuple[float, float]]]]:
    shapes: list[list[list[tuple[float, float]]]] = []
    cursor = 100
    while cursor + 8 <= len(blob):
        _, length_words = struct.unpack_from(">2i", blob, cursor)
        cursor += 8
        content = blob[cursor : cursor + length_words * 2]
        cursor += length_words * 2
        if len(content) < 4:
            shapes.append([])
            continue
        shape_type = struct.unpack_from("<i", content, 0)[0]
        if shape_type == 0:
            shapes.append([])
            continue
        if shape_type not in (5, 15, 25):
            raise ValueError(f"Unsupported shapefile shape type: {shape_type}")
        part_count, point_count = struct.unpack_from("<2i", content, 36)
        part_starts = list(struct.unpack_from(f"<{part_count}i", content, 44))
        point_offset = 44 + 4 * part_count
        points = [
            struct.unpack_from("<2d", content, point_offset + i * 16)
            for i in range(point_count)
        ]
        part_starts.append(point_count)
        shapes.append(
            [points[part_starts[i] : part_starts[i + 1]] for i in range(part_count)]
        )
    return shapes


def read_boundaries() -> list[dict]:
    with zipfile.ZipFile(BOUNDARY_ZIP) as archive:
        shp_name = next(name for name in archive.namelist() if name.endswith(".shp"))
        dbf_name = next(name for name in archive.namelist() if name.endswith(".dbf"))
        shapes = read_polygon_shapes(archive.read(shp_name))
        rows = read_dbf(archive.read(dbf_name))
    if len(shapes) != len(rows):
        raise ValueError(f"Geometry/attribute mismatch: {len(shapes)} vs {len(rows)}")
    return [
        {
            "fips": row["GEOID"].zfill(5),
            "state_fips": row["STATEFP"].zfill(2),
            "rings": rings,
        }
        for row, rings in zip(rows, shapes)
        if row and rings
    ]


def albers_projector(
    standard_parallel_1: float,
    standard_parallel_2: float,
    latitude_origin: float,
    central_meridian: float,
):
    phi1, phi2, phi0, lambda0 = map(
        math.radians,
        (standard_parallel_1, standard_parallel_2, latitude_origin, central_meridian),
    )
    n = 0.5 * (math.sin(phi1) + math.sin(phi2))
    c = math.cos(phi1) ** 2 + 2 * n * math.sin(phi1)
    rho0 = math.sqrt(c - 2 * n * math.sin(phi0)) / n

    def project(lon: float, lat: float) -> tuple[float, float]:
        lam, phi = math.radians(lon), math.radians(lat)
        delta = (lam - lambda0 + math.pi) % (2 * math.pi) - math.pi
        theta = n * delta
        rho = math.sqrt(max(0.0, c - 2 * n * math.sin(phi))) / n
        return rho * math.sin(theta), rho0 - rho * math.cos(theta)

    return project


def bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def fit_transform(
    source_bounds: tuple[float, float, float, float],
    target: tuple[float, float, float, float],
):
    min_x, min_y, max_x, max_y = source_bounds
    tx, ty, tw, th = target
    scale = min(tw / (max_x - min_x), th / (max_y - min_y))
    used_w, used_h = (max_x - min_x) * scale, (max_y - min_y) * scale
    offset_x = tx + (tw - used_w) / 2 - min_x * scale
    offset_y = ty + (th - used_h) / 2 + max_y * scale

    def transform(x: float, y: float) -> tuple[float, float]:
        return offset_x + x * scale, offset_y - y * scale

    return transform


def projected_paths(boundaries: list[dict], allowed_fips: set[str]) -> dict[str, str]:
    regions = {
        "lower48": {
            "states": allowed_fips - {"02", "15"},
            "project": albers_projector(29.5, 45.5, 37.5, -96),
            "target": (55, 35, 1090, 495),
        },
        "alaska": {
            "states": {"02"},
            "project": albers_projector(55, 65, 50, -154),
            "target": (75, 545, 245, 120),
        },
        "hawaii": {
            "states": {"15"},
            "project": albers_projector(18, 22, 20, -157),
            "target": (365, 575, 175, 75),
        },
    }

    result: dict[str, str] = {}
    for config in regions.values():
        selected = [b for b in boundaries if b["state_fips"] in config["states"]]
        projected: dict[str, list[list[tuple[float, float]]]] = {}
        all_points: list[tuple[float, float]] = []
        for feature in selected:
            rings = [
                [config["project"](lon, lat) for lon, lat in ring]
                for ring in feature["rings"]
            ]
            projected[feature["fips"]] = rings
            all_points.extend(point for ring in rings for point in ring)
        transform = fit_transform(bounds(all_points), config["target"])
        for fips, rings in projected.items():
            commands: list[str] = []
            for ring in rings:
                if not ring:
                    continue
                screen = [transform(x, y) for x, y in ring]
                commands.append(f"M{screen[0][0]:.2f},{screen[0][1]:.2f}")
                commands.extend(f"L{x:.2f},{y:.2f}" for x, y in screen[1:])
                commands.append("Z")
            result[fips] = "".join(commands)
    return result


def quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    fraction = position - low
    return sorted_values[low] * (1 - fraction) + sorted_values[high] * fraction


def metric_summaries(records: dict[str, dict]) -> dict[str, dict]:
    summaries = {}
    for key in METRICS:
        values = sorted(
            item[key]["value"]
            for item in records.values()
            if item[key]["value"] is not None
        )
        summaries[key] = {
            "count": len(values),
            "missing": len(records) - len(values),
            "min": min(values),
            "max": max(values),
            "median": statistics.median(values),
            "q1": quantile(values, 0.25),
            "q3": quantile(values, 0.75),
            "breaks": [quantile(values, p) for p in (0.2, 0.4, 0.6, 0.8)],
        }
    return summaries


def color_for(value: float | None, breaks: list[float]) -> str:
    if value is None:
        return MISSING_COLOR
    index = sum(value > threshold for threshold in breaks)
    return COLORS[index]


def build_path_markup(
    paths: dict[str, str], records: dict[str, dict], summaries: dict[str, dict]
) -> str:
    pieces = []
    for fips in sorted(paths):
        record = records.get(fips)
        value = record["diabetes"]["value"] if record else None
        fill = color_for(value, summaries["diabetes"]["breaks"])
        label = (
            f'{record["county"]}, {record["state"]}'
            if record
            else f"County FIPS {fips}; no PLACES row"
        )
        pieces.append(
            f'<path class="county" id="county-{fips}" data-fips="{fips}" '
            f'd="{paths[fips]}" fill="{fill}" tabindex="0" '
            f'aria-label="{label}" />'
        )
    return "\n".join(pieces)


def static_legend(summary: dict) -> str:
    edges = [summary["min"], *summary["breaks"], summary["max"]]
    items = []
    for index, color in enumerate(COLORS):
        y = 332 + index * 52
        items.append(f'<rect x="1090" y="{y}" width="38" height="26" rx="3" fill="{color}"/>')
        items.append(
            f'<text x="1140" y="{y + 18}" class="legend-label">'
            f'{edges[index]:.1f}–{edges[index + 1]:.1f}%</text>'
        )
    items.append(f'<rect x="1090" y="602" width="38" height="26" rx="3" fill="{MISSING_COLOR}"/>')
    items.append('<text x="1140" y="620" class="legend-label">Not published</text>')
    return "\n".join(items)


def write_static_svg(path_markup: str, summaries: dict[str, dict]) -> None:
    summary = summaries["diabetes"]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800" role="img" aria-labelledby="title desc">
<title id="title">Diabetes rate by U.S. county</title>
<desc id="desc">A county map of 2023 CDC PLACES estimates. Darker blue indicates higher prevalence. Kentucky and Pennsylvania are shown as not published.</desc>
<rect width="1400" height="800" fill="#f7f9fc"/>
<text x="55" y="42" class="eyebrow">CDC PLACES • 2023 county estimates</text>
<text x="55" y="76" class="title">Where is diagnosed diabetes prevalence higher?</text>
<text x="55" y="103" class="subtitle">Share of adults, adjusted for age; darker blue means a higher rate.</text>
<rect x="35" y="125" width="1000" height="640" rx="16" fill="#ffffff" stroke="#dbe3ed"/>
<g transform="translate(16,128) scale(.86)">{path_markup}</g>
<text x="86" y="626" class="inset-title">Alaska</text><text x="330" y="650" class="inset-title">Hawaii</text>
<text x="625" y="715" class="note">County area does not represent population.</text>
<rect x="1055" y="125" width="310" height="640" rx="16" fill="#ffffff" stroke="#dbe3ed"/>
<text x="1088" y="171" class="panel-label">DISTRIBUTION</text>
<text x="1088" y="212" class="stat">{summary["median"]:.1f}%</text><text x="1088" y="237" class="note">Median estimate</text>
<text x="1225" y="212" class="stat">{summary["count"]:,}</text><text x="1225" y="237" class="note">Published counties</text>
<line x1="1088" y1="267" x2="1332" y2="267" stroke="#dbe3ed"/>
<text x="1088" y="301" class="legend-title">Share of adults (age-adjusted)</text>
{static_legend(summary)}
<line x1="1088" y1="653" x2="1332" y2="653" stroke="#dbe3ed"/>
<text x="1088" y="683" class="note">Each of the 5 colours holds about</text>
<text x="1088" y="702" class="note">one fifth of counties (20% each).</text>
<text x="1088" y="731" class="note">Gray includes unpublished estimates and</text>
<text x="1088" y="750" class="note">Loving County, TX (no PLACES row).</text>
<style>
text{{font-family:Inter,Arial,sans-serif;fill:#182230}} .eyebrow{{font-size:14px;font-weight:700;letter-spacing:1px;fill:#466079}}
.title{{font-size:30px;font-weight:750}} .subtitle{{font-size:16px;fill:#526579}} .county{{stroke:#fff;stroke-width:.45;fill-rule:evenodd}}
.legend-title,.inset-title{{font-size:15px;font-weight:700}} .legend-label{{font-size:14px;fill:#44576a}}
.panel-label{{font-size:12px;font-weight:800;letter-spacing:1.3px;fill:#66788b}} .stat{{font-size:27px;font-weight:800}}
.note{{font-size:12px;fill:#5d6f81}}
</style>
</svg>'''
    STATIC_SVG.write_text(svg, encoding="utf-8")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>County Health Patterns — CDC PLACES</title>
  <meta name="description" content="Interactive county choropleth of age-adjusted diabetes, obesity, and physical inactivity estimates." />
  <style>
    :root{--ink:#172331;--muted:#5b6c7e;--line:#dce4ec;--panel:#fff;--bg:#f3f6fa;--accent:#08519c;--focus:#f59e0b}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .app{min-height:100vh;max-width:1500px;margin:auto;padding:22px 28px 18px;display:grid;grid-template-rows:auto auto 1fr auto;gap:14px}
    header{display:flex;justify-content:space-between;gap:24px;align-items:end}.kicker{font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#466079;margin-bottom:6px}
    h1{font-size:clamp(24px,2.45vw,38px);line-height:1.08;margin:0;max-width:940px;letter-spacing:-.025em}.subtitle{color:var(--muted);font-size:15px;margin-top:8px}
    .controls{display:flex;flex-wrap:wrap;gap:8px}.metric-button{border:1px solid #b9c8d7;background:#fff;color:#274159;border-radius:999px;padding:9px 14px;font-weight:750;font-size:14px;cursor:pointer}
    .metric-button[aria-pressed="true"]{background:#123f67;border-color:#123f67;color:white}.metric-button:focus-visible,.county:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
    .workspace{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:14px}.map-card,.side-card{background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:0 9px 28px rgba(42,61,79,.07)}
    .map-card{min-height:0;position:relative;overflow:hidden;padding:6px}.map-card svg{display:block;width:100%;height:100%;min-height:455px}.county{stroke:#fff;stroke-width:.48;fill-rule:evenodd;cursor:pointer;transition:fill .34s ease,opacity .18s ease,stroke-width .18s ease}.county:hover,.county.is-selected{stroke:#f59e0b;stroke-width:2.2;paint-order:stroke;filter:drop-shadow(0 1px 1px rgba(0,0,0,.25))}.county.is-dimmed{opacity:.18}
    .inset-label{font-size:17px;font-weight:800;fill:#40566b}.inset-note{font-size:13px;fill:#6a7b8c}
    .side-card{padding:18px;display:flex;flex-direction:column;gap:17px}.section-label{font-size:11px;font-weight:850;letter-spacing:.11em;text-transform:uppercase;color:#66788b}.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.stat{background:#f5f8fb;border-radius:10px;padding:11px}.stat strong{display:block;font-size:21px}.stat span{font-size:12px;color:var(--muted)}
    .legend-swatches{display:grid;grid-template-columns:repeat(5,1fr);height:16px;border-radius:5px;overflow:hidden;margin-top:8px}.legend-labels{display:grid;grid-template-columns:repeat(5,1fr);font-size:10px;color:var(--muted);gap:2px;margin-top:5px}.legend-labels span{text-align:center}.missing{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;margin-top:10px}.missing-box{width:17px;height:14px;background:#d7dce2;border:1px solid #c5cbd2}
    .selection{border-top:1px solid var(--line);padding-top:15px;min-height:128px}.selection h2{font-size:19px;margin:5px 0 4px}.selection .place{color:var(--muted);font-size:13px}.selection .estimate{font-size:28px;font-weight:820;margin:10px 0 1px}.selection .ci{font-size:13px;color:var(--muted)}.selection-empty{color:var(--muted);font-size:14px;line-height:1.5}.clear{align-self:flex-start;background:none;border:0;padding:5px 0;color:#0d5c9e;font-weight:750;cursor:pointer}
    .method-note{font-size:12px;line-height:1.5;color:var(--muted);margin-top:auto}.tooltip{position:fixed;z-index:10;pointer-events:none;background:#172331;color:#fff;border-radius:10px;padding:11px 13px;min-width:210px;box-shadow:0 12px 28px rgba(0,0,0,.2);opacity:0;transform:translate(12px,12px);transition:opacity .1s}.tooltip.is-visible{opacity:1}.tooltip strong{display:block;font-size:14px}.tooltip span{display:block;font-size:12px;color:#d8e4ef;margin-top:4px}
    footer{display:flex;justify-content:space-between;gap:18px;color:var(--muted);font-size:11px;line-height:1.4}footer p{margin:0;max-width:850px}
    @media(max-width:920px){.app{padding:16px}.workspace{grid-template-columns:1fr}.map-card svg{min-height:420px}.side-card{display:grid;grid-template-columns:1fr 1fr}.method-note{grid-column:1/-1}header{align-items:start;flex-direction:column}}
    @media(max-width:620px){.side-card{display:flex}.map-card svg{min-height:350px}footer{flex-direction:column}.subtitle{font-size:13px}}
    @media(prefers-reduced-motion:reduce){.county,.tooltip{transition:none}}
  </style>
</head>
<body>
<main class="app">
  <header>
    <div><div class="kicker">CDC PLACES · County health patterns</div><h1 id="headline">@@INITIAL_HEADLINE@@</h1><div class="subtitle">Share of adults, 2023 estimates, adjusted for age</div></div>
  </header>
  <nav class="controls" aria-label="Choose health metric">@@BUTTONS@@</nav>
  <section class="workspace">
    <div class="map-card" aria-label="Interactive county choropleth">
      <svg id="map" viewBox="0 0 1200 700" role="img" aria-labelledby="map-title map-desc">
        <title id="map-title">County-level health estimates</title>
        <desc id="map-desc">Darker blue represents a higher age-adjusted prevalence estimate. Hover, focus, or select a county for details.</desc>
        <g id="counties">@@PATHS@@</g>
        <g aria-hidden="true"><text x="82" y="552" class="inset-label">Alaska</text><text x="370" y="580" class="inset-label">Hawaii</text><text x="760" y="657" class="inset-note">County area does not represent population.</text></g>
      </svg>
      <div class="tooltip" id="tooltip" role="status"></div>
    </div>
    <aside class="side-card">
      <div><div class="section-label">Distribution</div><div class="stat-grid"><div class="stat"><strong id="median"></strong><span>Median estimate</span></div><div class="stat"><strong id="available"></strong><span>Published counties</span></div></div></div>
      <div><div class="section-label">Colour groups (20% of counties each)</div><div id="legend-title" style="font-weight:760;margin-top:4px"></div><div class="legend-swatches">@@SWATCHES@@</div><div class="legend-labels" id="legend-labels"></div><div class="missing"><span class="missing-box"></span><span>Not published / no data row</span></div></div>
      <div class="selection" id="selection"><div class="section-label">Selected county</div><p class="selection-empty">Hover over a county for details. Click to keep it highlighted.</p></div>
      <div class="method-note"><strong>How to read:</strong> each colour holds about one fifth of counties, from the lowest 20% (lightest) to the highest 20% (darkest). Rates are adjusted for age so counties with older or younger populations can be compared. Values are CDC model estimates, not direct counts, and this is not a health ranking.</div>
    </aside>
  </section>
  <footer><p><strong>Source:</strong> CDC PLACES 2025 release; 2023 county-level estimates. Boundary: U.S. Census Bureau 2023 Cartographic Boundary File (1:5,000,000). Kentucky and Pennsylvania estimates are unpublished for these 2023 measures.</p><p>Use the metric buttons, then hover or click a county.</p></footer>
</main>
<script>
const countyData=@@DATA@@;
const metricMeta=@@META@@;
const summaries=@@SUMMARIES@@;
const colors=@@COLORS@@;
let currentMetric='diabetes',selectedFips=null;
const paths=[...document.querySelectorAll('.county')],tooltip=document.getElementById('tooltip'),selection=document.getElementById('selection');
const fmt=value=>value==null?'Not published':`${value.toFixed(1)}%`;
function colorFor(value,breaks){if(value==null)return '@@MISSING_COLOR@@';let i=0;while(i<breaks.length&&value>breaks[i])i++;return colors[i]}
function updateMetric(metric){currentMetric=metric;tooltip.classList.remove('is-visible');const meta=metricMeta[metric],summary=summaries[metric];document.getElementById('headline').textContent=meta.headline;document.getElementById('legend-title').textContent=meta.title;document.getElementById('median').textContent=`${summary.median.toFixed(1)}%`;document.getElementById('available').textContent=summary.count.toLocaleString();document.querySelectorAll('.metric-button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.metric===metric)));paths.forEach(path=>{const row=countyData[path.dataset.fips];path.style.fill=colorFor(row?.[metric]?.value??null,summary.breaks)});const edges=[summary.min,...summary.breaks,summary.max];document.getElementById('legend-labels').innerHTML=colors.map((_,i)=>`<span>${edges[i].toFixed(1)}–${edges[i+1].toFixed(1)}</span>`).join('');if(selectedFips)renderSelection(selectedFips)}
function details(fips){const row=countyData[fips],meta=metricMeta[currentMetric];if(!row)return {title:`County FIPS ${fips}`,place:'No PLACES data row',estimate:'Not published',ci:''};const m=row[currentMetric];return{title:`${row.county}`,place:`${row.state} · FIPS ${row.fips}`,estimate:fmt(m.value),ci:m.low==null?'Likely range not published':`Likely range ${m.low.toFixed(1)}–${m.high.toFixed(1)}% (95% interval)`,metric:meta.title}}
function showTooltip(fips,x,y){const d=details(fips);tooltip.innerHTML=`<strong>${d.title}</strong><span>${d.place}</span><span>${d.metric||''}: ${d.estimate}</span><span>${d.ci}</span>`;tooltip.style.left=`${Math.min(x,window.innerWidth-245)}px`;tooltip.style.top=`${Math.min(y,window.innerHeight-130)}px`;tooltip.classList.add('is-visible')}
function renderSelection(fips){const d=details(fips);selection.innerHTML=`<div class="section-label">Selected county</div><h2>${d.title}</h2><div class="place">${d.place}</div><div class="estimate">${d.estimate}</div><div class="ci">${d.metric||''}${d.ci?' · '+d.ci:''}</div><button class="clear" id="clear-selection">Clear selection</button>`;document.getElementById('clear-selection').onclick=clearSelection}
function clearSelection(){selectedFips=null;paths.forEach(p=>p.classList.remove('is-selected','is-dimmed'));selection.innerHTML='<div class="section-label">Selected county</div><p class="selection-empty">Hover over a county for details. Click to keep it highlighted.</p>'}
paths.forEach(path=>{const fips=path.dataset.fips;path.addEventListener('pointermove',e=>showTooltip(fips,e.clientX,e.clientY));path.addEventListener('pointerleave',()=>tooltip.classList.remove('is-visible'));path.addEventListener('focus',()=>{const r=path.getBoundingClientRect();showTooltip(fips,r.left+r.width/2,r.top+r.height/2)});path.addEventListener('blur',()=>tooltip.classList.remove('is-visible'));path.addEventListener('click',()=>{selectedFips=fips;paths.forEach(p=>{p.classList.toggle('is-selected',p===path);p.classList.toggle('is-dimmed',p!==path)});renderSelection(fips)})});
document.querySelectorAll('.metric-button').forEach(button=>button.addEventListener('click',()=>updateMetric(button.dataset.metric)));
updateMetric('diabetes');
</script>
</body></html>'''


def write_interactive_html(
    path_markup: str, records: dict[str, dict], summaries: dict[str, dict]
) -> None:
    buttons = "".join(
        f'<button class="metric-button" data-metric="{key}" aria-pressed="false">'
        f'{spec["button"]}</button>'
        for key, spec in METRICS.items()
    )
    swatches = "".join(f'<span style="background:{color}"></span>' for color in COLORS)
    meta = {
        key: {field: spec[field] for field in ("title", "headline")}
        for key, spec in METRICS.items()
    }
    replacements = {
        "@@INITIAL_HEADLINE@@": METRICS["diabetes"]["headline"],
        "@@BUTTONS@@": buttons,
        "@@PATHS@@": path_markup,
        "@@SWATCHES@@": swatches,
        "@@DATA@@": json.dumps(records, ensure_ascii=False, separators=(",", ":")),
        "@@META@@": json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
        "@@SUMMARIES@@": json.dumps(summaries, separators=(",", ":")),
        "@@COLORS@@": json.dumps(COLORS),
        "@@MISSING_COLOR@@": MISSING_COLOR,
    }
    html = HTML_TEMPLATE
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = read_places()
    boundaries = read_boundaries()
    allowed_states = {fips[:2] for fips in records}
    boundaries = [b for b in boundaries if b["state_fips"] in allowed_states]
    boundary_fips = {b["fips"] for b in boundaries}
    record_fips = set(records)
    missing_boundaries = sorted(record_fips - boundary_fips)
    if missing_boundaries:
        raise ValueError(f"PLACES rows without a 2023 county boundary: {missing_boundaries}")

    paths = projected_paths(boundaries, allowed_states)
    summaries = metric_summaries(records)
    path_markup = build_path_markup(paths, records, summaries)
    write_interactive_html(path_markup, records, summaries)
    write_static_svg(path_markup, summaries)

    validation = {
        "status": "PASS",
        "input": str(DATA_PATH.relative_to(ROOT)),
        "input_sha256": sha256(DATA_PATH),
        "boundary": str(BOUNDARY_ZIP.relative_to(ROOT)),
        "boundary_sha256": sha256(BOUNDARY_ZIP),
        "boundary_source": BOUNDARY_URL,
        "places_rows": len(records),
        "matched_places_rows": len(record_fips & boundary_fips),
        "places_rows_without_boundary": missing_boundaries,
        "boundary_counties_without_places_row": sorted(boundary_fips - record_fips),
        "connecticut_planning_regions_matched": sorted(
            fips for fips in record_fips & boundary_fips if fips.startswith("09")
        ),
        "metrics": summaries,
        "outputs": [
            str((OUTPUT_DIR / "index.html").relative_to(ROOT)),
            str(STATIC_SVG.relative_to(ROOT)),
        ],
    }
    VALIDATION_PATH.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
