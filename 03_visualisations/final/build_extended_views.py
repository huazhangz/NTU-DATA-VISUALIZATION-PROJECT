#!/usr/bin/env python3
"""Build the three extended visualisations from the extended analysis outputs.

Views (forms not used elsewhere in the project):

* interactive_measure_landscape/ - clustered Spearman heatmap with a
  dendrogram, plus an on-demand hexbin density plot for any measure pair.
* interactive_state_tiles/      - US state tile-grid cartogram on a diverging
  scale, linked to a ranked dot plot.
* interactive_age_gap/          - ridgeline of crude minus age-adjusted gaps,
  linked to a county dumbbell profile.

Each view also gets a static SVG. Run ``02_analysis/extended_analysis.py``
first. Standard library plus pandas/numpy (already required by the project).
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
CATEGORY_ORDER = ["Health outcome", "Health status", "Risk behavior", "Prevention", "Disability", "Social need"]
CATEGORY_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
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
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--accent:#2a78d6;--missing:#d9d8d3;--focus:#eda100}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface:#1a1a19;
--plane:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--accent:#3987e5;--missing:#454542}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface:#1a1a19;--plane:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--accent:#3987e5;--missing:#454542}
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
# 1. Measure landscape
# ---------------------------------------------------------------------------

LANDSCAPE_JS = r"""
const M=DATA.measures, N=M.length, ORDER=DATA.order, CELL=17, LABW=210, DENH=70, TOP=DENH+6;
const heat=document.getElementById('heat');
const W=LABW+N*CELL+10, H=TOP+N*CELL+10;
heat.setAttribute('viewBox',`0 0 ${W} ${H}`);
const idx=Object.fromEntries(M.map((m,i)=>[m.id,i]));
const pos=Object.fromEntries(ORDER.map((id,i)=>[id,i]));
// dendrogram
const dg=el('g',{transform:`translate(${LABW},0)`},heat);
const maxH=Math.max(...DATA.merges.map(m=>m.height));
const nodeX={}, nodeY={};
DATA.leaf.forEach((id,i)=>{nodeX[i]=pos[id]*CELL+CELL/2;nodeY[i]=DENH;});
const yH=h=>DENH-(h/maxH)*(DENH-6);
for(const m of DATA.merges){const xl=nodeX[m.left],xr=nodeX[m.right],y=yH(m.height);
el('path',{d:`M${xl},${nodeY[m.left]}V${y}H${xr}V${nodeY[m.right]}`,fill:'none',stroke:'var(--muted)','stroke-width':1},dg);
nodeX[m.id]=(xl+xr)/2;nodeY[m.id]=y;}
const cutY=yH(DATA.cut);el('line',{x1:0,x2:N*CELL,y1:cutY,y2:cutY,stroke:'var(--axis)','stroke-dasharray':'3 3'},dg);
el('text',{x:-4,y:cutY+3,'text-anchor':'end',text:'cut',class:'tick'},dg);
// cells
const cg=el('g',{transform:`translate(${LABW},${TOP})`},heat);
for(let r=0;r<N;r++)for(let c=0;c<N;c++){const a=ORDER[r],b=ORDER[c];const v=DATA.rho[idx[a]][idx[b]];
el('rect',{x:c*CELL+1,y:r*CELL+1,width:CELL-2,height:CELL-2,rx:2,fill:a===b?'var(--grid)':divColor(v),'data-r':r,'data-c':c},cg);}
// cluster blocks
let start=0;for(let i=1;i<=N;i++){if(i===N||DATA.group[ORDER[i]]!==DATA.group[ORDER[start]]){
el('rect',{x:start*CELL,y:start*CELL,width:(i-start)*CELL,height:(i-start)*CELL,fill:'none',stroke:'var(--ink)','stroke-width':1.5,rx:3},cg);start=i;}}
const hl=el('rect',{fill:'none',stroke:'var(--ink)','stroke-width':2,width:CELL,height:CELL,rx:3,visibility:'hidden'},cg);
// labels
const lg=el('g',{transform:`translate(0,${TOP})`},heat);
ORDER.forEach((id,r)=>{const m=M[idx[id]];
el('rect',{x:LABW-14,y:r*CELL+4,width:9,height:9,rx:2,fill:DATA.catColor[m.category]},lg);
el('text',{x:LABW-19,y:r*CELL+CELL/2+4,'text-anchor':'end',text:m.label+(m.core?' •':'')},lg);});
let sel=null;
function cellAt(ev){const pt=heat.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;const p=pt.matrixTransform(heat.getScreenCTM().inverse());
const c=Math.floor((p.x-LABW)/CELL),r=Math.floor((p.y-TOP)/CELL);return(r>=0&&c>=0&&r<N&&c<N)?[r,c]:null;}
heat.addEventListener('pointermove',ev=>{const rc=cellAt(ev);if(!rc){hl.setAttribute('visibility','hidden');hideTip();return;}
const[r,c]=rc;hl.setAttribute('x',c*CELL);hl.setAttribute('y',r*CELL);hl.setAttribute('visibility','visible');
const a=M[idx[ORDER[r]]],b=M[idx[ORDER[c]]];
showTip(ev,t=>tipRow(t,a===b?'—':'ρ = '+DATA.rho[idx[a.id]][idx[b.id]].toFixed(2),[a.label,'× '+b.label,
['Counties',DATA.n[idx[a.id]][idx[b.id]].toLocaleString()],a===b?'':'Click to open the density plot']));});
heat.addEventListener('pointerleave',()=>{hl.setAttribute('visibility','hidden');hideTip();});
heat.addEventListener('click',ev=>{const rc=cellAt(ev);if(!rc||rc[0]===rc[1])return;setPair(ORDER[rc[1]],ORDER[rc[0]]);});
// selects
const sx=document.getElementById('sx'),sy=document.getElementById('sy');
for(const s of[sx,sy])for(const id of ORDER){const o=el('option',{value:id,text:M[idx[id]].label},s);}
sx.addEventListener('change',()=>setPair(sx.value,sy.value));sy.addEventListener('change',()=>setPair(sx.value,sy.value));
// hexbin
const hex=document.getElementById('hex');const HW=460,HH=400,PL=48,PB=40,PT=10,PR=12,R=7;
hex.setAttribute('viewBox',`0 0 ${HW} ${HH}`);
const BLUE=['#cde2fb','#9ec5f4','#6da7ec','#3987e5','#256abf','#184f95','#0d366b'];
function setPair(x,y){if(x===y)return;sx.value=x;sy.value=y;const ix=idx[x],iy=idx[y];
hex.replaceChildren();const xs=DATA.values[ix],ys=DATA.values[iy];const pts=[];
for(let i=0;i<xs.length;i++)if(xs[i]!==null&&ys[i]!==null)pts.push([xs[i],ys[i]]);
const ext=a=>{let lo=Infinity,hi=-Infinity;for(const v of a){if(v<lo)lo=v;if(v>hi)hi=v;}const pad=(hi-lo)*.04||1;return[lo-pad,hi+pad];};
const[x0,x1]=ext(pts.map(p=>p[0])),[y0,y1]=ext(pts.map(p=>p[1]));
const X=v=>PL+(v-x0)/(x1-x0)*(HW-PL-PR),Y=v=>HH-PB-(v-y0)/(y1-y0)*(HH-PB-PT);
const ticks=(a,b)=>{const s=[1,2,2.5,5,10,20];const raw=(b-a)/5;const mag=10**Math.floor(Math.log10(raw));const st=s.map(k=>k*mag).find(k=>k>=raw);
const out=[];for(let v=Math.ceil(a/st)*st;v<=b;v+=st)out.push(+v.toFixed(6));return out;};
for(const t of ticks(x0,x1)){el('line',{x1:X(t),x2:X(t),y1:PT,y2:HH-PB,class:'gridline'},hex);el('text',{x:X(t),y:HH-PB+14,'text-anchor':'middle',class:'tick',text:t+'%'},hex);}
for(const t of ticks(y0,y1)){el('line',{x1:PL,x2:HW-PR,y1:Y(t),y2:Y(t),class:'gridline'},hex);el('text',{x:PL-6,y:Y(t)+4,'text-anchor':'end',class:'tick',text:t+'%'},hex);}
el('line',{x1:PL,x2:HW-PR,y1:HH-PB,y2:HH-PB,class:'axisline'},hex);
el('text',{x:(PL+HW-PR)/2,y:HH-4,'text-anchor':'middle',text:M[ix].label},hex);
el('text',{x:12,y:(PT+HH-PB)/2,'text-anchor':'middle',transform:`rotate(-90 12 ${(PT+HH-PB)/2})`,text:M[iy].label},hex);
const dx=R*Math.sqrt(3),dy=R*1.5,bins=new Map();
for(const[vx,vy]of pts){const px=X(vx),py=Y(vy);let row=Math.round(py/dy);let col=Math.round((px-(row&1?dx/2:0))/dx);
let best=null,bd=1e9;for(const rr of[row-1,row,row+1])for(const cc of[col-1,col,col+1]){const cx=cc*dx+(rr&1?dx/2:0),cy=rr*dy;
const d=(px-cx)**2+(py-cy)**2;if(d<bd){bd=d;best=[rr,cc,cx,cy];}}const k=best[0]+','+best[1];
if(!bins.has(k))bins.set(k,{cx:best[2],cy:best[3],n:0});bins.get(k).n++;}
const maxN=Math.max(...[...bins.values()].map(b=>b.n));
const hp=[];for(let a=0;a<6;a++){const t=Math.PI/180*(60*a-30);hp.push([R*Math.cos(t),R*Math.sin(t)]);}
for(const b of bins.values()){const lvl=Math.min(BLUE.length-1,Math.floor(Math.log(b.n)/Math.log(maxN+1)*BLUE.length));
const p=el('polygon',{points:hp.map(([u,v])=>`${(b.cx+u*.94).toFixed(1)},${(b.cy+v*.94).toFixed(1)}`).join(' '),fill:BLUE[lvl]},hex);
p.addEventListener('pointermove',ev=>showTip(ev,t=>tipRow(t,b.n+' counties',['in this hexagon'])));p.addEventListener('pointerleave',hideTip);}
document.getElementById('pairStat').textContent=`ρ = ${DATA.rho[ix][iy].toFixed(2)} · ${pts.length.toLocaleString()} counties with both estimates`;
document.getElementById('hexmax').textContent=maxN;}
// table
const tb=document.querySelector('#pairs tbody');
for(const p of DATA.topPairs){const tr=el('tr',{},tb);el('td',{text:M[idx[p.a]].label},tr);el('td',{text:M[idx[p.b]].label},tr);
el('td',{class:'n',text:p.rho.toFixed(2)},tr);el('td',{class:'n',text:p.n.toLocaleString()},tr);}
setPair(DATA.defaultPair[0],DATA.defaultPair[1]);
"""


def build_landscape(data: pd.DataFrame, catalog: pd.DataFrame) -> dict:
    clusters = json.loads((ANALYSIS / "extended_clusters.json").read_text(encoding="utf-8"))
    pairs = pd.read_csv(ANALYSIS / "extended_spearman_pairs.csv")
    leaf = clusters["leaf_names"]
    cols = [f"{m}_AdjPrev" for m in leaf]
    rho = data[cols].rank().corr(min_periods=500).to_numpy()
    present = data[cols].notna().astype(int)
    n = present.T.dot(present).to_numpy()
    lab = catalog.set_index("measure")
    measures = [{"id": m, "label": lab.loc[m, "label"], "category": lab.loc[m, "category"],
                 "core": bool(lab.loc[m, "core_eda"])} for m in leaf]
    values = [[num(v, 1) for v in data[c]] for c in cols]
    top = pd.concat([pairs.sort_values("rho", ascending=False).head(12), pairs.head(8)])
    payload = {
        "measures": measures, "order": clusters["order"], "leaf": leaf, "merges": clusters["merges"],
        "cut": clusters["cut_height"], "group": clusters["groups"],
        "rho": [[round(float(v), 3) for v in row] for row in rho], "n": n.tolist(), "values": values,
        "catColor": dict(zip(CATEGORY_ORDER, CATEGORY_COLORS)),
        "topPairs": top.to_dict("records"), "defaultPair": ["FOODINSECU", "DEPRESSION"],
    }
    legend = "".join(f'<span><i style="background:{c}"></i>{esc(k)}</span>' for k, c in zip(CATEGORY_ORDER, CATEGORY_COLORS))
    body = f"""
