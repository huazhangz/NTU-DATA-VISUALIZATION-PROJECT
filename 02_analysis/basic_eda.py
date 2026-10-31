#!/usr/bin/env python3
"""Basic, reproducible EDA for the accepted CDC PLACES input.

Scope: 2023 age-adjusted county estimates for diagnosed diabetes, obesity,
and no leisure-time physical activity. This stage covers coverage,
distributions, quantiles, state-level county medians, and review of extreme
values. It deliberately does not perform correlation, causal modelling,
clustering, or mapping.
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
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172033}.title{font-size:24px;font-weight:700}.subtitle{font-size:13px;fill:#5C667A}.panel{font-size:15px;font-weight:700}.axis{font-size:11px;fill:#5C667A}.value{font-size:12px;font-weight:700}.note{font-size:11px;fill:#5C667A}.grid{stroke:#E5E9F0;stroke-width:1}.frame{fill:none;stroke:#AAB2C0;stroke-width:1}</style>',
        f'<text x="60" y="42" class="title">{esc(title)}</text>',
        f'<text x="60" y="66" class="subtitle">{esc(subtitle)}</text>',
    ]


def save_svg(name: str, lines: list[str]) -> None:
    lines.append("</svg>")
    (FIG / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def metric_summary(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for metric, label in METRICS.items():
        values = pd.to_numeric(df[metric], errors="coerce")
        quantiles = values.quantile([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
        records.append(
            {
                "metric": metric,
                "label": label,
                "county_rows": len(df),
                "non_missing": int(values.notna().sum()),
                "missing": int(values.isna().sum()),
                "missing_pct": round(float(values.isna().mean() * 100), 2),
                "mean": round(float(values.mean()), 2),
                "std": round(float(values.std()), 2),
                "min": round(float(values.min()), 2),
                "p05": round(float(quantiles.loc[0.05]), 2),
                "p10": round(float(quantiles.loc[0.10]), 2),
                "p25": round(float(quantiles.loc[0.25]), 2),
                "median": round(float(quantiles.loc[0.50]), 2),
                "p75": round(float(quantiles.loc[0.75]), 2),
                "p90": round(float(quantiles.loc[0.90]), 2),
                "p95": round(float(quantiles.loc[0.95]), 2),
                "max": round(float(values.max()), 2),
                "iqr": round(float(quantiles.loc[0.75] - quantiles.loc[0.25]), 2),
            }
        )
    return pd.DataFrame(records)


def draw_distributions(df: pd.DataFrame, summary: pd.DataFrame) -> None:
    width, height = 1120, 780
    lines = svg_start(
        width,
        height,
        "County distributions of the three core estimates",
        "2023 age-adjusted model estimates. Each histogram includes 2,956 counties; Kentucky and Pennsylvania are missing.",
    )
    left, right = 115, 1040
    panel_height = 145
    tops = [115, 335, 555]
    for panel_index, (metric, label) in enumerate(METRICS.items()):
        values = pd.to_numeric(df[metric], errors="coerce").dropna().to_numpy(float)
        counts, edges = np.histogram(values, bins=24)
        top = tops[panel_index]
        bottom = top + panel_height
        xmin = math.floor(values.min() / 5) * 5
        xmax = math.ceil(values.max() / 5) * 5
        ymax = int(counts.max())
        sx = lambda value: left + (right - left) * (value - xmin) / (xmax - xmin)
        sy = lambda value: bottom - panel_height * value / ymax
        row = summary.loc[summary["metric"] == metric].iloc[0]
        lines.append(f'<text x="60" y="{top - 25}" class="panel">{esc(label)}</text>')
        lines.append(f'<text x="1040" y="{top - 25}" text-anchor="end" class="value">median {row["median"]:.1f}% · IQR {row["p25"]:.1f}–{row["p75"]:.1f}%</text>')
        for tick in range(int(xmin), int(xmax) + 1, 5):
            x = sx(tick)
            lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
            lines.append(f'<text x="{x:.1f}" y="{bottom + 20}" text-anchor="middle" class="axis">{tick}%</text>')
        for count, x0, x1 in zip(counts, edges[:-1], edges[1:]):
            px0, px1 = sx(x0), sx(x1)
            py = sy(count)
            lines.append(f'<rect x="{px0 + 1:.1f}" y="{py:.1f}" width="{max(1, px1 - px0 - 2):.1f}" height="{bottom - py:.1f}" fill="{COLORS[metric]}" fill-opacity="0.86"/>')
        median_x = sx(float(row["median"]))
        lines.append(f'<line x1="{median_x:.1f}" y1="{top}" x2="{median_x:.1f}" y2="{bottom}" stroke="#172033" stroke-width="2"/>')
        lines.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{panel_height}" class="frame"/>')
    lines.append('<text x="577" y="760" text-anchor="middle" class="axis">Age-adjusted county prevalence estimate (%)</text>')
    save_svg("basic_01_core_distributions.svg", lines)


def draw_quantiles(summary: pd.DataFrame) -> None:
    width, height = 1060, 410
    lines = svg_start(
        width,
        height,
        "Typical county ranges differ across the three measures",
        "Whisker = 5th–95th percentile; box = 25th–75th percentile; dot = median. Counties have equal visual weight.",
    )
    left, right, top, bottom = 315, 1000, 110, 310
    xmin, xmax = 0, 60
    for tick in range(xmin, xmax + 1, 10):
        x = left + (right - left) * (tick - xmin) / (xmax - xmin)
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
        lines.append(f'<text x="{x:.1f}" y="{bottom + 25}" text-anchor="middle" class="axis">{tick}%</text>')
    scale = lambda value: left + (right - left) * (float(value) - xmin) / (xmax - xmin)
    for index, row in summary.iterrows():
        y = 135 + index * 75
        color = COLORS[str(row["metric"])]
        lines.append(f'<text x="295" y="{y + 5}" text-anchor="end" class="panel">{esc(row["label"])}</text>')
        lines.append(f'<line x1="{scale(row["p05"]):.1f}" y1="{y}" x2="{scale(row["p95"]):.1f}" y2="{y}" stroke="#5C667A" stroke-width="2"/>')
        lines.append(f'<line x1="{scale(row["p05"]):.1f}" y1="{y-7}" x2="{scale(row["p05"]):.1f}" y2="{y+7}" stroke="#5C667A" stroke-width="2"/>')
        lines.append(f'<line x1="{scale(row["p95"]):.1f}" y1="{y-7}" x2="{scale(row["p95"]):.1f}" y2="{y+7}" stroke="#5C667A" stroke-width="2"/>')
        lines.append(f'<rect x="{scale(row["p25"]):.1f}" y="{y-13}" width="{scale(row["p75"])-scale(row["p25"]):.1f}" height="26" fill="{color}" fill-opacity="0.45"/>')
        lines.append(f'<circle cx="{scale(row["median"]):.1f}" cy="{y}" r="6" fill="{color}"/>')
        lines.append(f'<text x="{scale(row["p95"])+10:.1f}" y="{y+4}" class="value">median {row["median"]:.1f}%</text>')
    lines.append('<text x="657" y="375" text-anchor="middle" class="axis">Age-adjusted county prevalence estimate (%)</text>')
    save_svg("basic_02_core_quantile_ranges.svg", lines)


def draw_state_medians(state_medians: pd.DataFrame) -> None:
    width, height = 1120, 670
    lines = svg_start(
        width,
        height,
        "State distributions of county-level medians",
        "Each dot is a state's median across its counties—not a population-weighted state prevalence. KY and PA have no 2023 values.",
    )
    left, right = 115, 1040
    panel_height = 125
    tops = [120, 310, 500]
    for panel_index, (metric, label) in enumerate(METRICS.items()):
        values = state_medians[metric].dropna().sort_values()
        top = tops[panel_index]
        bottom = top + panel_height
        xmin = math.floor(values.min() / 5) * 5
        xmax = math.ceil(values.max() / 5) * 5
        sx = lambda value: left + (right - left) * (value - xmin) / (xmax - xmin)
        lines.append(f'<text x="60" y="{top - 22}" class="panel">{esc(label)}</text>')
        for tick in range(int(xmin), int(xmax) + 1, 5):
            x = sx(tick)
            lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" class="grid"/>')
            lines.append(f'<text x="{x:.1f}" y="{bottom + 19}" text-anchor="middle" class="axis">{tick}%</text>')
        for index, (state, value) in enumerate(values.items()):
            y = top + 18 + (index % 7) * 13
            lines.append(f'<circle cx="{sx(value):.1f}" cy="{y}" r="4.2" fill="{COLORS[metric]}" fill-opacity="0.72"><title>{esc(state)}: {value:.1f}%</title></circle>')
        median_of_state_medians = float(values.median())
        lines.append(f'<line x1="{sx(median_of_state_medians):.1f}" y1="{top}" x2="{sx(median_of_state_medians):.1f}" y2="{bottom}" stroke="#172033" stroke-width="2"/>')
        lines.append(f'<text x="{sx(median_of_state_medians)+7:.1f}" y="{top+13}" class="value">median state: {median_of_state_medians:.1f}%</text>')
        lines.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{panel_height}" class="frame"/>')
    save_svg("basic_03_state_county_medians.svg", lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    if not INPUT.is_file():
        raise FileNotFoundError(f"Accepted cleaned input is missing: {INPUT}")
    if not VALIDATION.is_file():
        raise FileNotFoundError("Run validate_eda_input.py before basic EDA.")
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise RuntimeError("EDA input validation has not passed.")
    if validation.get("summary", {}).get("cleaned_sha256") != sha256(INPUT):
        raise RuntimeError("Cleaned input changed after validation; rerun validate_eda_input.py.")

    df = pd.read_csv(INPUT, dtype={"CountyFIPS": "string"}, low_memory=False)
    summary = metric_summary(df)
    summary.to_csv(OUT / "basic_metric_summary.csv", index=False)

    state_medians = (
        df.groupby(["StateAbbr", "StateDesc"], dropna=False)[list(METRICS)]
        .median()
        .round(2)
        .reset_index()
        # Stable sort with a tie-breaker so reruns produce identical files.
        .sort_values(["DIABETES_AdjPrev", "StateAbbr"], na_position="last", kind="mergesort")
    )
    state_medians.to_csv(OUT / "basic_state_county_medians.csv", index=False)

    extreme_rows = []
    for metric, label in METRICS.items():
        available = df[["CountyFIPS", "StateAbbr", "StateDesc", "derived__CountyName_display", metric]].dropna(subset=[metric]).copy()
        for side, selected in [("lower_tail_review", available.nsmallest(10, metric)), ("upper_tail_review", available.nlargest(10, metric))]:
            for _, row in selected.iterrows():
                extreme_rows.append(
                    {
                        "metric": metric,
                        "label": label,
                        "review_group": side,
                        "CountyFIPS": row["CountyFIPS"],
                        "StateAbbr": row["StateAbbr"],
                        "StateDesc": row["StateDesc"],
                        "CountyName_display": row["derived__CountyName_display"],
                        "estimate_pct": row[metric],
                    }
                )
    pd.DataFrame(extreme_rows).to_csv(OUT / "basic_extreme_value_review.csv", index=False)

    draw_distributions(df, summary)
    draw_quantiles(summary)
    draw_state_medians(state_medians.set_index("StateAbbr"))

    generated_at = datetime.now(ZoneInfo("Asia/Singapore")).isoformat(timespec="seconds")
    manifest = {
        "generated_at": generated_at,
        "status": "complete",
        "scope": list(METRICS),
        "input": str(INPUT.relative_to(ROOT)),
        "input_sha256": sha256(INPUT),
        "county_rows": len(df),
        "analysis_rows_per_metric": {row.metric: int(row.non_missing) for row in summary.itertuples()},
        "tables": [
            "02_analysis/outputs/basic_metric_summary.csv",
            "02_analysis/outputs/basic_state_county_medians.csv",
            "02_analysis/outputs/basic_extreme_value_review.csv",
        ],
        "figures": [
            "03_visualisations/exploratory/basic_01_core_distributions.svg",
            "03_visualisations/exploratory/basic_02_core_quantile_ranges.svg",
            "03_visualisations/exploratory/basic_03_state_county_medians.svg",
        ],
    }
    (OUT / "basic_eda_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = {row.metric: row for row in summary.itertuples()}
    missing_abbr = sorted(df.loc[df[list(METRICS)].isna().any(axis=1), "StateAbbr"].unique())
    missing_states = "、".join(
        f"{df.loc[df['StateAbbr'] == abbr, 'StateDesc'].iloc[0]}（{abbr}）" for abbr in missing_abbr
    )
    report = f"""# 基础探索性数据分析（Basic EDA）报告

