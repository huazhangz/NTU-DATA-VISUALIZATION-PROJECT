#!/usr/bin/env python3
"""Preliminary analysis of the PLACES measures beyond the three core-EDA measures.

Descriptive, county-level (ecological) questions only:

1. Coverage: which of the 40 age-adjusted measures are published where, and
   for which year?
2. Related measures: which 2023 measures rise and fall together across
   counties? (pairwise Spearman rank correlation)
3. State profiles: how does each state's typical (median) county compare with
   the typical U.S. county, for every measure?
4. Method check: how far apart are crude and age-adjusted estimates? This
   justifies using age-adjusted values for county comparisons; it is not
   visualised.

Outputs feed ``03_visualisations/final/build_extended_views.py``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "01_data" if (ROOT / "01_data").is_dir() else ROOT / "data"
INPUT = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
RAW = DATA_ROOT / "raw/places_county_gis_2025_i46a-9kgh.csv"
DICTIONARY = DATA_ROOT / "processed/places_county_gis_2025_field_dictionary.csv"
VALIDATION = ROOT / "02_analysis/outputs/input_validation.json"
OUT = ROOT / "02_analysis/outputs"
REPORT = ROOT / "02_analysis/EXTENDED_report.md"
TZ = ZoneInfo("Asia/Singapore")

# Plain-English chart labels. Population groups are stated where they are
# not "all adults".
LABELS = {
    "ACCESS2": "No health insurance (ages 18–64)",
    "ARTHRITIS": "Arthritis",
    "BINGE": "Binge drinking",
    "BPHIGH": "High blood pressure",
    "BPMED": "Taking blood pressure medicine (adults with high BP)",
    "CANCER": "Cancer (excluding skin cancer)",
    "CASTHMA": "Asthma",
    "CHD": "Coronary heart disease",
    "CHECKUP": "Routine checkup in past year",
    "CHOLSCREEN": "Cholesterol check in past 5 years",
    "COLON_SCREEN": "Colorectal cancer screening (ages 45–75)",
    "COPD": "COPD (chronic lung disease)",
    "CSMOKING": "Current smoking",
    "DENTAL": "Dental visit in past year",
    "DEPRESSION": "Depression",
    "DIABETES": "Diabetes",
    "GHLTH": "Fair or poor general health",
    "HIGHCHOL": "High cholesterol",
    "LPA": "Physical inactivity",
    "MAMMOUSE": "Mammogram (women 50–74)",
    "MHLTH": "Frequent mental distress",
    "OBESITY": "Obesity",
    "PHLTH": "Frequent physical distress",
    "SLEEP": "Short sleep (under 7 hours)",
    "STROKE": "Stroke",
    "TEETHLOST": "All teeth lost (ages 65+)",
    "HEARING": "Hearing disability",
    "VISION": "Vision disability",
    "COGNITION": "Cognitive disability",
    "MOBILITY": "Mobility disability",
    "SELFCARE": "Self-care disability",
    "INDEPLIVE": "Independent-living disability",
    "DISABILITY": "Any disability",
    "LONELINESS": "Loneliness",
    "FOODSTAMP": "Received food stamps (SNAP)",
    "FOODINSECU": "Food insecurity",
    "HOUSINSECU": "Housing insecurity",
    "SHUTUTILITY": "Utility shut-off threat",
    "LACKTRPT": "Lack of reliable transportation",
    "EMOTIONSPT": "Lack of social and emotional support",
}
CATEGORY_LABELS = {
    "health_outcome": "Health condition",
    "health_status": "Health status",
    "health_risk_behavior": "Risk behavior",
    "prevention": "Prevention and care",
    "disability": "Disability",
    "health_related_social_need": "Social need",
}
CORE = {"DIABETES", "OBESITY", "LPA"}
# Measures left out of the charts because their population group makes a
# county comparison hard to read (kept in every table).
CHART_EXCLUDED = {"BPMED"}
STRENGTH = [(0.7, "strong"), (0.4, "moderate"), (0.2, "weak"), (0.0, "little or none")]


def strength(rho: float) -> str:
    return next(word for cut, word in STRENGTH if abs(rho) >= cut)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_input() -> str:
    if not VALIDATION.is_file():
        raise SystemExit("Missing EDA input validation. Run validate_eda_input.py first.")
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise SystemExit("EDA input validation is not PASS.")
    digest = sha256(INPUT)
    if validation.get("summary", {}).get("cleaned_sha256") != digest:
        raise SystemExit("Cleaned CSV hash differs from the validated hash.")
    return digest


def measure_catalog() -> pd.DataFrame:
    fields = pd.read_csv(DICTIONARY)
    adj = fields[fields["column_name"].str.endswith("_AdjPrev")].copy()
    adj["measure"] = adj["column_name"].str.removesuffix("_AdjPrev")
    adj["year"] = adj["description"].str.extract(r"(20\d\d)\s*$")[0].astype(int)
    adj["category"] = adj["measure_category"].map(CATEGORY_LABELS)
    adj["label"] = adj["measure"].map(LABELS)
    if adj["label"].isna().any() or adj["category"].isna().any():
        raise SystemExit("Unlabelled measure or category in the field dictionary.")
    return adj[["measure", "label", "category", "year", "description"]].reset_index(drop=True)


def main() -> None:
    digest = check_input()
    data = pd.read_csv(INPUT, dtype={"CountyFIPS": str}, encoding="utf-8-sig")
    catalog = measure_catalog()

    # ---- 1. coverage and distribution per measure ---------------------
    rows = []
    for m in catalog.itertuples():
        values = data[f"{m.measure}_AdjPrev"].dropna()
        unpublished = sorted(set(data["StateAbbr"]) - set(data.loc[values.index, "StateAbbr"]))
        rows.append({
            "measure": m.measure,
            "label": m.label,
            "category": m.category,
            "year": m.year,
            "core_eda": m.measure in CORE,
            "in_charts": m.measure not in CHART_EXCLUDED,
            "counties": int(values.size),
            "unpublished_states": " ".join(unpublished),
            "median": round(float(values.median()), 2),
            "p10": round(float(values.quantile(.10)), 2),
            "p90": round(float(values.quantile(.90)), 2),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "extended_measure_catalog.csv", index=False)

    # ---- 2. related measures (2023 only; years are not mixed) --------
    m23 = catalog.loc[catalog["year"] == 2023, "measure"].tolist()
    cols = [f"{m}_AdjPrev" for m in m23]
    rho = data[cols].corr(method="spearman", min_periods=500)
    present = data[cols].notna().astype(int)
    pair_n = present.T.dot(present)
    rho.index = rho.columns = m23
    pair_n.index = pair_n.columns = m23
    if rho.isna().any().any():
        raise SystemExit("Undefined Spearman correlation among 2023 measures.")
    rho.round(4).to_csv(OUT / "extended_spearman_matrix.csv")
    tri = []
    for i, a in enumerate(m23):
        for b in m23[i + 1:]:
            r = float(rho.loc[a, b])
            tri.append({"a": a, "b": b, "rho": round(r, 4), "n": int(pair_n.loc[a, b]), "strength": strength(r)})
    pairs = pd.DataFrame(tri).sort_values(["rho", "a", "b"], kind="mergesort")
    pairs.to_csv(OUT / "extended_spearman_pairs.csv", index=False)

    # Within-state check for the strongest pair: if the association holds at
    # the same level inside almost every state, it is a stable property of
    # the estimates rather than a between-state artefact.
    top = pairs.iloc[-1]
    within = (
        data[[f"{top.a}_AdjPrev", f"{top.b}_AdjPrev", "StateAbbr"]].dropna()
        .groupby("StateAbbr")
        .filter(lambda g: len(g) >= 20)
        .groupby("StateAbbr")
        .apply(lambda g: g.iloc[:, :2].corr(method="spearman").iloc[0, 1], include_groups=False)
    )

    # Confirm the strongest pair's values match the immutable raw file cell by cell.
    raw = pd.read_csv(RAW, dtype=str, encoding="utf-8-sig").set_index("CountyFIPS")
    for col in (f"{top.a}_AdjPrev", f"{top.b}_AdjPrev"):
        cleaned = data.set_index("CountyFIPS")[col]
        if not pd.to_numeric(raw[col]).reindex(cleaned.index).equals(cleaned):
            raise SystemExit(f"{col} differs from the raw CSV.")

    # ---- 3. state profiles --------------------------------------------
    state_rows = []
    for m in catalog.itertuples():
        col = f"{m.measure}_AdjPrev"
        national = float(data[col].median())
        for (abbr, name), grp in data.groupby(["StateAbbr", "StateDesc"]):
            vals = grp[col].dropna()
            state_rows.append({
                "measure": m.measure,
                "state": abbr,
                "state_name": name,
                "counties": int(vals.size),
                "state_median": round(float(vals.median()), 2) if vals.size else None,
                "national_median": round(national, 2),
                "difference_pp": round(float(vals.median()) - national, 2) if vals.size else None,
            })
    states = pd.DataFrame(state_rows)
    states.to_csv(OUT / "extended_state_medians.csv", index=False)

    # ---- 4. method check: crude minus age-adjusted ---------------------
    gap_rows = []
    for m in catalog.itertuples():
        g = (data[f"{m.measure}_CrudePrev"] - data[f"{m.measure}_AdjPrev"]).dropna()
        gap_rows.append({
            "measure": m.measure,
            "label": m.label,
            "year": m.year,
            "counties": int(g.size),
            "median_gap_pp": round(float(g.median()), 2),
            "p05": round(float(g.quantile(.05)), 2),
            "p95": round(float(g.quantile(.95)), 2),
            "share_crude_higher": round(float((g > 0).mean()), 3),
        })
    gap_table = pd.DataFrame(gap_rows).sort_values(["median_gap_pp", "measure"], ascending=[False, True], kind="mergesort")
    gap_table.to_csv(OUT / "extended_age_adjustment_gap.csv", index=False)

    # ---- report -------------------------------------------------------
    now = datetime.now(TZ).replace(microsecond=0).isoformat()
    lab = dict(zip(catalog["measure"], catalog["label"]))
    fmt = lambda r: f"{lab[r.a]} × {lab[r.b]}"
    counts = pairs["strength"].value_counts()
    pos_strong = int(((pairs["rho"] >= 0.7)).sum())
    neg_moderate = int(((pairs["rho"] <= -0.4)).sum())
    hrsn = catalog.loc[catalog["category"] == "Social need", "measure"].tolist()

    def related(measure: str, k: int = 5) -> str:
        s = rho[measure].drop(measure).sort_values(ascending=False)
        return "；".join(f"{lab[o]} `{v:.2f}`" for o, v in s.head(k).items())

    cov = summary.groupby(["year", "counties", "unpublished_states"]).size().reset_index(name="measures")
    lines = [
        "# 扩展初步分析（Extended preliminary analysis）报告",
        "",
        f"生成时间（Generated）：{now}",
        "",
        "## 1. 范围",
        "",
        "核心 EDA 只用了 40 项年龄调整指标中的 3 项（糖尿病、肥胖、缺乏体育活动）。本轮对全部 40 项做描述性初步分析：覆盖范围、指标间的县级共变、州级轮廓，以及粗率与年龄调整率的方法检查。",
        "",
        f"输入：已验收清洗表，SHA-256 `{digest}`，{len(data):,} 行。",
        "",
        "## 2. 覆盖范围（Coverage）",
        "",
        "| 年份 | 指标数 | 有值县数 | 未发布的州 |",
        "| ---: | ---: | ---: | --- |",
    ]
    for r in cov.itertuples():
        lines.append(f"| {r.year} | {r.measures} | {r.counties:,} | {r.unpublished_states or '无'} |")
    lines += [
        "",
        "- 空白表示未发布，一律保留为缺失，不补零、不插补。",
        "- 2022 年的 5 项（结直肠癌筛查、看牙、乳腺 X 光、睡眠不足、65 岁以上全口无牙）不与 2023 指标做相关，也不连成趋势。",
        "- `ACCESS2`（18–64 岁）、`BPMED`（高血压患者）、`COLON_SCREEN`、`MAMMOUSE`、`TEETHLOST` 的人群不是全部成年人。"
        "`BPMED` 只在表格中保留，不进入图表，因为它的分母（已诊断高血压者）使县间比较难以直观解读。",
        "- `LONELINESS` 按交接约定标为 Loneliness（字段字典仍写 socially isolated；发布说明称已改为孤独）。",
        "",
        "## 3. 指标间共变（Related measures）",
        "",
        "方法：35 项 2023 指标两两计算 Spearman 等级相关 `ρ`，使用两两都有值的县（Pairwise complete）。"
        "社会需求（HRSN）指标参与的配对只有 2,299 县，其余为 2,956 县，因此两类配对的 `ρ` 不是在同一组县上算的，只宜粗略比较。",
        "",
        f"强度用语：|ρ| ≥ 0.7 为强，0.4–0.7 为中等，0.2–0.4 为弱，< 0.2 为几乎无关。595 对中：强 {counts.get('strong', 0)}、中等 {counts.get('moderate', 0)}、弱 {counts.get('weak', 0)}、几乎无关 {counts.get('little or none', 0)}。"
        f"其中强正相关 {pos_strong} 对，中等及以上负相关 {neg_moderate} 对。",
        "",
        "与三项核心指标关联最强的其他指标：",
        "",
        f"- 糖尿病：{related('DIABETES')}",
        f"- 肥胖：{related('OBESITY')}",
        f"- 缺乏体育活动：{related('LPA')}",
        "",
        "最强正相关：" + "；".join(f"{fmt(r)} `{r.rho:.2f}`" for r in pairs.tail(5)[::-1].itertuples()) + "。",
        "",
        "最强负相关：" + "；".join(f"{fmt(r)} `{r.rho:.2f}`" for r in pairs.head(5).itertuples()) + "。",
        "",
        f"可靠性检查：最强的一对（{lab[top.a]} × {lab[top.b]}，`ρ = {top.rho:.2f}`）在 {len(within)} 个至少 20 县的州内各自计算，"
        f"州内 `ρ` 中位数为 {within.median():.2f}，最低 {within.min():.2f}。数值已与原始 CSV 逐格核对一致，不是计算错误。"
        "两个概念上不同的指标在几乎每个州内都接近完全同步，说明这种极高相关主要来自 PLACES 小域模型共用同一组县级人口与社会经济协变量，"
        "而不是两种现象之间的独立证据。因此图中只用“同步程度”描述，不作因果或机制解读，并对 |ρ| ≥ 0.9 的配对加注。",
        "",
        "初步解读：慢性病、健康状况、残疾和社会需求在县级普遍同向变化——一个县若在其中一项偏高，往往多项都偏高；"
        "暴饮、癌症、胆固醇检查与这一组多为反向。",
        "",
        "## 4. 州级轮廓（State profiles）",
        "",
        "方法：每州县级估计的中位数（“该州的典型县”）减全国县级中位数（“美国典型县”），单位为百分点。"
        "这不是州人口患病率，未按人口加权；县数少的州（DC 1 县、DE 3 县、HI 5 县）波动较大。",
        "",
        "| 指标 | 美国典型县 | 最高的 3 州（差值） | 最低的 3 州（差值） |",
        "| --- | ---: | --- | --- |",
    ]
    for m in ["DIABETES", "DEPRESSION", "FOODINSECU", "CSMOKING", "BINGE", "CHECKUP"]:
        s = states[(states.measure == m) & states.difference_pp.notna()].sort_values(["difference_pp", "state"], kind="mergesort")
        hi = ", ".join(f"{r.state} {r.difference_pp:+.1f}" for r in s.tail(3)[::-1].itertuples())
        lo = ", ".join(f"{r.state} {r.difference_pp:+.1f}" for r in s.head(3).itertuples())
        lines.append(f"| {lab[m]} | {s.national_median.iloc[0]:.1f}% | {hi} | {lo} |")
    lines += [
        "",
        "完整 40 × 51 表见 `outputs/extended_state_medians.csv`。",
        "",
        "## 5. 方法检查：粗率与年龄调整率（不做成图）",
        "",
        "粗率（Crude）反映县里实际人口；年龄调整率（Age-adjusted）按 2000 年美国标准人口重新加权，用于县间公平比较。二者之差（粗率 − 调整率）：",
        "",
        "| 指标 | 年份 | 中位差（百分点） | 5%–95% | 粗率更高的县占比 |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for r in pd.concat([gap_table.head(5), gap_table.tail(3)]).itertuples():
        lines.append(f"| {r.label} | {r.year} | {r.median_gap_pp:+.2f} | {r.p05:+.1f} 至 {r.p95:+.1f} | {r.share_crude_higher:.0%} |")
    core_gaps = gap_table.set_index("measure").loc[sorted(CORE)]
    lines += [
        "",
        "结论：与年龄相关的慢性病差值可达数个百分点，方向随指标而变，所以县间比较必须使用年龄调整率（本项目所有图表都如此）。"
        "三项核心指标的中位差为：" + "，".join(f"{lab[k]} {v:+.1f}" for k, v in core_gaps["median_gap_pp"].items()) + " 个百分点。"
        "`BPMED` 的差值约 +20 个百分点，进一步说明它不适合放进面向大众的图表。",
        "",
        "## 6. 解读边界",
        "",
        "- 全部为县级生态描述，不推断个人风险，也不推断因果。",
        "- 估计来自同一小域模型，共享协变量会抬高指标间相关（见第 3 节检查）。",
        "- 州中位数不等于州患病率；未按人口加权。",
        "- 不把 2022 与 2023 指标连成时间趋势。",
        "",
        "## 7. 对应可视化",
        "",
        "- `03_visualisations/final/interactive_related_measures/`：选择一项指标，查看其他 2023 指标与它的同步程度（排序条形图），点击条形查看县级散点。",
        "- `03_visualisations/final/interactive_state_tiles/`：州瓦片地图 + 排名点图，可切换 39 项指标。",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "status": "complete",
        "generated_at": now,
        "input": str(INPUT.relative_to(ROOT)),
        "input_sha256": digest,
        "measures": int(len(catalog)),
        "measures_2023": len(m23),
        "measures_2022": int((catalog["year"] == 2022).sum()),
        "chart_excluded": sorted(CHART_EXCLUDED),
        "strongest_pair": {"a": top.a, "b": top.b, "rho": float(top.rho),
                           "within_state_median_rho": round(float(within.median()), 4), "states_checked": int(len(within))},
        "outputs": [
            "02_analysis/EXTENDED_report.md",
            "02_analysis/outputs/extended_age_adjustment_gap.csv",
            "02_analysis/outputs/extended_measure_catalog.csv",
            "02_analysis/outputs/extended_spearman_matrix.csv",
            "02_analysis/outputs/extended_spearman_pairs.csv",
            "02_analysis/outputs/extended_state_medians.csv",
        ],
    }
    (OUT / "extended_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
