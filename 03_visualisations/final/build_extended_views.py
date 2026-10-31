#!/usr/bin/env python3
"""Build the two extended visualisations and the project gallery.

* interactive_related_measures/ - pick a 2023 measure; ranked bars show how
  closely every other measure moves with it across counties; click a bar for
  the county scatterplot.
* interactive_state_tiles/      - each state's typical (median) county versus
  the typical U.S. county, on an equal-size state tile map, linked to a
  ranked dot plot.

Each view also gets a static SVG. Run ``02_analysis/extended_analysis.py``
first. Uses pandas/numpy (already required by the project).
"""

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "01_data" if (ROOT / "01_data").is_dir() else ROOT / "data"
INPUT = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
ANALYSIS = ROOT / "02_analysis/outputs"
FINAL = ROOT / "03_visualisations/final"
VALIDATION_OUT = ANALYSIS / "extended_views_validation.json"

# Reference palette (dataviz skill). Category slots in fixed order.
CATEGORY_ORDER = ["Health condition", "Health status", "Risk behavior", "Prevention and care", "Disability", "Social need"]
CATEGORY_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
POS, NEG = "#2a78d6", "#eb6834"  # move together / move in opposite directions
DIVERGING = ["#1c5cab", "#86b6ef", "#f0efec", "#f0a3a0", "#b8302f"]  # negative -> positive
MISSING = "#d9d8d3"

TILES = {
    "AK": (0, 0), "ME": (11, 0), "VT": (10, 1), "NH": (11, 1),
    "WA": (1, 2), "ID": (2, 2), "MT": (3, 2), "ND": (4, 2), "MN": (5, 2), "IL": (6, 2), "WI": (7, 2),
    "MI": (8, 2), "NY": (9, 2), "RI": (10, 2), "MA": (11, 2),
    "OR": (1, 3), "NV": (2, 3), "WY": (3, 3), "SD": (4, 3), "IA": (5, 3), "IN": (6, 3), "OH": (7, 3),
    "PA": (8, 3), "NJ": (9, 3), "CT": (10, 3),
    "CA": (1, 4), "UT": (2, 4), "CO": (3, 4), "NE": (4, 4), "MO": (5, 4), "KY": (6, 4), "WV": (7, 4),
    "VA": (8, 4), "MD": (9, 4), "DE": (10, 4),
    "AZ": (2, 5), "NM": (3, 5), "KS": (4, 5), "AR": (5, 5), "TN": (6, 5), "NC": (7, 5), "SC": (8, 5),
    "DC": (9, 5),
    "OK": (4, 6), "LA": (5, 6), "MS": (6, 6), "AL": (7, 6), "GA": (8, 6),
    "HI": (0, 7), "TX": (4, 7), "FL": (9, 7),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def hex_rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def diverging(t: float) -> str:
    """t in [-1, 1] -> color along the 5-stop diverging ramp."""
    t = max(-1.0, min(1.0, t))
    pos = (t + 1) / 2 * (len(DIVERGING) - 1)
    i = min(int(pos), len(DIVERGING) - 2)
    f = pos - i
    a, b = hex_rgb(DIVERGING[i]), hex_rgb(DIVERGING[i + 1])
    return "#" + "".join(f"{round(a[k] + (b[k] - a[k]) * f):02x}" for k in range(3))


def num(v: float | None, digits: int = 1) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), digits)


# ---------------------------------------------------------------------------
# Shared page chrome
# ---------------------------------------------------------------------------

BASE_CSS = """
.viz-root{color-scheme:light;--surface:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--accent:#2a78d6;--missing:#d9d8d3;--focus:#eda100;--pos:#2a78d6;--neg:#eb6834}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface:#1a1a19;
--plane:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--accent:#3987e5;--missing:#454542;--pos:#3987e5;--neg:#d95926}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface:#1a1a19;--plane:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--accent:#3987e5;--missing:#454542;--pos:#3987e5;--neg:#d95926}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--plane);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{background:var(--plane);min-height:100vh;color:var(--ink)}
.app{max-width:1480px;margin:auto;padding:20px 24px 18px;display:flex;flex-direction:column;gap:14px}
.kicker{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--ink2)}
h1{font-size:clamp(22px,2.1vw,32px);line-height:1.15;margin:4px 0 6px;letter-spacing:-.01em}
.sub{color:var(--ink2);font-size:14px;max-width:980px;line-height:1.45}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.controls label{font-size:13px;color:var(--ink2);display:flex;gap:6px;align-items:center}
select,input[type=search],button{font:inherit;font-size:13px;color:var(--ink);background:var(--surface);
border:1px solid var(--axis);border-radius:8px;padding:6px 10px}
button{cursor:pointer}button[aria-pressed="true"]{background:var(--ink);color:var(--surface);border-color:var(--ink)}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.card{background:var(--surface);border-radius:14px;box-shadow:0 0 0 1px var(--ring);padding:14px;min-width:0}
.card h2{font-size:15px;margin:0 0 4px}.card .note{font-size:12px;color:var(--ink2);margin:0 0 8px;line-height:1.4}
svg text{fill:var(--ink2);font-size:11px;font-variant-numeric:tabular-nums}
.tick{fill:var(--muted)}.gridline{stroke:var(--grid);stroke-width:1}.axisline{stroke:var(--axis);stroke-width:1}
.tip{position:fixed;pointer-events:none;z-index:9;background:var(--surface);color:var(--ink);box-shadow:0 0 0 1px var(--ring),0 6px 20px rgba(0,0,0,.14);
border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.45;max-width:300px;display:none}
.tip strong{font-size:15px;display:block}.tip .k{color:var(--ink2)}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.stat{background:var(--plane);border-radius:10px;padding:9px 10px}.stat .lab{font-size:11px;color:var(--ink2)}
.stat .val{font-size:20px;font-weight:650}.stat .ctx{font-size:11px;color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--ink2);align-items:center}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px}
.ramp{display:inline-block;width:160px;height:10px;border-radius:5px;vertical-align:middle;margin:0 6px}
details{font-size:13px;color:var(--ink2)}details summary{cursor:pointer;font-weight:600;color:var(--ink)}
table{border-collapse:collapse;font-size:12px;margin-top:8px;font-variant-numeric:tabular-nums}
th,td{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:left}td.n{text-align:right}
.foot{font-size:12px;color:var(--muted);line-height:1.5}
a{color:var(--accent)}
@media (max-width:900px){section[style*="grid-template-columns"]{grid-template-columns:1fr!important}.stats{grid-template-columns:1fr}}
"""