<div class="controls"><label>Density plot: x <select id="sx" aria-label="x measure"></select></label>
<label>y <select id="sy" aria-label="y measure"></select></label><button id="theme" type="button">Dark mode</button></div>
<section style="display:grid;grid-template-columns:minmax(0,1.35fr) minmax(320px,1fr);gap:14px">
<div class="card"><h2>Spearman correlation, 35 measures (2023 estimates)</h2>
<p class="note">Rows and columns ordered by average-linkage clustering on 1 − ρ. Outlined blocks are the five groups cut at
height {clusters['cut_height']}. • marks the three core-EDA measures. Hover a cell for ρ; click to open its density plot.</p>
<svg id="heat" role="img" aria-label="Clustered correlation heatmap" style="width:100%;height:auto"></svg>
<div class="legend"><span>ρ −1<span class="ramp" style="background:linear-gradient(90deg,{','.join(DIVERGING)})"></span>+1</span>{legend}</div>
</div>
<div style="display:flex;flex-direction:column;gap:14px">
<div class="card"><h2>Pair density (hexbin)</h2><p class="note" id="pairStat"></p>
<svg id="hex" role="img" aria-label="Hexbin density plot" style="width:100%;height:auto"></svg>
<div class="legend"><span>Counties per hexagon: 1<span class="ramp" style="background:linear-gradient(90deg,#cde2fb,#6da7ec,#256abf,#0d366b)"></span><span id="hexmax"></span> (log scale)</span></div></div>
<div class="card"><h2>Reading this view</h2><p class="note">One large group holds chronic outcomes, health status, disability and all
seven social-need measures: counties high on one tend to be high on the rest. Binge drinking, cancer and cholesterol screening sit apart and
run opposite. PLACES estimates share model covariates, so very high ρ (0.95+) partly reflects the model, not independent evidence.
Social-need pairs use the 2,299 counties where those measures are published.</p>
<details><summary>Table view: strongest pairs</summary><table id="pairs"><thead><tr><th>Measure A</th><th>Measure B</th><th>ρ</th><th>Counties</th></tr></thead><tbody></tbody></table></details></div>
</div></section>"""
    out = FINAL / "interactive_measure_landscape"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "Measure landscape — PLACES county estimates", "Extended analysis · Measure landscape",
        "Most PLACES burdens rise and fall together across counties",
        "How 35 age-adjusted county estimates for 2023 co-vary. Kentucky and Pennsylvania have no 2023 estimates; social-need measures are blank in nine more states.",
        body, payload, LANDSCAPE_JS), encoding="utf-8")

    # static SVG
    order = clusters["order"]
    pos = {m: i for i, m in enumerate(order)}
    ix = {m: i for i, m in enumerate(leaf)}
    cell, labw, denh = 18, 230, 80
    top_y = 70 + denh
    width, height = labw + len(order) * cell + 40, top_y + len(order) * cell + 92
    b = [f'<text x="24" y="34" font-size="20" font-weight="700" fill="#0b0b0b">Most PLACES burdens rise and fall together across counties</text>',
         f'<text x="24" y="56" font-size="13" fill="#52514e">Spearman ρ between 35 age-adjusted county estimates (2023), ordered by average-linkage clustering; outlined blocks = 5 groups.</text>']
    nx = {i: labw + pos[m] * cell + cell / 2 for i, m in enumerate(leaf)}
    ny = {i: float(top_y - 4) for i in range(len(leaf))}
    max_h = max(m["height"] for m in clusters["merges"])
    for m in clusters["merges"]:
        y = top_y - 4 - m["height"] / max_h * (denh - 8)
        b.append(f'<path d="M{nx[m["left"]]:.1f},{ny[m["left"]]:.1f}V{y:.1f}H{nx[m["right"]]:.1f}V{ny[m["right"]]:.1f}" fill="none" stroke="#898781"/>')
        nx[m["id"]] = (nx[m["left"]] + nx[m["right"]]) / 2
        ny[m["id"]] = y
    for r, a in enumerate(order):
        meta = lab.loc[a]
        color = dict(zip(CATEGORY_ORDER, CATEGORY_COLORS))[meta["category"]]
        b.append(f'<rect x="{labw - 15}" y="{top_y + r * cell + 4}" width="10" height="10" rx="2" fill="{color}"/>')
        b.append(f'<text x="{labw - 20}" y="{top_y + r * cell + 13}" font-size="11" text-anchor="end" fill="#52514e">{esc(meta["label"])}</text>')
        for c, bb in enumerate(order):
            fill = "#e1e0d9" if a == bb else diverging(rho[ix[a]][ix[bb]])
            b.append(f'<rect x="{labw + c * cell + 1}" y="{top_y + r * cell + 1}" width="{cell - 2}" height="{cell - 2}" rx="2" fill="{fill}"/>')
    start = 0
    for i in range(1, len(order) + 1):
        if i == len(order) or clusters["groups"][order[i]] != clusters["groups"][order[start]]:
            s = (i - start) * cell
            b.append(f'<rect x="{labw + start * cell}" y="{top_y + start * cell}" width="{s}" height="{s}" fill="none" stroke="#0b0b0b" stroke-width="1.5" rx="3"/>')
            start = i
    ly = top_y + len(order) * cell + 26
    b.append('<defs><linearGradient id="dv">' + "".join(f'<stop offset="{k / 4}" stop-color="{c}"/>' for k, c in enumerate(DIVERGING)) + '</linearGradient></defs>')
    b.append(f'<text x="{labw}" y="{ly + 9}" font-size="11" fill="#52514e">ρ −1</text><rect x="{labw + 32}" y="{ly}" width="160" height="10" rx="5" fill="url(#dv)"/><text x="{labw + 198}" y="{ly + 9}" font-size="11" fill="#52514e">+1</text>')
    x, ry = labw, ly + 22
    for k, c in zip(CATEGORY_ORDER, CATEGORY_COLORS):
        b.append(f'<rect x="{x}" y="{ry}" width="10" height="10" rx="2" fill="{c}"/><text x="{x + 14}" y="{ry + 9}" font-size="11" fill="#52514e">{esc(k)}</text>')
        x += 14 + len(k) * 6.4 + 16
    b.append(f'<text x="24" y="{height - 14}" font-size="11" fill="#898781">Source: CDC PLACES 2025 county release (i46a-9kgh). Pairwise-complete counties (2,956; 2,299 for social-need pairs). Descriptive, ecological.</text>')
    (FINAL / "measure_landscape_heatmap.svg").write_text(svg_doc(width, height, "Clustered correlation heatmap", b), encoding="utf-8")
    return {"measures": len(leaf), "symmetric": bool(np.allclose(rho, rho.T)), "groups": len(set(clusters["groups"].values()))}


# ---------------------------------------------------------------------------
# 2. State tiles
# ---------------------------------------------------------------------------

TILES_JS = r"""
const M=DATA.measures, S=DATA.states, T=50, G=4;
const mapSvg=document.getElementById('tiles'), dots=document.getElementById('dots');
mapSvg.setAttribute('viewBox',`0 0 ${12*(T+G)} ${8*(T+G)}`);
const sel=document.getElementById('measure');
const cats=[...new Set(M.map(m=>m.category))];
for(const c of cats){const og=el('optgroup',{label:c},sel);for(const m of M.filter(m=>m.category===c))el('option',{value:m.id,text:`${m.label} (${m.year})`},og);}
let current=null, hover=null;
const tileEls={};
for(const s of S){const[cx,cy]=DATA.tiles[s.abbr];const g=el('g',{transform:`translate(${cx*(T+G)},${cy*(T+G)})`,tabindex:0,role:'img'},mapSvg);
const r=el('rect',{width:T,height:T,rx:6},g);const t1=el('text',{x:T/2,y:21,'text-anchor':'middle','font-size':13,'font-weight':650},g);
const t2=el('text',{x:T/2,y:38,'text-anchor':'middle','font-size':11},g);tileEls[s.abbr]={g,r,t1,t2};
g.addEventListener('pointermove',ev=>{setHover(s.abbr);tipFor(ev,s.abbr);});g.addEventListener('pointerleave',()=>{setHover(null);hideTip();});
g.addEventListener('focus',()=>{setHover(s.abbr);const b=g.getBoundingClientRect();tipFor({clientX:b.right,clientY:b.top},s.abbr);});
g.addEventListener('blur',()=>{setHover(null);hideTip();});}
function tipFor(ev,abbr){const m=M.find(m=>m.id===current),v=m.values[abbr],s=S.find(s=>s.abbr===abbr);
showTip(ev,t=>v?tipRow(t,(v.d>0?'+':'')+v.d.toFixed(1)+' pp',[s.name,['State county median',v.m.toFixed(1)+'%'],['National county median',m.national.toFixed(1)+'%'],['Counties',String(v.n)]])
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
document.getElementById('cov').textContent=`${pub.length} of 51 states published · ${m.counties.toLocaleString()} counties`;
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
    for m in sorted(catalog.itertuples(), key=lambda r: (order[r.category], r.label)):
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
<div class="stats"><div class="stat"><div class="lab">National county median</div><div class="val" id="nat"></div><div class="ctx" id="cov"></div></div>
<div class="stat"><div class="lab">Furthest above</div><div class="val" id="top"></div><div class="ctx">percentage points vs national</div></div>
<div class="stat"><div class="lab">Furthest below</div><div class="val" id="bot"></div><div class="ctx">percentage points vs national</div></div></div>
<section style="display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr);gap:14px">
<div class="card"><h2>State median of county estimates minus national county median</h2><p class="note" id="desc"></p>
<svg id="tiles" role="group" aria-label="US state tile map" style="width:100%;height:auto">
<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="6" height="6" fill="var(--missing)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--surface)" stroke-width="2"/></pattern></defs></svg>
<div class="legend"><span>Below national <span id="lo"></span><span class="ramp" style="background:linear-gradient(90deg,""" + ",".join(DIVERGING) + """)"></span><span id="hi"></span> above</span>
<span><i style="background:repeating-linear-gradient(45deg,var(--missing) 0 3px,var(--surface) 3px 5px)"></i>Not published</span></div></div>
<div class="card"><h2>States ranked</h2><p class="note">Same values; hover links to the map. Scale is symmetric around the national median.</p>
<svg id="dots" role="img" aria-label="Ranked dot plot" style="width:100%;height:auto"></svg></div></section>
<div class="card"><details><summary>Table view</summary><table id="tbl"><thead><tr><th>State</th><th>County median</th><th>Δ pp</th><th>Counties</th></tr></thead><tbody></tbody></table></details>
<p class="note" style="margin-top:8px">Each tile is one state, equal size regardless of area, so small states stay visible. Values are medians of county
estimates (not population-weighted state prevalence); DC has 1 county, DE 3, HI 5. Five measures (colorectal screening, dental visit,
mammography, short sleep, all teeth lost) are 2022 estimates and are published in every state.</p></div>"""
    out = FINAL / "interactive_state_tiles"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "State profiles — PLACES tile map", "Extended analysis · State profiles",
        "Where each state's counties sit against the national county median",
        "Pick any of the 40 age-adjusted measures. Red means the state's median county is above the national county median, blue below.",
        body, payload, TILES_JS), encoding="utf-8")

    # static small multiples
    show = ["DEPRESSION", "FOODINSECU", "LONELINESS", "CSMOKING", "BINGE", "CHECKUP"]
    t, g = 22, 2
    pw, ph = 12 * (t + g), 8 * (t + g)
    cols, gapx, gapy = 3, 34, 64
    width = 24 * 2 + cols * pw + (cols - 1) * gapx
    height = 90 + 2 * (ph + gapy) + 30
    b = ['<text x="24" y="34" font-size="20" font-weight="700" fill="#0b0b0b">Where each state\'s counties sit against the national county median</text>',
         '<text x="24" y="56" font-size="13" fill="#52514e">State median of county age-adjusted estimates minus national county median (pp). Hatched = not published.</text>',
         '<defs><pattern id="h" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#d9d8d3"/><line x1="0" y1="0" x2="0" y2="5" stroke="#fcfcfb" stroke-width="2"/></pattern></defs>']
    by_id = {m["id"]: m for m in measures}
    for k, mid in enumerate(show):
        m = by_id[mid]
        ox = 24 + (k % cols) * (pw + gapx)
        oy = 90 + (k // cols) * (ph + gapy)
        b.append(f'<text x="{ox}" y="{oy - 8}" font-size="13" font-weight="650" fill="#0b0b0b">{esc(m["label"])} <tspan fill="#52514e" font-weight="400">· national {m["national"]:.1f}% · ±{m["extent"]:.1f} pp</tspan></text>')
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
    b.append(f'<text x="24" y="{height - 16}" font-size="11" fill="#52514e">Below</text><rect x="62" y="{height - 25}" width="140" height="10" rx="5" fill="url(#dv)"/><text x="208" y="{height - 16}" font-size="11" fill="#52514e">Above national · each panel scaled to its own largest gap · Source: CDC PLACES 2025 (i46a-9kgh)</text>')
    (FINAL / "state_tile_small_multiples.svg").write_text(svg_doc(width, height, "State tile small multiples", b), encoding="utf-8")
    return {"tiles": len(TILES), "states_in_data": len(names), "measures": len(measures),
            "unpublished_2023_core": sorted(set(TILES) - set(by_id["DIABETES"]["values"])),
            "unpublished_hrsn": sorted(set(TILES) - set(by_id["FOODINSECU"]["values"]))}


# ---------------------------------------------------------------------------
# 3. Age-adjustment gap
# ---------------------------------------------------------------------------

AGE_JS = r"""
const M=DATA.measures, C=DATA.counties, RH=26, LW=230, RW=420, W=LW+RW, TOP=26;
const ridge=document.getElementById('ridge'), bell=document.getElementById('bell');
const H=TOP+M.length*RH+52;ridge.setAttribute('viewBox',`0 0 ${W} ${H}`);
const BW=520;bell.setAttribute('viewBox',`0 0 ${BW} ${H}`);
const g0=DATA.range[0],g1=DATA.range[1];const X=v=>LW+(v-g0)/(g1-g0)*(RW-14);
for(let t=Math.ceil(g0/5)*5;t<=g1;t+=5){el('line',{x1:X(t),x2:X(t),y1:TOP-8,y2:H-40,class:t===0?'axisline':'gridline'},ridge);
el('text',{x:X(t),y:H-26,'text-anchor':'middle',class:'tick',text:(t>0?'+':'')+t},ridge);}
el('text',{x:X(0)+4,y:TOP-12,text:'crude = adjusted',class:'tick'},ridge);
el('text',{x:LW+RW/2,y:H-4,'text-anchor':'middle',text:'Crude minus age-adjusted (percentage points)'},ridge);
const marks=[];
M.forEach((m,i)=>{const base=TOP+i*RH+RH*.9;const g=el('g',{},ridge);
const pts=m.kde.map(([x,d])=>`${X(x).toFixed(1)},${(base-d*RH*1.55).toFixed(1)}`);
el('path',{d:`M${X(m.kde[0][0])},${base}L${pts.join('L')}L${X(m.kde[m.kde.length-1][0])},${base}Z`,fill:'var(--accent)','fill-opacity':.28,stroke:'var(--accent)','stroke-width':1.5},g);
el('line',{x1:X(m.p05),x2:X(m.p95),y1:base,y2:base,stroke:'var(--ink2)','stroke-width':2},g);
el('line',{x1:X(m.median),x2:X(m.median),y1:base-5,y2:base+3,stroke:'var(--ink)','stroke-width':2},g);
el('text',{x:LW-8,y:base-2,'text-anchor':'end',text:m.label+(m.year===2022?' (2022)':'')},g);
const mk=el('circle',{r:5,cy:base,fill:'#eb6834',stroke:'var(--surface)','stroke-width':2,visibility:'hidden'},g);marks.push(mk);
const hit=el('rect',{x:0,y:base-RH,width:W,height:RH,fill:'transparent'},g);
hit.addEventListener('pointermove',ev=>showTip(ev,t=>{const c=C[cur],gv=gap(c,i);tipRow(t,(m.median>0?'+':'')+m.median.toFixed(1)+' pp median',
[m.label,['5th–95th pct',`${m.p05.toFixed(1)} to ${m.p95.toFixed(1)}`],['Crude higher in',Math.round(m.share*100)+'% of counties'],
gv===null?'Selected county: not published':['Selected county',(gv>0?'+':'')+gv.toFixed(1)+' pp']]);}));
hit.addEventListener('pointerleave',hideTip);});
function gap(c,i){const cr=c.v[2*i],ad=c.v[2*i+1];return cr===null||ad===null?null:+(cr-ad).toFixed(2);}
// dumbbell
const BX=v=>60+v/DATA.vmax*(BW-80);
for(let t=0;t<=DATA.vmax;t+=20){el('line',{x1:BX(t),x2:BX(t),y1:TOP-8,y2:H-40,class:'gridline'},bell);
el('text',{x:BX(t),y:H-26,'text-anchor':'middle',class:'tick',text:t+'%'},bell);}
el('text',{x:BW/2,y:H-4,'text-anchor':'middle',text:'Prevalence (%)'},bell);
const rows=M.map((m,i)=>{const base=TOP+i*RH+RH*.9-6;const g=el('g',{},bell);
const ln=el('line',{y1:base,y2:base,stroke:'var(--axis)','stroke-width':3,'stroke-linecap':'round'},g);
const a=el('circle',{r:5,cy:base,fill:'var(--surface)',stroke:'var(--accent)','stroke-width':2.5},g);
const b=el('circle',{r:5,cy:base,fill:'#eb6834',stroke:'var(--surface)','stroke-width':1.5},g);
const tx=el('text',{y:base+4,class:'tick'},g);
const hit=el('rect',{x:0,y:base-RH+6,width:BW,height:RH,fill:'transparent'},g);
hit.addEventListener('pointermove',ev=>showTip(ev,t=>{const c=C[cur];const cr=c.v[2*i],ad=c.v[2*i+1];
cr===null?tipRow(t,'Not published',[m.label]):tipRow(t,`${cr.toFixed(1)}% crude`,[m.label,['Age-adjusted',ad.toFixed(1)+'%'],['Gap',((cr-ad)>0?'+':'')+(cr-ad).toFixed(1)+' pp']]);}));
hit.addEventListener('pointerleave',hideTip);return{ln,a,b,tx};});
let cur=DATA.defaultCounty;
function setCounty(i){cur=i;const c=C[i];document.getElementById('cname').textContent=`${c.name}, ${c.st}`;
document.getElementById('cidx').textContent=(c.idx===null?'n/a':(c.idx>0?'+':'')+c.idx.toFixed(2));
document.getElementById('crank').textContent=c.rank===null?'not ranked (2023 estimates not published)':`rank ${c.rank.toLocaleString()} of ${DATA.ranked.toLocaleString()} (1 = oldest-skewing)`;
document.getElementById('cpop').textContent=c.pop.toLocaleString();
M.forEach((m,k)=>{const gv=gap(c,k);if(gv===null)marks[k].setAttribute('visibility','hidden');else{marks[k].setAttribute('cx',X(Math.max(g0,Math.min(g1,gv))));marks[k].setAttribute('visibility','visible');}
const r=rows[k],cr=c.v[2*k],ad=c.v[2*k+1];if(cr===null){r.ln.setAttribute('visibility','hidden');r.a.setAttribute('visibility','hidden');r.b.setAttribute('visibility','hidden');
r.tx.setAttribute('x',BX(0));r.tx.textContent='not published';return;}
for(const e of[r.ln,r.a,r.b])e.setAttribute('visibility','visible');
r.ln.setAttribute('x1',BX(Math.min(cr,ad)));r.ln.setAttribute('x2',BX(Math.max(cr,ad)));r.a.setAttribute('cx',BX(ad));r.b.setAttribute('cx',BX(cr));
r.tx.setAttribute('x',BX(Math.max(cr,ad))+9);r.tx.textContent=((cr-ad)>0?'+':'')+(cr-ad).toFixed(1);});
document.getElementById('search').value=`${c.name}, ${c.st}`;}
const dl=document.getElementById('clist');C.forEach(c=>el('option',{value:`${c.name}, ${c.st}`},dl));
const lookup=new Map(C.map((c,i)=>[`${c.name}, ${c.st}`.toLowerCase(),i]));
document.getElementById('search').addEventListener('change',e=>{const i=lookup.get(e.target.value.trim().toLowerCase());if(i!==undefined)setCounty(i);});
document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>setCounty(+b.dataset.preset)));
const tb=document.querySelector('#tbl tbody');
for(const m of M){const tr=el('tr',{},tb);el('td',{text:m.label},tr);el('td',{class:'n',text:String(m.year)},tr);
el('td',{class:'n',text:(m.median>0?'+':'')+m.median.toFixed(2)},tr);el('td',{class:'n',text:`${m.p05.toFixed(1)} to ${m.p95.toFixed(1)}`},tr);
el('td',{class:'n',text:Math.round(m.share*100)+'%'},tr);}
setCounty(cur);
"""


def kde(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    sd = values.std()
    iqr = np.subtract(*np.percentile(values, [75, 25]))
    bw = 0.9 * min(sd, iqr / 1.34 if iqr > 0 else sd) * len(values) ** -0.2
    bw = max(bw, 0.08)
    dens = np.exp(-0.5 * ((grid[:, None] - values[None, :]) / bw) ** 2).sum(axis=1)
    return dens / dens.max()


def build_age_gap(data: pd.DataFrame, catalog: pd.DataFrame) -> dict:
    gaps = pd.read_csv(ANALYSIS / "extended_age_adjustment_gap.csv")  # sorted desc by median gap
    idx = pd.read_csv(ANALYSIS / "extended_county_age_gap_index.csv", dtype={"CountyFIPS": str})
    order = gaps["measure"].tolist()
    lo = float(np.floor(min(gaps["p05"].min(), -5)))
    hi = float(np.ceil(gaps["p95"].max() + 2))
    measures = []
    for r in gaps.itertuples():
        g = (data[f"{r.measure}_CrudePrev"] - data[f"{r.measure}_AdjPrev"]).dropna().to_numpy()
        a, b = np.percentile(g, [0.5, 99.5])
        grid = np.linspace(max(a, lo), min(b, hi), 90)
        measures.append({"id": r.measure, "label": r.label, "year": int(r.year), "median": r.median_gap_pp,
                         "p05": r.p05, "p95": r.p95, "share": r.share_crude_higher,
                         "kde": [[round(float(x), 2), round(float(d), 3)] for x, d in zip(grid, kde(g, grid))]})
    rank = {f: i + 1 for i, f in enumerate(idx["CountyFIPS"])}
    gi = dict(zip(idx["CountyFIPS"], idx["age_gap_index"]))
    sorted_data = data.sort_values(["StateAbbr", "derived__CountyName_display"]).reset_index(drop=True)
    counties = []
    for row in sorted_data.itertuples(index=False):
        rec = row._asdict()
        v = []
        for m in order:
            v += [num(rec[f"{m}_CrudePrev"]), num(rec[f"{m}_AdjPrev"])]
        counties.append({"fips": rec["CountyFIPS"], "name": rec["derived__CountyName_display"], "st": rec["StateAbbr"],
                         "pop": int(rec["TotalPopulation"]), "v": v,
                         "idx": num(gi.get(rec["CountyFIPS"]), 2), "rank": rank.get(rec["CountyFIPS"])})
    pos = {c["fips"]: i for i, c in enumerate(counties)}
    oldest, youngest = idx["CountyFIPS"].iloc[0], idx["CountyFIPS"].iloc[-1]
    middle = idx["CountyFIPS"].iloc[len(idx) // 2]
    vmax = 100
    payload = {"measures": measures, "counties": counties, "range": [lo, hi], "vmax": vmax,
               "defaultCounty": pos[oldest], "ranked": len(idx)}
    label = lambda f: f'{counties[pos[f]]["name"]}, {counties[pos[f]]["st"]}'
    body = f"""
<div class="controls"><label>County <input type="search" id="search" list="clist" size="28" aria-label="Find a county" placeholder="Type a county, ST"/></label>
<datalist id="clist"></datalist>
<button type="button" data-preset="{pos[oldest]}">Oldest-skewing: {esc(label(oldest))}</button>
<button type="button" data-preset="{pos[middle]}">Middle: {esc(label(middle))}</button>
<button type="button" data-preset="{pos[youngest]}">Youngest-skewing: {esc(label(youngest))}</button>
<button id="theme" type="button">Dark mode</button></div>
<div class="stats"><div class="stat"><div class="lab">Selected county</div><div class="val" id="cname"></div><div class="ctx">population <span id="cpop"></span></div></div>
<div class="stat"><div class="lab">Age-gap index</div><div class="val" id="cidx"></div><div class="ctx" id="crank"></div></div>
<div class="stat"><div class="lab">How to read</div><div class="ctx" style="font-size:12px;color:var(--ink2)">Gap &gt; 0: adults older than the
2000 U.S. standard population, so the crude rate exceeds the age-adjusted rate.</div></div></div>
<section style="display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:14px">
<div class="card"><h2>Distribution of the crude − age-adjusted gap across counties</h2>
<p class="note">One ridge per measure, sorted by median gap. Bar = 5th–95th percentile, tick = median, orange dot = selected county.</p>
<svg id="ridge" role="img" aria-label="Ridgeline of crude minus age-adjusted gaps" style="width:100%;height:auto"></svg></div>
<div class="card"><h2>Selected county: crude vs age-adjusted</h2>
<p class="note"><svg width="12" height="12" style="vertical-align:-2px"><circle cx="6" cy="6" r="4.5" fill="none" stroke="var(--accent)" stroke-width="2.5"/></svg> age-adjusted
&nbsp;<svg width="12" height="12" style="vertical-align:-2px"><circle cx="6" cy="6" r="5" fill="#eb6834"/></svg> crude &nbsp;· rows align with the ridges; number = gap in pp.</p>
<svg id="bell" role="img" aria-label="Dumbbell plot for the selected county" style="width:100%;height:auto"></svg></div></section>
<div class="card"><details><summary>Table view: gap by measure</summary><table id="tbl"><thead><tr><th>Measure</th><th>Year</th><th>Median gap (pp)</th><th>5th–95th</th><th>Crude higher</th></tr></thead><tbody></tbody></table></details>
<p class="note" style="margin-top:8px">The age-gap index is the mean z-score of the gap over eight age-graded measures (arthritis, high blood pressure, CHD, COPD,
high cholesterol, cancer, hearing and mobility disability); their gaps correlate at a median of 0.97, so the index tracks one county-level age
structure factor. Compare counties with age-adjusted rates; crude rates are closer to local caseload.</p></div>"""
    out = FINAL / "interactive_age_gap"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "Age-adjustment gap — PLACES county estimates", "Extended analysis · Age structure",
        "Older populations push crude rates up for chronic conditions and down for social and mental-health measures",
        "Crude prevalence reflects who lives in a county; age-adjusted prevalence removes that, for fair comparison. The gap between them is a window on each county's age profile.",
        body, payload, AGE_JS), encoding="utf-8")

    # static ridgeline
    rh, lw, rw, top = 22, 250, 640, 86
    width, height = lw + rw + 40, top + len(measures) * rh + 70
    X = lambda v: lw + (v - lo) / (hi - lo) * rw
    b = ['<text x="24" y="34" font-size="20" font-weight="700" fill="#0b0b0b">Older populations push crude rates up for chronic conditions</text>',
         '<text x="24" y="56" font-size="13" fill="#52514e">Distribution across counties of crude minus age-adjusted prevalence (pp). Bar = 5th–95th percentile; tick = median. Social and mental-health measures shift the other way.</text>']
    t = math.ceil(lo / 5) * 5
    while t <= hi:
        b.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 6}" y2="{height - 50}" stroke="{"#c3c2b7" if t == 0 else "#e1e0d9"}"/>')
        b.append(f'<text x="{X(t):.1f}" y="{height - 36}" font-size="11" text-anchor="middle" fill="#898781">{"+" if t > 0 else ""}{t}</text>')
        t += 5
    for i, m in enumerate(measures):
        base = top + i * rh + rh * .9
        pts = "L".join(f"{X(x):.1f},{base - d * rh * 1.5:.1f}" for x, d in m["kde"])
        b.append(f'<path d="M{X(m["kde"][0][0]):.1f},{base:.1f}L{pts}L{X(m["kde"][-1][0]):.1f},{base:.1f}Z" fill="#2a78d6" fill-opacity=".28" stroke="#2a78d6" stroke-width="1.3"/>')
        b.append(f'<line x1="{X(m["p05"]):.1f}" x2="{X(m["p95"]):.1f}" y1="{base:.1f}" y2="{base:.1f}" stroke="#52514e" stroke-width="2"/>')
        b.append(f'<line x1="{X(m["median"]):.1f}" x2="{X(m["median"]):.1f}" y1="{base - 5:.1f}" y2="{base + 3:.1f}" stroke="#0b0b0b" stroke-width="2"/>')
        b.append(f'<text x="{lw - 8}" y="{base - 2:.1f}" font-size="11" text-anchor="end" fill="#52514e">{esc(m["label"])}{" (2022)" if m["year"] == 2022 else ""}</text>')
    b.append(f'<text x="{lw + rw / 2}" y="{height - 18}" font-size="12" text-anchor="middle" fill="#52514e">Crude minus age-adjusted (percentage points) · Source: CDC PLACES 2025 (i46a-9kgh)</text>')
    (FINAL / "age_adjustment_ridgeline.svg").write_text(svg_doc(width, height, "Ridgeline of age-adjustment gaps", b), encoding="utf-8")
    return {"measures": len(measures), "counties": len(counties), "ranked_counties": len(idx),
            "oldest": label(oldest), "youngest": label(youngest)}


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

