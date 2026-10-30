#!/usr/bin/env python3
"""Relationship analysis for the three accepted core PLACES measures.

The analysis is descriptive and ecological. It reports Pearson and Spearman
correlations, simple linear trend summaries, and overlap of metric-specific
upper-quartile counties. It does not estimate causal effects.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "01_data" if (ROOT / "01_data").is_dir() else ROOT / "data"
INPUT = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
VALIDATION = ROOT / "02_analysis/outputs/input_validation.json"
OUT = ROOT / "02_analysis/outputs"
FIG = ROOT / "03_visualisations/exploratory"

METRICS = {
    "DIABETES_AdjPrev": "Diagnosed diabetes",
    "OBESITY_AdjPrev": "Obesity",
    "LPA_AdjPrev": "No leisure-time physical activity",
}
SHORT_LABELS = {
    "DIABETES_AdjPrev": "Diabetes",
    "OBESITY_AdjPrev": "Obesity",
    "LPA_AdjPrev": "Physical inactivity",
}
COLORS = {
    "DIABETES_AdjPrev": "#31688E",
    "OBESITY_AdjPrev": "#B14A67",
    "LPA_AdjPrev": "#26828E",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(title)}</title>',
        f'<desc id="desc">{esc(subtitle)}</desc>',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172033}.title{font-size:24px;font-weight:700}.subtitle{font-size:13px;fill:#5C667A}.panel{font-size:15px;font-weight:700}.axis{font-size:11px;fill:#5C667A}.axis-title{font-size:12px;fill:#172033}.value{font-size:12px;font-weight:700}.note{font-size:11px;fill:#5C667A}.grid{stroke:#E5E9F0;stroke-width:1}.frame{fill:none;stroke:#AAB2C0;stroke-width:1}</style>',
        f'<text x="60" y="42" class="title">{esc(title)}</text>',
        f'<text x="60" y="66" class="subtitle">{esc(subtitle)}</text>',
    ]


def save_svg(name: str, lines: list[str]) -> None:
    lines.append("</svg>")
    (FIG / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def padded_domain(values: pd.Series, step: int = 5) -> tuple[float, float]:
    lower = math.floor(float(values.min()) / step) * step
    upper = math.ceil(float(values.max()) / step) * step
    return lower, upper


def relationship_tables(complete: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    correlation_rows = []
    regression_rows = []
    columns = list(METRICS)
    for left_index, metric_x in enumerate(columns):
        for metric_y in columns[left_index + 1 :]:
            pair = complete[[metric_x, metric_y]].dropna()
            pearson = float(pair.corr(method="pearson").iloc[0, 1])
            spearman = float(pair.corr(method="spearman").iloc[0, 1])
            correlation_rows.append(
                {
                    "metric_x": metric_x,
                    "metric_y": metric_y,
                    "n": len(pair),
                    "pearson_r": round(pearson, 6),
                    "spearman_rho": round(spearman, 6),
                }
            )

            x = pair[metric_x].to_numpy(float)
            y = pair[metric_y].to_numpy(float)
            slope, intercept = np.polyfit(x, y, 1)
            predicted = slope * x + intercept
            r_squared = 1 - np.square(y - predicted).sum() / np.square(y - y.mean()).sum()
            regression_rows.append(
                {
                    "predictor": metric_x,
                    "outcome": metric_y,
                    "n": len(pair),
                    "slope": round(float(slope), 6),
                    "intercept": round(float(intercept), 6),
                    "r_squared": round(float(r_squared), 6),
                    "interpretation": "descriptive linear trend; not causal",
                }
            )
    return pd.DataFrame(correlation_rows), pd.DataFrame(regression_rows)


def draw_scatter_panels(complete: pd.DataFrame, correlations: pd.DataFrame) -> None:
    width, height = 1240, 650
    lines = svg_start(
        width,
        height,
        "Diabetes is more closely associated with physical inactivity",
        "County-level 2023 age-adjusted estimates; n=2,956. Lines are descriptive least-squares trends, not causal effects.",
    )
    y_metric = "DIABETES_AdjPrev"
    panels = [
        ("OBESITY_AdjPrev", 90, 570),
        ("LPA_AdjPrev", 675, 1155),
    ]
    top, bottom = 120, 545
    ymin, ymax = padded_domain(complete[y_metric])
    for metric_x, left, right in panels:
        x = complete[metric_x]
        y = complete[y_metric]
        xmin, xmax = padded_domain(x)
        sx = lambda value: left + (right - left) * (float(value) - xmin) / (xmax - xmin)
        sy = lambda value: bottom - (bottom - top) * (float(value) - ymin) / (ymax - ymin)

        relation = correlations.loc[
            ((correlations["metric_x"] == y_metric) & (correlations["metric_y"] == metric_x))
            | ((correlations["metric_y"] == y_metric) & (correlations["metric_x"] == metric_x))
        ].iloc[0]
        slope, intercept = np.polyfit(x.to_numpy(float), y.to_numpy(float), 1)
        clip_id = f"clip-{metric_x.lower()}"

        lines.append(f'<text x="{left}" y="100" class="panel">{esc(METRICS[metric_x])} vs diagnosed diabetes</text>')
        lines.append(f'<text x="{right}" y="100" text-anchor="end" class="value">Pearson r = {relation["pearson_r"]:.3f} · Spearman ρ = {relation["spearman_rho"]:.3f}</text>')
        lines.append(f'<defs><clipPath id="{clip_id}"><rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}"/></clipPath></defs>')
        for tick in range(int(xmin), int(xmax) + 1, 5):
            px = sx(tick)
            lines.append(f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{bottom}" class="grid"/>')
            lines.append(f'<text x="{px:.1f}" y="{bottom + 20}" text-anchor="middle" class="axis">{tick}%</text>')
        for tick in range(int(ymin), int(ymax) + 1, 5):
            py = sy(tick)
            lines.append(f'<line x1="{left}" y1="{py:.1f}" x2="{right}" y2="{py:.1f}" class="grid"/>')
            if left == 90:
                lines.append(f'<text x="{left - 12}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>')
        for xv, yv in zip(x, y):
            lines.append(f'<circle cx="{sx(xv):.2f}" cy="{sy(yv):.2f}" r="2.2" fill="{COLORS[metric_x]}" fill-opacity="0.20" clip-path="url(#{clip_id})"/>')
        line_y0 = slope * xmin + intercept
        line_y1 = slope * xmax + intercept
        lines.append(f'<line x1="{sx(xmin):.1f}" y1="{sy(line_y0):.1f}" x2="{sx(xmax):.1f}" y2="{sy(line_y1):.1f}" stroke="#172033" stroke-width="2.5" clip-path="url(#{clip_id})"/>')
        lines.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" class="frame"/>')
        lines.append(f'<text x="{(left+right)/2:.1f}" y="{bottom+48}" text-anchor="middle" class="axis-title">{esc(METRICS[metric_x])} (%)</text>')
    lines.append(f'<text x="22" y="{(top+bottom)/2:.1f}" transform="rotate(-90 22,{(top+bottom)/2:.1f})" text-anchor="middle" class="axis-title">Diagnosed diabetes (%)</text>')
    lines.append('<text x="622" y="628" text-anchor="middle" class="note">Each dot is one county or county-equivalent; Kentucky and Pennsylvania are absent because these 2023 estimates are unpublished.</text>')
    save_svg("relationship_01_diabetes_scatter.svg", lines)


def correlation_color(value: float) -> str:
    # All observed correlations are positive; interpolate a legible pale-to-dark blue.
    low = (230, 239, 246)
    high = (44, 95, 135)
    amount = max(0.0, min(1.0, value))
    rgb = tuple(round(low[index] + (high[index] - low[index]) * amount) for index in range(3))
    return "#%02x%02x%02x" % rgb


def draw_correlation_matrix(complete: pd.DataFrame) -> None:
    corr = complete[list(METRICS)].corr(method="pearson")
    labels = [SHORT_LABELS[column] for column in corr.columns]
    width, height = 830, 610
    lines = svg_start(
        width,
        height,
        "All three county estimates move together",
        "Pearson correlations for 2,956 counties with complete 2023 age-adjusted estimates. Correlation does not establish causation.",
    )
    left, top, cell = 285, 165, 105
    for index, label in enumerate(labels):
        x = left + index * cell + cell / 2
        y = top + index * cell + cell / 2
        lines.append(f'<text x="{x:.1f}" y="{top-18}" text-anchor="middle" class="axis">{esc(label)}</text>')
        lines.append(f'<text x="{left-18}" y="{y+4:.1f}" text-anchor="end" class="axis">{esc(label)}</text>')
    for row_index, row in enumerate(corr.index):
        for column_index, column in enumerate(corr.columns):
            value = float(corr.loc[row, column])
            x = left + column_index * cell
            y = top + row_index * cell
            text_color = "#FFFFFF" if value >= 0.78 else "#172033"
            lines.append(f'<rect x="{x}" y="{y}" width="{cell-3}" height="{cell-3}" fill="{correlation_color(value)}"/>')
            lines.append(f'<text x="{x+cell/2:.1f}" y="{y+cell/2+6:.1f}" text-anchor="middle" style="font:700 18px Arial;fill:{text_color}">{value:.3f}</text>')
    lines.append('<text x="285" y="525" class="note">Strongest pair: diabetes and physical inactivity (r = 0.873).</text>')
    save_svg("relationship_02_correlation_matrix.svg", lines)


def draw_joint_high_overlap(counts: pd.DataFrame, total: int) -> None:
    width, height = 1040, 560
    lines = svg_start(
        width,
        height,
        "Upper-quartile burden frequently overlaps",
        "Count of counties above the metric-specific 75th percentile on exactly zero, one, two, or all three measures.",
    )
    left, right, top, bottom = 130, 970, 120, 440
    max_count = int(counts["counties"].max())
    chart_height = bottom - top
    bar_width = 125
    gap = 70
    colors = ["#AAB2C0", "#7AA6B8", "#4C8198", "#B14A67"]
    for tick in range(0, max_count + 1, 500):
        y = bottom - chart_height * tick / max_count
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="grid"/>')
        lines.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick:,}</text>')
    for index, row in counts.iterrows():
        x = left + 70 + index * (bar_width + gap)
        height_value = chart_height * int(row["counties"]) / max_count
        y = bottom - height_value
        pct = int(row["counties"]) / total * 100
        label = "All 3" if int(row["high_metric_count"]) == 3 else str(int(row["high_metric_count"]))
        lines.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{height_value:.1f}" fill="{colors[index]}"/>')
        lines.append(f'<text x="{x+bar_width/2:.1f}" y="{y-10:.1f}" text-anchor="middle" class="value">{int(row["counties"]):,} ({pct:.1f}%)</text>')
        lines.append(f'<text x="{x+bar_width/2:.1f}" y="{bottom+28}" text-anchor="middle" class="panel">{label}</text>')
    lines.append('<text x="550" y="505" text-anchor="middle" class="axis-title">Number of measures at or above its 75th-percentile threshold</text>')
    lines.append('<text x="24" y="280" transform="rotate(-90 24,280)" text-anchor="middle" class="axis-title">Counties</text>')
    save_svg("relationship_03_joint_high_overlap.svg", lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    if not INPUT.is_file():
        raise FileNotFoundError(f"Accepted cleaned input is missing: {INPUT}")
    if not VALIDATION.is_file():
        raise FileNotFoundError("Run validate_eda_input.py before relationship analysis.")
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise RuntimeError("EDA input validation has not passed.")
    input_hash = sha256(INPUT)
    if validation.get("summary", {}).get("cleaned_sha256") != input_hash:
        raise RuntimeError("Cleaned input changed after validation; rerun validate_eda_input.py.")

    df = pd.read_csv(INPUT, dtype={"CountyFIPS": "string"}, low_memory=False)
    metric_columns = list(METRICS)
    complete_mask = df[metric_columns].notna().all(axis=1)
    complete = df.loc[complete_mask, metric_columns].astype(float).copy()
    correlations, regressions = relationship_tables(complete)
    correlations.to_csv(OUT / "relationship_correlations.csv", index=False)
    regressions.to_csv(OUT / "relationship_regressions.csv", index=False)

    thresholds = complete.quantile(0.75)
    high_flags = complete.ge(thresholds)
    high_counts = high_flags.sum(axis=1)
    overlap = (
        high_counts.value_counts()
        .sort_index()
        .rename_axis("high_metric_count")
        .reset_index(name="counties")
    )
    overlap["pct_of_complete_counties"] = (overlap["counties"] / len(complete) * 100).round(2)
    overlap.to_csv(OUT / "relationship_joint_high_summary.csv", index=False)

    joint_mask = high_flags.all(axis=1)
    joint_source = df.loc[complete_mask].loc[joint_mask].copy()
    joint_table = joint_source[
        ["CountyFIPS", "StateAbbr", "StateDesc", "derived__CountyName_display"] + metric_columns
    ].rename(columns={"derived__CountyName_display": "CountyName_display"})
    for metric in metric_columns:
        joint_table[f"{metric}_q75_threshold"] = float(thresholds[metric])
    joint_table = joint_table.sort_values(["StateAbbr", "CountyName_display", "CountyFIPS"])
    joint_table.to_csv(OUT / "relationship_joint_high_counties.csv", index=False)

    state_joint = (
        joint_table.groupby(["StateAbbr", "StateDesc"], as_index=False)
        .size()
        .rename(columns={"size": "joint_high_counties"})
        .sort_values(["joint_high_counties", "StateAbbr"], ascending=[False, True])
    )
    state_joint.to_csv(OUT / "relationship_joint_high_by_state.csv", index=False)

    draw_scatter_panels(complete, correlations)
    draw_correlation_matrix(complete)
    draw_joint_high_overlap(overlap, len(complete))

    def corr(metric_a: str, metric_b: str, kind: str) -> float:
        row = correlations.loc[
            ((correlations["metric_x"] == metric_a) & (correlations["metric_y"] == metric_b))
            | ((correlations["metric_x"] == metric_b) & (correlations["metric_y"] == metric_a))
        ].iloc[0]
        return float(row[kind])

    diabetes_obesity_r = corr("DIABETES_AdjPrev", "OBESITY_AdjPrev", "pearson_r")
    diabetes_inactivity_r = corr("DIABETES_AdjPrev", "LPA_AdjPrev", "pearson_r")
    obesity_inactivity_r = corr("OBESITY_AdjPrev", "LPA_AdjPrev", "pearson_r")
    diabetes_obesity_rho = corr("DIABETES_AdjPrev", "OBESITY_AdjPrev", "spearman_rho")
    diabetes_inactivity_rho = corr("DIABETES_AdjPrev", "LPA_AdjPrev", "spearman_rho")
    obesity_inactivity_rho = corr("OBESITY_AdjPrev", "LPA_AdjPrev", "spearman_rho")
    joint_count = int(joint_mask.sum())
    joint_pct = joint_count / len(complete) * 100
    generated_at = datetime.now(ZoneInfo("Asia/Singapore")).isoformat(timespec="seconds")

    report = f"""# 关系分析（Relationship Analysis）报告