THEME_JS = """
const themeBtn=document.getElementById('theme');
themeBtn.addEventListener('click',()=>{const r=document.documentElement;
const dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
r.dataset.theme=dark?'light':'dark';themeBtn.textContent=dark?'Dark mode':'Light mode';});
const tip=document.getElementById('tip');
function showTip(ev,build){tip.replaceChildren();build(tip);tip.style.display='block';
const w=tip.offsetWidth,h=tip.offsetHeight;let x=ev.clientX+14,y=ev.clientY+14;
if(x+w>innerWidth-8)x=ev.clientX-w-14;if(y+h>innerHeight-8)y=ev.clientY-h-14;tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){tip.style.display='none';}
function el(tag,attrs,parent){const ns=['svg','g','rect','line','path','text','circle','polygon','polyline'].includes(tag)?
document.createElementNS('http://www.w3.org/2000/svg',tag):document.createElement(tag);
for(const[k,v]of Object.entries(attrs||{})){if(k==='text')ns.textContent=v;else ns.setAttribute(k,v);}if(parent)parent.appendChild(ns);return ns;}
function tipRow(t,strong,rest){if(strong!==undefined)el('strong',{text:strong},t);for(const line of rest){const d=el('div',{},t);
if(Array.isArray(line)){el('span',{class:'k',text:line[0]+' '},d);d.appendChild(document.createTextNode(line[1]));}else d.textContent=line;}}
const DIV=%s;
function hexRgb(h){return[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));}
function divColor(t){t=Math.max(-1,Math.min(1,t));const p=(t+1)/2*(DIV.length-1);const i=Math.min(Math.floor(p),DIV.length-2);const f=p-i;
const a=hexRgb(DIV[i]),b=hexRgb(DIV[i+1]);return'#'+a.map((v,k)=>Math.round(v+(b[k]-v)*f).toString(16).padStart(2,'0')).join('');}
function inkOn(hex){const[r,g,b]=hexRgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});
return(.2126*r+.7152*g+.0722*b)>.36?'#0b0b0b':'#ffffff';}
""" % json.dumps(DIVERGING)