GALLERY = [
    ("interactive_county_map/index.html", "County health choropleth", "Diabetes, obesity and inactivity by county, with 95% intervals.", "Choropleth"),
    ("interactive_relationship/index.html", "Diabetes vs physical inactivity", "County scatterplot with LOWESS trend and region filter.", "Scatter + LOWESS"),
    ("interactive_overlap/index.html", "Upper-quartile overlap", "Counties in the top quartile of 0–3 core measures.", "Categorical map + bars"),
    ("interactive_measure_landscape/index.html", "Measure landscape", "How 35 measures co-vary: clustered heatmap, dendrogram, hexbin.", "New · Heatmap + dendrogram + hexbin"),
    ("interactive_state_tiles/index.html", "State profiles", "Any of 40 measures by state on a tile-grid map, linked to a ranking.", "New · Tile-grid cartogram"),
    ("interactive_age_gap/index.html", "Age-adjustment gap", "Crude vs age-adjusted rates: ridgeline and county dumbbells.", "New · Ridgeline + dumbbell"),
]


def build_gallery() -> None:
    cards = "".join(
        f'<a class="card g" href="{href}"><div class="kicker">{esc(tag)}</div><h2>{esc(t)}</h2><p class="note">{esc(d)}</p></a>'
        for href, t, d, tag in GALLERY)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>NTU data visualisation project — CDC PLACES 2025</title><style>{BASE_CSS}