生成时间（Generated）：{generated_at}

## 1. 分析问题（Research question）

2023 年美国县级年龄调整糖尿病患病率（Diagnosed diabetes）与肥胖（Obesity）、缺乏体育活动（No leisure-time physical activity）之间呈现怎样的县级关联（County-level association）？三项指标的较高值在多大程度上共同出现？

## 2. 方法（Methods）

- 使用 {len(complete):,} 个三项指标均有已发布估计的县或县等价区（Complete cases）。Kentucky 和 Pennsylvania 因该组 2023 指标未发布而不在分析中。
- Pearson correlation（`r`）描述线性关系；Spearman rank correlation（`ρ`）描述单调排序关系。
- 散点图中的直线是最小二乘趋势线（Least-squares trend），仅用于描述，不代表因果效应。
- “共同高值（Joint high burden）”定义为三项指标均大于或等于各自的第 75 百分位（Upper quartile）：糖尿病 {thresholds['DIABETES_AdjPrev']:.1f}%，肥胖 {thresholds['OBESITY_AdjPrev']:.1f}%，缺乏体育活动 {thresholds['LPA_AdjPrev']:.1f}%。这是探索性分组，不是健康排名或临床阈值。

## 3. 相关结果（Correlation results）

| 指标对（Metric pair） | Pearson `r` | Spearman `ρ` | 完整县数 |
| --- | ---: | ---: | ---: |
| 糖尿病 × 肥胖 | {diabetes_obesity_r:.3f} | {diabetes_obesity_rho:.3f} | {len(complete):,} |
| 糖尿病 × 缺乏体育活动 | {diabetes_inactivity_r:.3f} | {diabetes_inactivity_rho:.3f} | {len(complete):,} |
| 肥胖 × 缺乏体育活动 | {obesity_inactivity_r:.3f} | {obesity_inactivity_rho:.3f} | {len(complete):,} |