def page(title: str, kicker: str, headline: str, sub: str, body: str, data: dict, script: str) -> str:
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/><title>{esc(title)}</title>
<style>{BASE_CSS}</style></head><body><div class="viz-root"><main class="app">
<header><div class="kicker">{esc(kicker)}</div><h1>{esc(headline)}</h1><div class="sub">{sub}</div></header>
{body}
<p class="foot">Source: CDC PLACES County Data (GIS Friendly Format), 2025 release, dataset i46a-9kgh; cleaned and validated
project table. Model-based small-area estimates; county-level, descriptive, not causal. <a href="../index.html">All project views</a></p>
</main></div><div class="tip" id="tip" role="status"></div>
<script id="data" type="application/json">{payload}</script>
<script>const DATA=JSON.parse(document.getElementById('data').textContent);
{THEME_JS}
{script}</script></body></html>
"""


def svg_doc(width: int, height: int, title: str, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="system-ui,-apple-system,Segoe UI,sans-serif" role="img" aria-label="{esc(title)}">'
        f'<rect width="{width}" height="{height}" fill="#fcfcfb"/>' + "".join(body) + "</svg>\n"
    )


# ---------------------------------------------------------------------------
# 1. Related measures
# ---------------------------------------------------------------------------

RELATED_JS = r"""
const M=DATA.measures, idx=Object.fromEntries(M.map((m,i)=>[m.id,i]));
const sel=document.getElementById('measure'), bars=document.getElementById('bars'), sc=document.getElementById('scatter');
for(const c of DATA.categories){const og=el('optgroup',{label:c},sel);for(const m of M.filter(m=>m.category===c))el('option',{value:m.id,text:m.label},og);}
const word=r=>{const a=Math.abs(r);return a>=.7?'strong':a>=.4?'moderate':a>=.2?'weak':'little or none';};
const dir=r=>r>=0?'move together':'move in opposite directions';
let cur=null, other=null;
function draw(id){cur=id;hideTip();const i=idx[id];
const rows=M.filter(m=>m.id!==id).map(m=>({m,r:DATA.rho[i][idx[m.id]],n:DATA.n[i][idx[m.id]]})).sort((a,b)=>b.r-a.r);
const RH=19,LW=270,PW=360,W=LW+PW+60,TOP=34,H=TOP+rows.length*RH+30;bars.setAttribute('viewBox',`0 0 ${W} ${H}`);bars.replaceChildren();
const X=v=>LW+(v+1)/2*PW;
for(const[t,lab]of[[-1,'−1'],[-.7,''],[-.4,''],[0,'0'],[.4,''],[.7,''],[1,'+1']]){el('line',{x1:X(t),x2:X(t),y1:TOP-6,y2:H-24,class:t===0?'axisline':'gridline'},bars);
if(lab)el('text',{x:X(t),y:H-8,'text-anchor':'middle',class:'tick',text:lab},bars);}
el('text',{x:X(-.85),y:TOP-14,'text-anchor':'middle',class:'tick',text:'strong opposite'},bars);
el('text',{x:X(.85),y:TOP-14,'text-anchor':'middle',class:'tick',text:'strong together'},bars);
rows.forEach((row,k)=>{const y=TOP+k*RH;const g=el('g',{tabindex:0,role:'button','aria-label':`${row.m.label}: ${row.r.toFixed(2)}, ${word(row.r)}`},bars);
el('rect',{x:0,y:y,width:W,height:RH,fill:row.m.id===other?'var(--grid)':'transparent',rx:4},g);
el('text',{x:LW-8,y:y+13,'text-anchor':'end',text:row.m.label},g);
const x0=X(0),x1=X(row.r);el('rect',{x:Math.min(x0,x1),y:y+4,width:Math.max(1,Math.abs(x1-x0)),height:RH-8,rx:3,fill:row.r>=0?'var(--pos)':'var(--neg)'},g);
el('text',{x:row.r>=0?x1+5:x1-5,y:y+13,'text-anchor':row.r>=0?'start':'end',text:row.r.toFixed(2)+(Math.abs(row.r)>=.9?' †':'')},g);
const show=ev=>showTip(ev,t=>tipRow(t,row.r.toFixed(2),[`${M[i].label} and ${row.m.label}`,`${word(row.r)}: counties ${dir(row.r)}`,['Counties compared',row.n.toLocaleString()],'Click to see the counties']));
g.addEventListener('pointermove',show);g.addEventListener('pointerleave',hideTip);
g.addEventListener('click',()=>{setOther(row.m.id);});g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setOther(row.m.id);}});});
const strong=rows.filter(r=>Math.abs(r.r)>=.7).length;
document.getElementById('nStrong').textContent=String(strong);
document.getElementById('top').textContent=rows[0].m.label;document.getElementById('topv').textContent=rows[0].r.toFixed(2)+' · '+word(rows[0].r);
const last=rows[rows.length-1];document.getElementById('bot').textContent=last.m.label;document.getElementById('botv').textContent=last.r.toFixed(2)+' · '+(last.r<0?word(last.r)+' opposite':word(last.r));
const tb=document.querySelector('#tbl tbody');tb.replaceChildren();
for(const row of rows){const tr=el('tr',{},tb);el('td',{text:row.m.label},tr);el('td',{text:row.m.category},tr);el('td',{class:'n',text:row.r.toFixed(2)},tr);
el('td',{text:word(row.r)+(row.r<0?' (opposite)':'')},tr);el('td',{class:'n',text:row.n.toLocaleString()},tr);}
if(!other||other===id)other=rows[0].m.id;setOther(other,true);history.replaceState(null,'','#'+id);}
function setOther(o,skipRedraw){other=o;if(!skipRedraw){draw(cur);return;}
const a=DATA.values[idx[o]],b=DATA.values[idx[cur]];const pts=[];for(let k=0;k<a.length;k++)if(a[k]!==null&&b[k]!==null)pts.push([a[k],b[k],k]);
sc.replaceChildren();const W=460,H=380,PL=50,PB=44,PT=10,PR=12;sc.setAttribute('viewBox',`0 0 ${W} ${H}`);
const ext=v=>{let lo=Infinity,hi=-Infinity;for(const x of v){if(x<lo)lo=x;if(x>hi)hi=x;}const p=(hi-lo)*.04||1;return[lo-p,hi+p];};
const[x0,x1]=ext(pts.map(p=>p[0])),[y0,y1]=ext(pts.map(p=>p[1]));
const X=v=>PL+(v-x0)/(x1-x0)*(W-PL-PR),Y=v=>H-PB-(v-y0)/(y1-y0)*(H-PB-PT);
const ticks=(lo,hi)=>{const raw=(hi-lo)/5,mag=10**Math.floor(Math.log10(raw)),st=[1,2,2.5,5,10].map(k=>k*mag).find(k=>k>=raw);const o=[];for(let v=Math.ceil(lo/st)*st;v<=hi;v+=st)o.push(+v.toFixed(6));return o;};
for(const t of ticks(x0,x1)){el('line',{x1:X(t),x2:X(t),y1:PT,y2:H-PB,class:'gridline'},sc);el('text',{x:X(t),y:H-PB+15,'text-anchor':'middle',class:'tick',text:t+'%'},sc);}
for(const t of ticks(y0,y1)){el('line',{x1:PL,x2:W-PR,y1:Y(t),y2:Y(t),class:'gridline'},sc);el('text',{x:PL-6,y:Y(t)+4,'text-anchor':'end',class:'tick',text:t+'%'},sc);}
const g=el('g',{},sc);for(const[a1,b1]of pts)el('circle',{cx:X(a1).toFixed(1),cy:Y(b1).toFixed(1),r:2.2,fill:'var(--accent)','fill-opacity':.35},g);
el('text',{x:(PL+W-PR)/2,y:H-6,'text-anchor':'middle',text:M[idx[o]].label},sc);
el('text',{x:12,y:(PT+H-PB)/2,'text-anchor':'middle',transform:`rotate(-90 12 ${(PT+H-PB)/2})`,text:M[idx[cur]].label},sc);
const hl=el('circle',{r:6,fill:'none',stroke:'var(--ink)','stroke-width':2,visibility:'hidden'},sc);
sc.onpointermove=ev=>{const pt=sc.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;const p=pt.matrixTransform(sc.getScreenCTM().inverse());
let best=null,bd=400;for(const q of pts){const d=(X(q[0])-p.x)**2+(Y(q[1])-p.y)**2;if(d<bd){bd=d;best=q;}}
if(!best){hl.setAttribute('visibility','hidden');hideTip();return;}hl.setAttribute('cx',X(best[0]));hl.setAttribute('cy',Y(best[1]));hl.setAttribute('visibility','visible');
const c=DATA.counties[best[2]];showTip(ev,t=>tipRow(t,`${c[0]}, ${c[1]}`,[[M[idx[cur]].label,best[1].toFixed(1)+'%'],[M[idx[o]].label,best[0].toFixed(1)+'%']]));};
sc.onpointerleave=()=>{hl.setAttribute('visibility','hidden');hideTip();};
const r=DATA.rho[idx[cur]][idx[o]];
document.getElementById('pairTitle').textContent=`${M[idx[cur]].label} vs ${M[idx[o]].label}`;
document.getElementById('pairStat').textContent=`Correlation ${r.toFixed(2)} (${word(r)}${r<0?', opposite':''}) · ${pts.length.toLocaleString()} counties · each dot is one county`;}
sel.addEventListener('change',()=>{other=null;draw(sel.value);});
const start=location.hash.slice(1);sel.value=idx[start]!==undefined?start:DATA.defaultMeasure;draw(sel.value);
"""


def build_related(data: pd.DataFrame, catalog: pd.DataFrame) -> dict:
    cat = catalog[(catalog["year"] == 2023) & catalog["in_charts"]].copy()
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    cat = cat.sort_values(["category", "label"], key=lambda s: s.map(order) if s.name == "category" else s)
    ids = cat["measure"].tolist()
    matrix = pd.read_csv(ANALYSIS / "extended_spearman_matrix.csv", index_col=0)
    rho = matrix.loc[ids, ids].to_numpy()
    cols = [f"{m}_AdjPrev" for m in ids]
    present = data[cols].notna().astype(int)
    n = present.T.dot(present).to_numpy()
    measures = [{"id": r.measure, "label": r.label, "category": r.category} for r in cat.itertuples()]
    gaz = pd.read_csv(DATA_ROOT / "reference/places_to_2023_gazetteer.csv", dtype=str)
    full = dict(zip(gaz["CountyFIPS"].str.zfill(5), gaz["census_name"]))
    payload = {
        "measures": measures, "categories": [c for c in CATEGORY_ORDER if c in set(cat["category"])],
        "rho": [[round(float(v), 3) for v in row] for row in rho], "n": n.tolist(),
        "values": [[num(v) for v in data[c]] for c in cols],
        "counties": [[full.get(f, n), st] for f, n, st in zip(data["CountyFIPS"], data["derived__CountyName_display"], data["StateAbbr"])],
        "defaultMeasure": "DIABETES",
    }
    body = f"""