生成时间（Generated）：{generated_at}

## 1. 分析范围（Scope）

本轮正式探索性数据分析（Exploratory Data Analysis, EDA）使用已通过验收的清洗数据表，聚焦三个 2023 年县级年龄调整患病率估计（Age-adjusted prevalence estimates）：诊断糖尿病（Diagnosed diabetes）、肥胖（Obesity）和无休闲时间体育活动（No leisure-time physical activity）。

本阶段包括数据覆盖情况（Coverage）、单变量分布（Univariate distributions）、分位数（Quantiles）、州内县级中位数（State-level county medians）和尾部数值诊断。本报告尚未检验指标之间的关联（Association），也不作因果推断（Causal inference）。

## 2. 数据覆盖情况（Coverage）

每个指标均有 {rows['DIABETES_AdjPrev'].non_missing:,} 个已发布的县级估计，并有 {rows['DIABETES_AdjPrev'].missing} 行缺失，缺失率为 {rows['DIABETES_AdjPrev'].missing_pct:.2f}%。所有缺失行均来自 {missing_states}。这些空白值代表未发布（Unpublished），本分析保留其缺失状态，未将其替换为 0，也未进行插补（Imputation）。

## 3. 分布摘要（Distribution summary）

| 指标（Measure） | 均值（Mean） | 中位数（Median） | 四分位距（IQR） | 第 10–90 百分位 | 最小–最大值 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 诊断糖尿病（Diagnosed diabetes） | {rows['DIABETES_AdjPrev'].mean:.2f}% | {rows['DIABETES_AdjPrev'].median:.2f}% | {rows['DIABETES_AdjPrev'].p25:.2f}–{rows['DIABETES_AdjPrev'].p75:.2f}% | {rows['DIABETES_AdjPrev'].p10:.2f}–{rows['DIABETES_AdjPrev'].p90:.2f}% | {rows['DIABETES_AdjPrev'].min:.2f}–{rows['DIABETES_AdjPrev'].max:.2f}% |
| 肥胖（Obesity） | {rows['OBESITY_AdjPrev'].mean:.2f}% | {rows['OBESITY_AdjPrev'].median:.2f}% | {rows['OBESITY_AdjPrev'].p25:.2f}–{rows['OBESITY_AdjPrev'].p75:.2f}% | {rows['OBESITY_AdjPrev'].p10:.2f}–{rows['OBESITY_AdjPrev'].p90:.2f}% | {rows['OBESITY_AdjPrev'].min:.2f}–{rows['OBESITY_AdjPrev'].max:.2f}% |
| 无休闲时间体育活动（No leisure-time physical activity） | {rows['LPA_AdjPrev'].mean:.2f}% | {rows['LPA_AdjPrev'].median:.2f}% | {rows['LPA_AdjPrev'].p25:.2f}–{rows['LPA_AdjPrev'].p75:.2f}% | {rows['LPA_AdjPrev'].p10:.2f}–{rows['LPA_AdjPrev'].p90:.2f}% | {rows['LPA_AdjPrev'].min:.2f}–{rows['LPA_AdjPrev'].max:.2f}% |

