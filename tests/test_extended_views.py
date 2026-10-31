"""Checks for the extended analysis and the final visualisations."""

from __future__ import annotations

import importlib.util
import json
import re
import xml.dom.minidom
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "02_analysis/outputs"
FINAL = ROOT / "03_visualisations/final"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strength_words():
    analysis = load(ROOT / "02_analysis/extended_analysis.py")
    assert analysis.strength(0.95) == "strong"
    assert analysis.strength(-0.7) == "strong"
    assert analysis.strength(0.55) == "moderate"
    assert analysis.strength(-0.25) == "weak"
    assert analysis.strength(0.1) == "little or none"


def test_extended_analysis_outputs():
    catalog = pd.read_csv(OUT / "extended_measure_catalog.csv")
    assert len(catalog) == 40
    assert (catalog["year"] == 2022).sum() == 5
    assert catalog.loc[~catalog["in_charts"], "measure"].tolist() == ["BPMED"]
    matrix = pd.read_csv(OUT / "extended_spearman_matrix.csv", index_col=0)
    assert matrix.shape == (35, 35)
    assert np.allclose(matrix.to_numpy(), matrix.to_numpy().T)
    assert np.allclose(np.diag(matrix.to_numpy()), 1)
    pairs = pd.read_csv(OUT / "extended_spearman_pairs.csv")
    assert len(pairs) == 35 * 34 // 2
    states = pd.read_csv(OUT / "extended_state_medians.csv")
    assert states["state"].nunique() == 51
    # Unpublished values must stay missing, never zero.
    ky = states[(states["state"] == "KY") & (states["measure"] == "DIABETES")]
    assert ky["counties"].iloc[0] == 0 and pd.isna(ky["state_median"].iloc[0])
    hrsn = states[(states["measure"] == "FOODINSECU") & (states["counties"] == 0)]
    assert set(hrsn["state"]) == {"CO", "FL", "KY", "OR", "PA", "SD", "TN", "TX", "VT", "WA", "WY"}


def test_core_regressions_use_diabetes_as_outcome():
    reg = pd.read_csv(OUT / "relationship_regressions.csv")
    diabetes_rows = reg[(reg["predictor"] == "DIABETES_AdjPrev") | (reg["outcome"] == "DIABETES_AdjPrev")]
    assert (diabetes_rows["outcome"] == "DIABETES_AdjPrev").all()


def test_state_medians_are_deterministic_and_rounded():
    medians = pd.read_csv(OUT / "basic_state_county_medians.csv")
    numeric = medians.select_dtypes("number")
    assert (numeric.round(2).fillna(-1) == numeric.fillna(-1)).all().all()
    ordered = medians.sort_values(["DIABETES_AdjPrev", "StateAbbr"], na_position="last", kind="mergesort")
    assert ordered["StateAbbr"].tolist() == medians["StateAbbr"].tolist()


def test_views_and_gallery():
    result = json.loads((OUT / "extended_views_validation.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    for rel in result["outputs"]:
        path = ROOT / rel
        assert path.is_file(), rel
        if path.suffix == ".svg":
            xml.dom.minidom.parse(str(path))
        elif "interactive_" in rel:
            text = path.read_text(encoding="utf-8")
            payload = text.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0]
            json.loads(payload)  # strict JSON: no NaN/Infinity
    gallery = (FINAL / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'href="(interactive_[^"/]+)/index.html"', gallery)
    assert len(links) == 5
    for href in links:
        assert (FINAL / href / "index.html").is_file(), href
    for other in FINAL.glob("interactive_*"):
        assert other.name in links, f"{other.name} is not linked from the gallery"


def test_no_county_suffix_on_county_equivalents():
    for name in ("interactive_county_map", "interactive_relationship", "interactive_overlap"):
        text = (FINAL / name / "index.html").read_text(encoding="utf-8")
        assert "Orleans Parish" in text or "Orleans Parish" in text.replace("\\u", "")
        assert "Parish County" not in text and "city County" not in text