.gal{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}a.g{{text-decoration:none;color:var(--ink)}}a.g:hover{{box-shadow:0 0 0 2px var(--accent)}}
</style></head><body><div class="viz-root"><main class="app"><header><div class="kicker">SD6105 · CDC PLACES county data, 2025 release</div>
<h1>Project visualisations</h1><div class="sub">Six interactive views of the cleaned and validated county table (3,143 counties, 40 age-adjusted measures).
The first three cover the core EDA measures; the last three come from the extended preliminary analysis.</div></header>
<section class="gal">{cards}</section>
<p class="foot">Source: CDC PLACES County Data (GIS Friendly Format), 2025 release (i46a-9kgh); U.S. Census Bureau 2023 cartographic boundaries.
County-level model-based estimates; descriptive, not causal.</p></main></div></body></html>
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
    checks = {
        "landscape": build_landscape(data, catalog),
        "state_tiles": build_state_tiles(data, catalog),
        "age_gap": build_age_gap(data, catalog),
    }
    build_gallery()
    ok = (checks["landscape"]["symmetric"] and checks["landscape"]["measures"] == 35
          and checks["state_tiles"]["tiles"] == checks["state_tiles"]["states_in_data"] == 51
          and checks["state_tiles"]["unpublished_2023_core"] == ["KY", "PA"]
          and len(checks["state_tiles"]["unpublished_hrsn"]) == 11
          and checks["age_gap"]["counties"] == 3143)
    outputs = sorted(str(p.relative_to(ROOT)) for p in [
        FINAL / "index.html", FINAL / "measure_landscape_heatmap.svg", FINAL / "state_tile_small_multiples.svg",
        FINAL / "age_adjustment_ridgeline.svg", FINAL / "interactive_measure_landscape/index.html",
        FINAL / "interactive_state_tiles/index.html", FINAL / "interactive_age_gap/index.html"])
    result = {"status": "PASS" if ok else "FAIL", "input_sha256": digest, "checks": checks, "outputs": outputs}
    VALIDATION_OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