## 4. 初步发现（Initial observations）

1. 在三个指标中，肥胖（Obesity）的典型县级估计最高：其中位数（Median）为 {rows['OBESITY_AdjPrev'].median:.1f}%；无休闲时间体育活动为 {rows['LPA_AdjPrev'].median:.1f}%；诊断糖尿病为 {rows['DIABETES_AdjPrev'].median:.1f}%。三者衡量的是不同现象，因此不应把数值大小解读为统一的“严重程度”尺度。
2. 三个指标均呈现明显的县际差异（County-level variation）。中间 80% 的县分别落在：糖尿病 {rows['DIABETES_AdjPrev'].p10:.1f}%–{rows['DIABETES_AdjPrev'].p90:.1f}%，肥胖 {rows['OBESITY_AdjPrev'].p10:.1f}%–{rows['OBESITY_AdjPrev'].p90:.1f}%，缺乏体育活动 {rows['LPA_AdjPrev'].p10:.1f}%–{rows['LPA_AdjPrev'].p90:.1f}%。
3. 三个指标的均值（Mean）与中位数（Median）较为接近，但完整值域明显宽于中央分布。尾部县（Tail counties）已保留用于诊断检查，未被自动删除或当作异常数据。
4. 不同州的县级中位数存在差异，说明后续空间分析（Spatial analysis）具有必要性。但这些数值是各州内县级估计的等权中位数，不是人口加权的州级患病率（Population-weighted state prevalence）。

## 5. 解读边界（Interpretation limits）

- 本数据为模型生成的县级估计（Model-based county estimates），不是对每个县的直接调查测量。
- 空白值表示未发布（Unpublished），不表示 0。
- 本阶段的全国汇总对每个县等权处理（Equal county weight），未按人口加权。
- 尾部数值表用于诊断检查（Diagnostic review），不是县级健康排名（Health ranking）。
- 指标关联（Association）和空间分析将在后续阶段分开完成；本报告不作因果推断（Causal claim）。
"""
    (ROOT / "02_analysis/EDA_report.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
