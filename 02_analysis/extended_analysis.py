#!/usr/bin/env python3
"""Preliminary analysis of the PLACES measures not covered by the core EDA.

Three descriptive questions, all county-level and ecological:

1. Measure landscape: how do the 35 measures estimated for 2023 co-vary
   across counties? (pairwise Spearman correlation + average-linkage
   hierarchical clustering on 1 - rho)
2. State profiles: how do state medians of county estimates differ from the
   national county median, for all 40 age-adjusted measures?
3. Age-adjustment gap: how far apart are crude and age-adjusted estimates,
   and which measures and counties does the population age structure move
   the most?

Outputs feed ``03_visualisations/final/build_extended_views.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "01_data" if (ROOT / "01_data").is_dir() else ROOT / "data"
INPUT = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
DICTIONARY = DATA_ROOT / "processed/places_county_gis_2025_field_dictionary.csv"
VALIDATION = ROOT / "02_analysis/outputs/input_validation.json"
OUT = ROOT / "02_analysis/outputs"
REPORT = ROOT / "02_analysis/EXTENDED_report.md"
TZ = ZoneInfo("Asia/Singapore")

# Short English labels used on every chart.
LABELS = {
    "ACCESS2": "No health insurance (18–64)",
    "ARTHRITIS": "Arthritis",
    "BINGE": "Binge drinking",
    "BPHIGH": "High blood pressure",
    "BPMED": "BP medication (among high BP)",
    "CANCER": "Cancer (non-skin)",
    "CASTHMA": "Current asthma",
    "CHD": "Coronary heart disease",
    "CHECKUP": "Routine checkup",
    "CHOLSCREEN": "Cholesterol screening",
    "COLON_SCREEN": "Colorectal screening (45–75)",
    "COPD": "COPD",
    "CSMOKING": "Current smoking",
    "DENTAL": "Dental visit",
    "DEPRESSION": "Depression",
    "DIABETES": "Diagnosed diabetes",
    "GHLTH": "Fair or poor health",
    "HIGHCHOL": "High cholesterol",
    "LPA": "Physical inactivity",
    "MAMMOUSE": "Mammography (women 50–74)",
    "MHLTH": "Frequent mental distress",
    "OBESITY": "Obesity",
    "PHLTH": "Frequent physical distress",
    "SLEEP": "Short sleep",
    "STROKE": "Stroke",
    "TEETHLOST": "All teeth lost (65+)",
    "HEARING": "Hearing disability",
    "VISION": "Vision disability",
    "COGNITION": "Cognitive disability",
    "MOBILITY": "Mobility disability",
    "SELFCARE": "Self-care disability",
    "INDEPLIVE": "Independent-living disability",
    "DISABILITY": "Any disability",
    "LONELINESS": "Loneliness",
    "FOODSTAMP": "Received food stamps",
    "FOODINSECU": "Food insecurity",
    "HOUSINSECU": "Housing insecurity",
    "SHUTUTILITY": "Utility shut-off threat",
    "LACKTRPT": "Lack of transportation",
    "EMOTIONSPT": "Lack of emotional support",
}
CATEGORY_LABELS = {
    "health_outcome": "Health outcome",
    "health_status": "Health status",
    "health_risk_behavior": "Risk behavior",
    "prevention": "Prevention",
    "disability": "Disability",
    "health_related_social_need": "Social need",
}
CORE = {"DIABETES", "OBESITY", "LPA"}
CLUSTER_CUT = 0.55  # average-linkage height (1 - rho) used to name groups


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
    adj["category_label"] = adj["measure_category"].map(CATEGORY_LABELS)
    adj["label"] = adj["measure"].map(LABELS)
    if adj["label"].isna().any() or adj["category_label"].isna().any():
        raise SystemExit("Unlabelled measure or category in the field dictionary.")
    return adj[["measure", "label", "measure_category", "category_label", "year", "description"]].reset_index(drop=True)


def average_linkage(dist: np.ndarray) -> tuple[list[dict], list[int]]:
    """Plain UPGMA. Returns merges and the dendrogram leaf order."""
    n = len(dist)
    clusters = {i: [i] for i in range(n)}
    nodes = {i: {"id": i, "leaf": i, "height": 0.0} for i in range(n)}
    d = {(i, j): dist[i, j] for i in range(n) for j in range(i + 1, n)}
    merges = []
    next_id = n
    while len(clusters) > 1:
        (a, b), h = min(d.items(), key=lambda kv: (kv[1], kv[0]))
        members = clusters.pop(a) + clusters.pop(b)
        node = {"id": next_id, "left": a, "right": b, "height": float(h), "size": len(members)}
        nodes[next_id] = node
        merges.append(node)
        d = {k: v for k, v in d.items() if a not in k and b not in k}
        for other, om in clusters.items():
            avg = float(np.mean([dist[x, y] for x in members for y in om]))
            d[(min(other, next_id), max(other, next_id))] = avg
        clusters[next_id] = members
        next_id += 1

    def leaves(node_id: int) -> list[int]:
        node = nodes[node_id]
        if "leaf" in node:
            return [node["leaf"]]
        return leaves(node["left"]) + leaves(node["right"])

    return merges, leaves(next_id - 1)


def cut_tree(merges: list[dict], n: int, height: float) -> list[int]:
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    members = {i: [i] for i in range(n)}
    for m in merges:
        members[m["id"]] = members[m["left"]] + members[m["right"]]
        if m["height"] <= height:
            root = members[m["id"]][0]
            for leaf in members[m["id"]]:
                parent[find(leaf)] = find(root)
    return [find(i) for i in range(n)]


def main() -> None:
    digest = check_input()
    data = pd.read_csv(INPUT, dtype={"CountyFIPS": str}, encoding="utf-8-sig")
    catalog = measure_catalog()

    # ---- 1. catalog with county distribution summaries -----------------
    rows = []
    for m in catalog.itertuples():
        values = data[f"{m.measure}_AdjPrev"].dropna()
        rows.append({
            "measure": m.measure,
            "label": m.label,
            "category": m.category_label,
            "year": m.year,
            "core_eda": m.measure in CORE,
            "counties": int(values.size),
            "states": int(data.loc[values.index, "StateAbbr"].nunique()),
            "median": round(float(values.median()), 2),
            "p25": round(float(values.quantile(.25)), 2),
            "p75": round(float(values.quantile(.75)), 2),
            "min": float(values.min()),
            "max": float(values.max()),
            "iqr_over_median": round(float((values.quantile(.75) - values.quantile(.25)) / values.median()), 3),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "extended_measure_catalog.csv", index=False)

    # ---- 2. 2023 measure landscape -----------------------------------
    m23 = catalog[catalog["year"] == 2023]["measure"].tolist()
    cols = [f"{m}_AdjPrev" for m in m23]
    ranks = data[cols].rank()
    rho = ranks.corr(method="pearson", min_periods=500)  # Spearman = Pearson on ranks
    present = data[cols].notna().astype(int)
    pair_n = present.T.dot(present)
    rho.index = rho.columns = m23
    pair_n.index = pair_n.columns = m23
    if rho.isna().any().any():
        raise SystemExit("Undefined Spearman correlation in the 2023 landscape.")
    merges, order = average_linkage(1 - rho.to_numpy())
    groups_raw = cut_tree(merges, len(m23), CLUSTER_CUT)
    group_ids = {}
    for leaf in order:  # number groups by dendrogram order
        group_ids.setdefault(groups_raw[leaf], len(group_ids) + 1)
    group_of = {m23[i]: group_ids[groups_raw[i]] for i in range(len(m23))}

    ordered = [m23[i] for i in order]
    rho.loc[ordered, ordered].round(4).to_csv(OUT / "extended_spearman_matrix.csv")
    tri = []
    for i, a in enumerate(m23):
        for b in m23[i + 1:]:
            tri.append({"a": a, "b": b, "rho": round(float(rho.loc[a, b]), 4), "n": int(pair_n.loc[a, b])})
    pairs = pd.DataFrame(tri).sort_values("rho")
    pairs.to_csv(OUT / "extended_spearman_pairs.csv", index=False)
    clusters = {
        "method": "average linkage (UPGMA) on distance 1 - Spearman rho, pairwise-complete counties",
        "cut_height": CLUSTER_CUT,
        "order": ordered,
        "groups": group_of,
        "merges": [{**m, "left": int(m["left"]), "right": int(m["right"])} for m in merges],
        "leaf_names": m23,
    }
    (OUT / "extended_clusters.json").write_text(json.dumps(clusters, indent=2), encoding="utf-8")

    # ---- 3. state medians vs national county median -------------------
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

    # ---- 4. crude minus age-adjusted gap ------------------------------
    gap_rows = []
    gaps = {}
    for m in catalog.itertuples():
        g = (data[f"{m.measure}_CrudePrev"] - data[f"{m.measure}_AdjPrev"]).dropna()
        gaps[m.measure] = g
        gap_rows.append({
            "measure": m.measure,
            "label": m.label,
            "category": m.category_label,
            "year": m.year,
            "counties": int(g.size),
            "median_gap_pp": round(float(g.median()), 2),
            "p05": round(float(g.quantile(.05)), 2),
            "p95": round(float(g.quantile(.95)), 2),
            "share_crude_higher": round(float((g > 0).mean()), 3),
            "median_relative_gap": round(float((g / data.loc[g.index, f"{m.measure}_AdjPrev"]).median()), 3),
        })
    gap_table = pd.DataFrame(gap_rows).sort_values("median_gap_pp", ascending=False)
    gap_table.to_csv(OUT / "extended_age_adjustment_gap.csv", index=False)

    # Counties the age structure moves most: mean z-score of the gap over the
    # age-graded chronic outcomes with complete 2023 data.
    age_graded = ["ARTHRITIS", "BPHIGH", "CHD", "COPD", "HIGHCHOL", "CANCER", "HEARING", "MOBILITY"]
    gz = pd.DataFrame({m: (gaps[m] - gaps[m].mean()) / gaps[m].std() for m in age_graded}).dropna()
    county_gap = data.loc[gz.index, ["CountyFIPS", "derived__CountyName_display", "StateAbbr", "TotalPopulation"]].copy()
    county_gap["age_gap_index"] = gz.mean(axis=1).round(3)
    for m in age_graded:
        county_gap[f"{m}_gap_pp"] = gaps[m].loc[gz.index].round(2)
    county_gap = county_gap.sort_values("age_gap_index", ascending=False)
    county_gap.to_csv(OUT / "extended_county_age_gap_index.csv", index=False)
    gap_corr = gz.corr().to_numpy()[np.triu_indices(len(age_graded), 1)]

    # ---- report -------------------------------------------------------
    now = datetime.now(TZ).replace(microsecond=0).isoformat()
    lab = dict(zip(catalog["measure"], catalog["label"]))
    group_members: dict[int, list[str]] = {}
    for m in ordered:
        group_members.setdefault(group_of[m], []).append(m)
    hrsn = catalog[catalog["measure_category"] == "health_related_social_need"]["measure"].tolist()
    hr = pairs[(pairs["a"].isin(hrsn) ^ pairs["b"].isin(hrsn))].copy()
    hr["abs"] = hr["rho"].abs()
    top_hr = hr.sort_values("abs", ascending=False).head(6)
    fmt = lambda r: f"{lab[r.a]} × {lab[r.b]}"

    lines = [
        "# 扩展探索分析（Extended preliminary analysis）报告",
        "",
        f"生成时间（Generated）：{now}",
        "",
        "## 1. 为什么扩展",
        "",
        f"核心 EDA 只用了 40 项年龄调整指标中的 3 项（糖尿病、肥胖、缺乏体育活动）。本轮对其余 37 项做初步分析，回答三个描述性问题：",
        "",
        "1. 35 项 2023 指标之间的县级共变结构（Measure landscape）是什么样的？",
        "2. 各州的县级中位数相对全国县级中位数偏高还是偏低（State profiles）？",
        "3. 粗率（Crude）与年龄调整率（Age-adjusted）差多少，哪些指标、哪些县受人口年龄结构影响最大？",
        "",
        "## 2. 数据范围",
        "",
        f"- 输入：已验收清洗表，SHA-256 `{digest}`，3,143 行。",
        "- 35 项指标为 2023 年估计；`COLON_SCREEN`、`DENTAL`、`MAMMOUSE`、`SLEEP`、`TEETHLOST` 5 项为 2022 年估计，3,143 县全有值。2022 指标不进入第 3 节的相关矩阵，避免混合年份。",
        "- Kentucky、Pennsylvania 无 2023 估计；7 项社会需求（HRSN）指标另在 CO、FL、OR、SD、TN、TX、VT、WA、WY 空白，只有 2,299 县有值。空白一律保留为缺失，不补零。",
        "- `LONELINESS` 按交接文件的约定标为 Loneliness（字段字典描述仍写 socially isolated；发布说明称已改为孤独）。",
        "- `ACCESS2`（18–64 岁）、`BPMED`（高血压患者）、`COLON_SCREEN`、`MAMMOUSE`、`TEETHLOST` 的分母不是全部成年人，只与自身比较。",
        "",
        "## 3. 指标共变结构（Measure landscape）",
        "",
        "方法：两两完整县（Pairwise complete）的 Spearman `ρ`；以 `1 − ρ` 为距离做平均连接层次聚类（Average-linkage / UPGMA），"
        f"在高度 {CLUSTER_CUT} 处切分成组。社会需求指标与其他指标的配对只有 2,299 县，其余配对为 2,956 县。",
        "",
        "| 组 | 成员 |",
        "| ---: | --- |",
    ]
    for gid, mem in group_members.items():
        lines.append(f"| {gid} | {', '.join(lab[m] for m in mem)} |")
    strongest = pairs.sort_values("rho", ascending=False).head(5)
    weakest = pairs.head(5)
    lines += [
        "",
        "最强正相关：" + "；".join(f"{fmt(r)} `ρ = {r.rho:.2f}`" for r in strongest.itertuples()) + "。",
        "",
        "最强负相关：" + "；".join(f"{fmt(r)} `ρ = {r.rho:.2f}`" for r in weakest.itertuples()) + "。",
        "",
        "社会需求与其他类别关联最强的配对：" + "；".join(f"{fmt(r)} `ρ = {r.rho:.2f}`" for r in top_hr.itertuples()) + "。",
        "",
        "初步解读：慢性病、健康状况、残疾和社会需求在县级高度同向共变，形成一个大的“负担”簇；"
        "暴饮（Binge drinking）、筛查与就诊类预防指标多与该簇负相关。高相关部分源于 PLACES 小域模型共享县级协变量，"
        "不能当作独立证据。",
        "",
        "## 4. 州级轮廓（State profiles）",
        "",
        "方法：每州县级估计的中位数减去全国县级中位数（百分点）。这是县的中位数，不是州人口患病率；县数少的州（DC 1 县、DE 3 县、HI 5 县）波动更大。",
        "",
    ]
    show = ["DEPRESSION", "LONELINESS", "FOODINSECU", "CSMOKING", "BINGE", "CHECKUP"]
    lines += ["| 指标 | 全国县中位数 | 最高的 3 州（差值） | 最低的 3 州（差值） |", "| --- | ---: | --- | --- |"]
    for m in show:
        s = states[(states.measure == m) & states.difference_pp.notna()].sort_values("difference_pp")
        hi = ", ".join(f"{r.state} {r.difference_pp:+.1f}" for r in s.tail(3)[::-1].itertuples())
        lo = ", ".join(f"{r.state} {r.difference_pp:+.1f}" for r in s.head(3).itertuples())
        lines.append(f"| {lab[m]} | {s.national_median.iloc[0]:.1f}% | {hi} | {lo} |")
    lines += [
        "",
        "完整 40 × 51 表见 `outputs/extended_state_medians.csv`。",
        "",
        "## 5. 年龄调整差（Crude − age-adjusted）",
        "",
        "差值为正表示该县成年人口比美国 2000 年标准人口更老，粗率因此高于年龄调整率。",
        "",
        "| 指标 | 年份 | 中位差（百分点） | 5%–95% | 粗率更高的县占比 |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for r in pd.concat([gap_table.head(6), gap_table.tail(4)]).itertuples():
        lines.append(f"| {r.label} | {r.year} | {r.median_gap_pp:+.2f} | {r.p05:+.1f} 至 {r.p95:+.1f} | {r.share_crude_higher:.0%} |")
    top = county_gap.head(5)
    lines += [
        "",
        f"8 项年龄相关慢性指标的县级差值彼此高度一致（两两相关中位数 {np.median(gap_corr):.2f}），说明差值主要反映同一个县级年龄结构因素。"
        "按这 8 项差值的平均 z 分数排序，差值最大的县为："
        + "；".join(f"{r.derived__CountyName_display}, {r.StateAbbr}（{r.age_gap_index:+.2f}）" for r in top.itertuples()) + "。",
        "",
        "含义：比较县与县的健康负担时应使用年龄调整率（本项目已如此）；规划服务需求时，粗率更接近当地实际人数比例。",
        "",
        "## 6. 解读边界",
        "",
        "- 全部为县级生态描述，不推断个人风险，也不推断因果。",
        "- 估计来自同一小域模型，共享协变量会抬高指标间相关。",
        "- 聚类切分高度是为了可读性选定的探索参数，不是统计检验结果。",
        "- 州中位数不等于州患病率；未按人口加权。",
        "",
        "## 7. 对应可视化",
        "",
        "- `03_visualisations/final/interactive_measure_landscape/`：聚类相关热力图 + 树状图（Dendrogram）+ 六边形分箱密度图（Hexbin）。",
        "- `03_visualisations/final/interactive_state_tiles/`：州瓦片地图（Tile-grid cartogram）+ 发散色阶 + 州排名点图。",
        "- `03_visualisations/final/interactive_age_gap/`：山脊图（Ridgeline）+ 县级哑铃图（Dumbbell）。",
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
        "cluster_groups": len(group_members),
        "outputs": sorted(str(p.relative_to(ROOT)) for p in OUT.glob("extended_*")) + [str(REPORT.relative_to(ROOT))],
    }
    (OUT / "extended_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
