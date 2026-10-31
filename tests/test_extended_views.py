"""Checks for the extended analysis and its visualisations."""

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


def test_average_linkage_on_toy_matrix():
    analysis = load(ROOT / "02_analysis/extended_analysis.py")
    dist = np.array([[0, 1, 9, 9], [1, 0, 9, 9], [9, 9, 0, 2], [9, 9, 2, 0]], dtype=float)
    merges, order = analysis.average_linkage(dist)
    assert [m["height"] for m in merges] == [1.0, 2.0, 9.0]
    assert sorted(order[:2]) == [0, 1] and sorted(order[2:]) == [2, 3]
    groups = analysis.cut_tree(merges, 4, 5.0)
    assert groups[0] == groups[1] != groups[2] == groups[3]


def test_extended_analysis_outputs():
    catalog = pd.read_csv(OUT / "extended_measure_catalog.csv")
    assert len(catalog) == 40
    assert (catalog["year"] == 2022).sum() == 5
    matrix = pd.read_csv(OUT / "extended_spearman_matrix.csv", index_col=0)
    assert matrix.shape == (35, 35)
    assert np.allclose(matrix.to_numpy(), matrix.to_numpy().T)
    assert np.allclose(np.diag(matrix.to_numpy()), 1)
    states = pd.read_csv(OUT / "extended_state_medians.csv")
    assert states["state"].nunique() == 51
    # Unpublished values must stay missing, never zero.
    ky = states[(states["state"] == "KY") & (states["measure"] == "DIABETES")]
    assert ky["counties"].iloc[0] == 0 and pd.isna(ky["state_median"].iloc[0])
    hrsn = states[(states["measure"] == "FOODINSECU") & (states["counties"] == 0)]
    assert set(hrsn["state"]) == {"CO", "FL", "KY", "OR", "PA", "SD", "TN", "TX", "VT", "WA", "WY"}


def test_views_validation_and_files():
    result = json.loads((OUT / "extended_views_validation.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    for rel in result["outputs"]:
        path = ROOT / rel
        assert path.is_file(), rel
        if path.suffix == ".svg":
            xml.dom.minidom.parse(str(path))
        else:
            text = path.read_text(encoding="utf-8")
            if "interactive_" in rel:
                assert '<script id="data" type="application/json">' in text
                payload = text.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0]
                json.loads(payload)  # strict JSON: no NaN/Infinity
    gallery = (FINAL / "index.html").read_text(encoding="utf-8")
    for href in re.findall(r'href="(interactive_[^"/]+)/index.html"', gallery):
        assert (FINAL / href / "index.html").is_file(), href