<div class="controls"><label>Measure <select id="measure" aria-label="Measure"></select></label>
<button id="theme" type="button">Dark mode</button></div>
<div class="stats"><div class="stat"><div class="lab">Strongly linked measures</div><div class="val" id="nStrong"></div><div class="ctx">correlation of 0.7 or more, either direction</div></div>
<div class="stat"><div class="lab">Most in step</div><div class="val" id="top" style="font-size:16px"></div><div class="ctx" id="topv"></div></div>
<div class="stat"><div class="lab">Least in step</div><div class="val" id="bot" style="font-size:16px"></div><div class="ctx" id="botv"></div></div></div>
<section style="display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,1fr);gap:14px">
<div class="card"><h2>How closely each measure moves with the selected one</h2>
<p class="note">Correlation across counties, from −1 to +1. Near +1: counties high on one are almost always high on the other.
Near 0: no consistent pattern. Below 0: they move in opposite directions. Click a bar to see the counties.</p>
<svg id="bars" role="group" aria-label="Correlation bars" style="width:100%;height:auto"></svg>
<div class="legend"><span><i style="background:var(--pos)"></i>Move together</span><span><i style="background:var(--neg)"></i>Move in opposite directions</span></div></div>
<div style="display:flex;flex-direction:column;gap:14px">
<div class="card"><h2 id="pairTitle"></h2><p class="note" id="pairStat"></p>
<svg id="scatter" role="img" aria-label="County scatterplot" style="width:100%;height:auto"></svg></div>
<div class="card"><h2>Read this carefully</h2><p class="note">These are county estimates from one CDC statistical model, which uses the same
county background data (age, income, education and so on) for every measure. That makes many measures look more alike than they really are:
† marks correlations of 0.9 or more, which mostly reflect the model, not a direct link. Correlation is not cause.
Social-need measures are published for 2,299 counties (not CO, FL, KY, OR, PA, SD, TN, TX, VT, WA, WY); other measures for 2,956 (not KY, PA).
Only 2023 estimates are shown.</p>
<details><summary>Table view</summary><table id="tbl"><thead><tr><th>Measure</th><th>Group</th><th>Correlation</th><th>Strength</th><th>Counties</th></tr></thead><tbody></tbody></table></details></div>
</div></section>"""
    out = FINAL / "interactive_related_measures"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "Related measures — PLACES county estimates", "Related measures",
        "Counties with more of one health problem tend to have more of many others",
        "Pick a 2023 measure to see which other measures rise and fall with it across U.S. counties.",
        body, payload, RELATED_JS), encoding="utf-8")

    # static: diabetes bars
    i = ids.index("DIABETES")
    rows = sorted(((ids[j], rho[i][j]) for j in range(len(ids)) if j != i), key=lambda t: -t[1])
    lab = dict(zip(cat["measure"], cat["label"]))
    rh, lw, pw, top = 20, 300, 420, 104
    width, height = lw + pw + 90, top + len(rows) * rh + 92
    X = lambda v: lw + (v + 1) / 2 * pw
    b = ['<text x="24" y="34" font-size="20" font-weight="700" fill="#0b0b0b">Counties with more diabetes tend to have more of many other problems</text>',
         '<text x="24" y="56" font-size="13" fill="#52514e">Correlation of each 2023 county estimate with diabetes (−1 to +1). † 0.9 or more: mostly reflects the shared CDC model.</text>']
    for t in (-1, -0.7, -0.4, 0, 0.4, 0.7, 1):
        b.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 6}" y2="{top + len(rows) * rh}" stroke="{"#c3c2b7" if t == 0 else "#e1e0d9"}"/>')
        if t in (-1, 0, 1):
            b.append(f'<text x="{X(t):.1f}" y="{top + len(rows) * rh + 16}" font-size="11" text-anchor="middle" fill="#898781">{t:+g}</text>')
    b.append(f'<text x="{X(-0.85):.1f}" y="{top - 14}" font-size="11" text-anchor="middle" fill="#898781">strong opposite</text><text x="{X(0.85):.1f}" y="{top - 14}" font-size="11" text-anchor="middle" fill="#898781">strong together</text>')
    for k, (m, r) in enumerate(rows):
        y = top + k * rh
        b.append(f'<text x="{lw - 8}" y="{y + 13}" font-size="11" text-anchor="end" fill="#52514e">{esc(lab[m])}</text>')
        x0, x1 = X(0), X(r)
        b.append(f'<rect x="{min(x0, x1):.1f}" y="{y + 4}" width="{max(1, abs(x1 - x0)):.1f}" height="{rh - 8}" rx="3" fill="{POS if r >= 0 else NEG}"/>')
        tx = x1 + 5 if r >= 0 else x1 - 5
        b.append(f'<text x="{tx:.1f}" y="{y + 13}" font-size="11" text-anchor="{"start" if r >= 0 else "end"}" fill="#52514e">{r:.2f}{" †" if abs(r) >= .9 else ""}</text>')
    ly = top + len(rows) * rh + 34
    x = 24
    for k, c in [("Move together", POS), ("Move in opposite directions", NEG)]:
        b.append(f'<rect x="{x}" y="{ly}" width="10" height="10" rx="2" fill="{c}"/><text x="{x + 14}" y="{ly + 9}" font-size="11" fill="#52514e">{esc(k)}</text>')
        x += 14 + len(k) * 6.2 + 16
    b.append(f'<text x="24" y="{height - 14}" font-size="11" fill="#898781">Source: CDC PLACES 2025 county release (i46a-9kgh). 2,956 counties (2,299 for social needs). County-level association, not cause.</text>')
    (FINAL / "related_measures_diabetes.svg").write_text(svg_doc(width, height, "Measures related to diabetes", b), encoding="utf-8")
    return {"measures": len(ids), "symmetric": bool(np.allclose(rho, rho.T)), "excluded": sorted(set(catalog["measure"]) - set(catalog.loc[catalog["in_charts"], "measure"]))}


# ---------------------------------------------------------------------------
# 2. State tiles
# ---------------------------------------------------------------------------

TILES_JS = r"""
const M=DATA.measures, S=DATA.states, T=50, G=4;
const mapSvg=document.getElementById('tiles'), dots=document.getElementById('dots');
mapSvg.setAttribute('viewBox',`0 0 ${12*(T+G)} ${8*(T+G)}`);
const sel=document.getElementById('measure');
const cats=[...new Set(M.map(m=>m.category))];
for(const c of cats){const og=el('optgroup',{label:c},sel);for(const m of M.filter(m=>m.category===c))el('option',{value:m.id,text:m.label+(m.year===2022?' (2022 data)':'')},og);}
let current=null, hover=null;
const tileEls={};
for(const s of S){const[cx,cy]=DATA.tiles[s.abbr];const g=el('g',{transform:`translate(${cx*(T+G)},${cy*(T+G)})`,tabindex:0,role:'img'},mapSvg);
const r=el('rect',{width:T,height:T,rx:6},g);const t1=el('text',{x:T/2,y:21,'text-anchor':'middle','font-size':13,'font-weight':650},g);
const t2=el('text',{x:T/2,y:38,'text-anchor':'middle','font-size':11},g);tileEls[s.abbr]={g,r,t1,t2};
g.addEventListener('pointermove',ev=>{setHover(s.abbr);tipFor(ev,s.abbr);});g.addEventListener('pointerleave',()=>{setHover(null);hideTip();});
g.addEventListener('focus',()=>{setHover(s.abbr);const b=g.getBoundingClientRect();tipFor({clientX:b.right,clientY:b.top},s.abbr);});
g.addEventListener('blur',()=>{setHover(null);hideTip();});}
function tipFor(ev,abbr){const m=M.find(m=>m.id===current),v=m.values[abbr],s=S.find(s=>s.abbr===abbr);
showTip(ev,t=>v?tipRow(t,(v.d>0?'+':'')+v.d.toFixed(1)+' points',[s.name,['Typical county here',v.m.toFixed(1)+'%'],['Typical U.S. county',m.national.toFixed(1)+'%'],['Counties',String(v.n)]])
:tipRow(t,'Not published',[s.name,m.label+' has no '+m.year+' estimate here']));}
function setHover(abbr){hover=abbr;for(const[a,e]of Object.entries(tileEls)){e.r.setAttribute('stroke',a===abbr?'var(--ink)':'none');e.r.setAttribute('stroke-width',2);}
dots.querySelectorAll('[data-abbr]').forEach(d=>{const on=d.dataset.abbr===abbr;d.querySelector('circle').setAttribute('r',on?7:5);
d.querySelector('circle').setAttribute('stroke',on?'var(--ink)':'var(--surface)');});}
function draw(id){current=id;const m=M.find(m=>m.id===id);const ext=m.extent||1;
for(const s of S){const e=tileEls[s.abbr],v=m.values[s.abbr];
if(v){const c=divColor(v.d/ext);e.r.setAttribute('fill',c);const ink=inkOn(c);e.t1.style.fill=ink;e.t2.style.fill=ink;
e.t1.textContent=s.abbr;e.t2.textContent=(v.d>0?'+':'')+v.d.toFixed(1);e.g.setAttribute('aria-label',`${s.name}: ${v.d.toFixed(1)} percentage points vs national`);}
else{e.r.setAttribute('fill','url(#hatch)');e.t1.style.fill='var(--ink2)';e.t2.style.fill='var(--ink2)';e.t1.textContent=s.abbr;e.t2.textContent='n/a';
e.g.setAttribute('aria-label',`${s.name}: not published`);}}
document.getElementById('lo').textContent='−'+ext.toFixed(1);document.getElementById('hi').textContent='+'+ext.toFixed(1)+' pp';
document.getElementById('nat').textContent=m.national.toFixed(1)+'%';
const pub=S.filter(s=>m.values[s.abbr]).sort((a,b)=>m.values[b.abbr].d-m.values[a.abbr].d);
document.getElementById('top').textContent=pub[0].abbr+' '+(m.values[pub[0].abbr].d>0?'+':'')+m.values[pub[0].abbr].d.toFixed(1);
const last=pub[pub.length-1];document.getElementById('bot').textContent=last.abbr+' '+m.values[last.abbr].d.toFixed(1);
document.getElementById('cov').textContent=`${pub.length} of 51 states published · ${m.counties.toLocaleString()} counties`+(m.year===2022?' · 2022 data':'');
document.getElementById('desc').textContent=m.description;
// ranked dot plot
dots.replaceChildren();const RH=14,PL=34,PR=16,W=440,H=pub.length*RH+40;dots.setAttribute('viewBox',`0 0 ${W} ${H}`);
const X=d=>PL+(d+ext)/(2*ext)*(W-PL-PR);
for(const t of[-ext,-ext/2,0,ext/2,ext]){el('line',{x1:X(t),x2:X(t),y1:8,y2:H-26,class:t===0?'axisline':'gridline'},dots);
el('text',{x:X(t),y:H-12,'text-anchor':'middle',class:'tick',text:(t>0?'+':'')+t.toFixed(1)},dots);}
pub.forEach((s,i)=>{const v=m.values[s.abbr],y=14+i*RH;const g=el('g',{'data-abbr':s.abbr},dots);
el('rect',{x:0,y:y-RH/2,width:W,height:RH,fill:'transparent'},g);
el('line',{x1:X(0),x2:X(v.d),y1:y,y2:y,stroke:'var(--axis)','stroke-width':2},g);
el('circle',{cx:X(v.d),cy:y,r:5,fill:divColor(v.d/ext),stroke:'var(--surface)','stroke-width':2},g);
el('text',{x:PL-6,y:y+4,'text-anchor':'end',text:s.abbr},g);
g.addEventListener('pointermove',ev=>{setHover(s.abbr);tipFor(ev,s.abbr);});g.addEventListener('pointerleave',()=>{setHover(null);hideTip();});});
// table
const tb=document.querySelector('#tbl tbody');tb.replaceChildren();
for(const s of pub){const v=m.values[s.abbr];const tr=el('tr',{},tb);el('td',{text:s.name},tr);el('td',{class:'n',text:v.m.toFixed(1)+'%'},tr);
el('td',{class:'n',text:(v.d>0?'+':'')+v.d.toFixed(1)},tr);el('td',{class:'n',text:String(v.n)},tr);}
history.replaceState(null,'','#'+id);}
sel.addEventListener('change',()=>draw(sel.value));
const start=location.hash.slice(1);sel.value=M.some(m=>m.id===start)?start:DATA.defaultMeasure;draw(sel.value);
"""


def build_state_tiles(data: pd.DataFrame, catalog: pd.DataFrame) -> dict:
    states_tbl = pd.read_csv(ANALYSIS / "extended_state_medians.csv")
    names = data.groupby("StateAbbr")["StateDesc"].first().to_dict()
    measures = []
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    for m in sorted(catalog[catalog["in_charts"]].itertuples(), key=lambda r: (order[r.category], r.label)):
        sub = states_tbl[states_tbl["measure"] == m.measure]
        values = {r.state: {"m": float(r.state_median), "d": float(r.difference_pp), "n": int(r.counties)}
                  for r in sub.itertuples() if r.counties > 0}
        ext = max(abs(v["d"]) for v in values.values())
        measures.append({
            "id": m.measure, "label": m.label, "category": m.category, "year": int(m.year),
            "national": float(sub["national_median"].iloc[0]), "extent": math.ceil(ext * 2) / 2,
            "counties": int(m.counties), "values": values,
            "description": catalog_desc[m.measure],
        })
    payload = {
        "measures": measures, "states": [{"abbr": a, "name": names[a]} for a in sorted(TILES)],
        "tiles": TILES, "defaultMeasure": "DEPRESSION",
    }
    body = """