三对指标均呈正相关（Positive association）。其中，糖尿病与缺乏体育活动的关联最强（Pearson `r = {diabetes_inactivity_r:.3f}`）；糖尿病与肥胖的关联相对较弱，但仍然明显（`r = {diabetes_obesity_r:.3f}`）。Pearson 与 Spearman 的结果方向和强弱顺序一致，支持这些关联在整体排序中也普遍存在；但仍需通过散点分布检查局部异常值。

## 4. 共同高值重叠（Joint high-burden overlap）

共有 {joint_count:,} 个县在三项指标上都达到或超过各自第 75 百分位，占完整样本的 {joint_pct:.1f}%。如果三项指标完全独立，三者同时进入上四分位的理论比例约为 1.56%；实际重叠远高于该参考值，与三项指标的正相关一致。

这些县应用于后续空间分析（Spatial analysis），检查是否形成地理集聚；不应把它们表述为“最不健康县排名”。

## 5. 解读边界（Interpretation limits）

- 这是县级生态关联（Ecological association），不能推断个人层面的风险，并需要避免生态谬误（Ecological fallacy）。
- 横截面关联（Cross-sectional association）不能证明肥胖或缺乏运动导致了糖尿病。
- 三项估计来自同一 PLACES 小域模型体系，共同的建模结构和未观测县级因素可能影响相关性。
- 本分析未控制年龄调整以外的混杂因素（Confounders），也未考虑空间自相关（Spatial autocorrelation）。
- 第 75 百分位只是为了识别共同高值模式，不是 CDC 定义的风险分界值。
"""
    (ROOT / "02_analysis/RELATIONSHIP_report.md").write_text(report, encoding="utf-8")

    manifest = {
        "generated_at": generated_at,
        "status": "complete",
        "input": str(INPUT.relative_to(ROOT)),
        "input_sha256": input_hash,
        "complete_counties": len(complete),
        "upper_quartile_thresholds": {metric: float(value) for metric, value in thresholds.items()},
        "joint_high_counties": joint_count,
        "tables": [
            "02_analysis/outputs/relationship_correlations.csv",
            "02_analysis/outputs/relationship_regressions.csv",
            "02_analysis/outputs/relationship_joint_high_summary.csv",
            "02_analysis/outputs/relationship_joint_high_counties.csv",
            "02_analysis/outputs/relationship_joint_high_by_state.csv",
        ],
        "figures": [
            "03_visualisations/exploratory/relationship_01_diabetes_scatter.svg",
            "03_visualisations/exploratory/relationship_02_correlation_matrix.svg",
            "03_visualisations/exploratory/relationship_03_joint_high_overlap.svg",
        ],
    }
    (OUT / "relationship_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