<div class="controls"><label>Measure <select id="measure" aria-label="Measure"></select></label>
<button id="theme" type="button">Dark mode</button></div>
<div class="stats"><div class="stat"><div class="lab">Typical U.S. county</div><div class="val" id="nat"></div><div class="ctx" id="cov"></div></div>
<div class="stat"><div class="lab">Furthest above</div><div class="val" id="top"></div><div class="ctx">points above the typical U.S. county</div></div>
<div class="stat"><div class="lab">Furthest below</div><div class="val" id="bot"></div><div class="ctx">points below the typical U.S. county</div></div></div>
<section style="display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr);gap:14px">
<div class="card"><h2>Typical county in each state compared with the typical U.S. county</h2><p class="note" id="desc"></p>
<svg id="tiles" role="group" aria-label="US state tile map" style="width:100%;height:auto">
<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="6" height="6" fill="var(--missing)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--surface)" stroke-width="2"/></pattern></defs></svg>
<div class="legend"><span>Lower <span id="lo"></span><span class="ramp" style="background:linear-gradient(90deg,""" + ",".join(DIVERGING) + """)"></span><span id="hi"></span> higher</span>
<span><i style="background:repeating-linear-gradient(45deg,var(--missing) 0 3px,var(--surface) 3px 5px)"></i>Not published</span></div></div>
<div class="card"><h2>States ranked</h2><p class="note">Same numbers, sorted. Hover a state here or on the map to see both.</p>
<svg id="dots" role="img" aria-label="Ranked dot plot" style="width:100%;height:auto"></svg></div></section>
<div class="card"><details><summary>Table view</summary><table id="tbl"><thead><tr><th>State</th><th>Typical county</th><th>Difference (points)</th><th>Counties</th></tr></thead><tbody></tbody></table></details>
<p class="note" style="margin-top:8px">How to read: each tile is one state, all the same size so small states stay visible. The number is how many
percentage points the state's middle (median) county sits above (+, red) or below (−, blue) the middle county of the whole U.S. It is not the
state's overall rate and is not weighted by population; DC has only 1 county, DE 3 and HI 5. Red means a higher rate, which is not always worse: for checkups and screenings, higher is better. Hatched tiles: CDC did not publish this measure there,
which is not the same as zero. Measures marked 2022 are from an earlier survey year and are published in every state.</p></div>"""
    out = FINAL / "interactive_state_tiles"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "State profiles — PLACES tile map", "Extended analysis · State profiles",
        "How does each state's typical county compare with the U.S.?",
        "Pick any of 39 measures. Red: the state's typical county has a higher rate than the typical U.S. county. Blue: lower.",
        body, payload, TILES_JS), encoding="utf-8")

    # static small multiples
    show = ["DIABETES", "DEPRESSION", "FOODINSECU", "CSMOKING", "BINGE", "CHECKUP"]
    t, g = 22, 2
    pw, ph = 12 * (t + g), 8 * (t + g)
    cols, gapx, gapy = 3, 34, 64
    width = 24 * 2 + cols * pw + (cols - 1) * gapx
    height = 90 + 2 * (ph + gapy) + 30
    b = ['<text x="24" y="34" font-size="20" font-weight="700" fill="#0b0b0b">How does each state\'s typical county compare with the U.S.?</text>',
         '<text x="24" y="56" font-size="13" fill="#52514e">Points above (red) or below (blue) the typical U.S. county. Red means a higher rate, not always worse (e.g. checkups). Hatched = not published.</text>',
         '<defs><pattern id="h" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#d9d8d3"/><line x1="0" y1="0" x2="0" y2="5" stroke="#fcfcfb" stroke-width="2"/></pattern></defs>']
    by_id = {m["id"]: m for m in measures}
    for k, mid in enumerate(show):
        m = by_id[mid]
        ox = 24 + (k % cols) * (pw + gapx)
        oy = 90 + (k // cols) * (ph + gapy)
        b.append(f'<text x="{ox}" y="{oy - 8}" font-size="13" font-weight="650" fill="#0b0b0b">{esc(m["label"])} <tspan fill="#52514e" font-weight="400">· U.S. {m["national"]:.1f}%</tspan></text>')
        for abbr, (cx, cy) in TILES.items():
            v = m["values"].get(abbr)
            fill = diverging(v["d"] / m["extent"]) if v else "url(#h)"
            b.append(f'<rect x="{ox + cx * (t + g)}" y="{oy + cy * (t + g)}" width="{t}" height="{t}" rx="3" fill="{fill}"/>')
            ink = "#0b0b0b"
            if v:
                r, gg, bb = (c / 255 for c in hex_rgb(fill))
                lum = sum(w * (c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4) for w, c in zip((.2126, .7152, .0722), (r, gg, bb)))
                ink = "#0b0b0b" if lum > .36 else "#ffffff"
            b.append(f'<text x="{ox + cx * (t + g) + t / 2}" y="{oy + cy * (t + g) + 14}" font-size="8" text-anchor="middle" fill="{ink}">{abbr}</text>')
    b.append('<defs><linearGradient id="dv">' + "".join(f'<stop offset="{k / 4}" stop-color="{c}"/>' for k, c in enumerate(DIVERGING)) + '</linearGradient></defs>')
    b.append(f'<text x="24" y="{height - 16}" font-size="11" fill="#52514e">Lower</text><rect x="62" y="{height - 25}" width="140" height="10" rx="5" fill="url(#dv)"/><text x="208" y="{height - 16}" font-size="11" fill="#52514e">Higher · each panel uses its own scale · Source: CDC PLACES 2025 (i46a-9kgh), age-adjusted 2023 estimates</text>')
    (FINAL / "state_tile_small_multiples.svg").write_text(svg_doc(width, height, "State tile small multiples", b), encoding="utf-8")
    return {"tiles": len(TILES), "states_in_data": len(names), "measures": len(measures),
            "unpublished_2023_core": sorted(set(TILES) - set(by_id["DIABETES"]["values"])),
            "unpublished_hrsn": sorted(set(TILES) - set(by_id["FOODINSECU"]["values"]))}


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

GALLERY = [
    ("interactive_county_map/index.html", "1 · Where are rates highest?",
     "County map of diabetes, obesity and physical inactivity. Hover a county for its estimate and range."),
    ("interactive_relationship/index.html", "2 · Inactivity and diabetes",
     "Each dot is a county: places with more physical inactivity tend to have more diabetes."),
    ("interactive_overlap/index.html", "3 · Where problems overlap",
     "Counties in the top 25% for none, one, two or all three of the core measures."),
    ("interactive_related_measures/index.html", "4 · What else goes with it?",
     "Pick a measure and see which of the other 2023 measures rise and fall with it."),
    ("interactive_state_tiles/index.html", "5 · How does each state compare?",
     "Each state's typical county against the typical U.S. county, for 39 measures."),
]


def build_gallery() -> None:
    cards = "".join(
        f'<a class="card g" href="{href}"><h2>{esc(t)}</h2><p class="note">{esc(d)}</p></a>' for href, t, d in GALLERY)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>NTU data visualisation project — CDC PLACES 2025</title><style>{BASE_CSS}
.gal{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}a.g{{text-decoration:none;color:var(--ink)}}a.g:hover{{box-shadow:0 0 0 2px var(--accent)}}
</style></head><body><div class="viz-root"><main class="app"><header><div class="kicker">SD6105 · CDC PLACES county data, 2025 release</div>
<h1>Adult health across U.S. counties</h1><div class="sub">Five interactive views of CDC estimates for 3,143 U.S. counties. Views 1–3 focus on diabetes,
obesity and physical inactivity; views 4–5 widen the lens to all measures. All rates are age-adjusted so counties with older or younger
populations can be compared fairly.</div></header>
<section class="gal">{cards}</section>
<p class="foot">Source: CDC PLACES County Data (GIS Friendly Format), 2025 release (i46a-9kgh); U.S. Census Bureau 2023 county boundaries.
Values are model-based estimates, not direct counts. They describe counties, not individuals, and show association, not cause.</p></main></div></body></html>
"""
    (FINAL / "index.html").write_text(doc, encoding="utf-8")


catalog_desc: dict[str, str] = {}


def main() -> None:
    manifest = json.loads((ANALYSIS / "extended_manifest.json").read_text(encoding="utf-8"))
    digest = sha256(INPUT)
    if manifest.get("input_sha256") != digest:
        raise SystemExit("Cleaned CSV hash differs from the extended analysis manifest. Re-run extended_analysis.py.")
    data = pd.read_csv(INPUT, dtype={"CountyFIPS": str}, encoding="utf-8-sig")
    catalog = pd.read_csv(ANALYSIS / "extended_measure_catalog.csv")
    fields = pd.read_csv(DATA_ROOT / "processed/places_county_gis_2025_field_dictionary.csv")
    for r in fields[fields["column_name"].str.endswith("_AdjPrev")].itertuples():
        catalog_desc[r.column_name.removesuffix("_AdjPrev")] = r.description
    checks = {"related": build_related(data, catalog), "state_tiles": build_state_tiles(data, catalog)}
    build_gallery()
    ok = (checks["related"]["symmetric"] and checks["related"]["measures"] == 34
          and checks["related"]["excluded"] == ["BPMED"]
          and checks["state_tiles"]["tiles"] == checks["state_tiles"]["states_in_data"] == 51
          and checks["state_tiles"]["measures"] == 39
          and checks["state_tiles"]["unpublished_2023_core"] == ["KY", "PA"]
          and len(checks["state_tiles"]["unpublished_hrsn"]) == 11)
    outputs = sorted(str(p.relative_to(ROOT)) for p in [
        FINAL / "index.html", FINAL / "related_measures_diabetes.svg", FINAL / "state_tile_small_multiples.svg",
        FINAL / "interactive_related_measures/index.html", FINAL / "interactive_state_tiles/index.html"])
    result = {"status": "PASS" if ok else "FAIL", "input_sha256": digest, "checks": checks, "outputs": outputs}
    VALIDATION_OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
