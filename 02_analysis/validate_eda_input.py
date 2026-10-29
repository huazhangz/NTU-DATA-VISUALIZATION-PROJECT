#!/usr/bin/env python3
"""Validate the cleaned CDC PLACES table before formal EDA.

This is an acceptance check, not a second cleaning pipeline. It reads the
cleaned table and field dictionary and writes reproducible QA outputs under
``02_analysis/outputs``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "01_data" if (ROOT / "01_data").is_dir() else ROOT / "data"
DATA = DATA_ROOT / "processed/places_county_gis_2025_i46a-9kgh_cleaned.csv"
DICTIONARY = DATA_ROOT / "processed/places_county_gis_2025_field_dictionary.csv"
RAW = DATA_ROOT / "raw/places_county_gis_2025_i46a-9kgh.csv"
RAW_HASH_RECORD = DATA_ROOT / "metadata/raw_sha256.txt"
OUT = ROOT / "02_analysis/outputs"

EXPECTED_ROWS = 3_143
EXPECTED_COLUMNS = 332
EXPECTED_LEADING_ZERO_FIPS = 318
EXPECTED_2023_MISSING_STATES = {"KY", "PA"}
CORE_METRICS = [
    "DIABETES_AdjPrev",
    "OBESITY_AdjPrev",
    "LPA_AdjPrev",
    "CSMOKING_AdjPrev",
    "ACCESS2_AdjPrev",
]
REQUIRED_CONTEXT_COLUMNS = [
    "StateAbbr",
    "StateDesc",
    "CountyName",
    "CountyFIPS",
    "TotalPopulation",
    "TotalPop18plus",
    "derived__CountyName_display",
    "derived__Geolocation_Longitude",
    "derived__Geolocation_Latitude",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, object]] = []

    def record(check_id: str, description: str, passed: bool, observed: object, expected: object) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "description": description,
                "observed": observed,
                "expected": expected,
            }
        )

    required_files = [DATA, DICTIONARY, RAW, RAW_HASH_RECORD]
    missing_files = [str(path.relative_to(ROOT)) for path in required_files if not path.is_file()]
    record("A01", "Required input files exist", not missing_files, missing_files, "none missing")
    if missing_files:
        write_results(checks, {}, {}, {})
        return 1

    expected_raw_hash = RAW_HASH_RECORD.read_text(encoding="utf-8").strip().split()[0]
    observed_raw_hash = sha256(RAW)
    record("A02", "Raw CSV hash matches the supplied provenance record", observed_raw_hash == expected_raw_hash, observed_raw_hash, expected_raw_hash)

    df = pd.read_csv(DATA, dtype={"CountyFIPS": "string"}, low_memory=False)
    dictionary = pd.read_csv(DICTIONARY)

    record("A03", "Cleaned table has the expected number of rows", len(df) == EXPECTED_ROWS, len(df), EXPECTED_ROWS)
    record("A04", "Cleaned table has the expected number of columns", len(df.columns) == EXPECTED_COLUMNS, len(df.columns), EXPECTED_COLUMNS)
    record("A05", "Field dictionary has one row per cleaned column", len(dictionary) == len(df.columns), len(dictionary), len(df.columns))

    dictionary_columns = dictionary["column_name"].astype(str).tolist()
    record("A06", "Field dictionary names and order match the cleaned table", dictionary_columns == df.columns.tolist(), "exact match" if dictionary_columns == df.columns.tolist() else "mismatch", "exact match")

    required_columns = REQUIRED_CONTEXT_COLUMNS + CORE_METRICS
    absent_columns = [column for column in required_columns if column not in df.columns]
    record("A07", "Required geographic, label, population, and core metric fields exist", not absent_columns, absent_columns, "none missing")
    if absent_columns:
        write_results(checks, {}, {}, {})
        return 1

    fips = df["CountyFIPS"]
    valid_fips = fips.str.fullmatch(r"\d{5}", na=False)
    record("A08", "Every CountyFIPS is a five-digit text key", bool(valid_fips.all()), int((~valid_fips).sum()), 0)
    record("A09", "CountyFIPS is unique", not bool(fips.duplicated().any()), int(fips.duplicated().sum()), 0)
    leading_zero_count = int(fips.str.startswith("0", na=False).sum())
    record("A10", "Leading-zero FIPS codes were preserved", leading_zero_count == EXPECTED_LEADING_ZERO_FIPS, leading_zero_count, EXPECTED_LEADING_ZERO_FIPS)

    numeric_failures: dict[str, int] = {}
    out_of_range: dict[str, int] = {}
    ci_failures: dict[str, int] = {}
    missing_rows: list[dict[str, object]] = []
    state_missing_rows: list[dict[str, object]] = []

    for metric in CORE_METRICS:
        numeric = pd.to_numeric(df[metric], errors="coerce")
        numeric_failures[metric] = int(df[metric].notna().sum() - numeric.notna().sum())
        out_of_range[metric] = int((numeric.notna() & ~numeric.between(0, 100)).sum())
        missing_states = sorted(df.loc[numeric.isna(), "StateAbbr"].dropna().unique().tolist())
        missing_rows.append(
            {
                "metric": metric,
                "non_missing": int(numeric.notna().sum()),
                "missing": int(numeric.isna().sum()),
                "missing_pct": round(float(numeric.isna().mean() * 100), 2),
                "missing_states": ";".join(missing_states),
            }
        )

        prefix = metric.removesuffix("_AdjPrev")
        low = pd.to_numeric(df[f"derived__{prefix}_Adj95CI_Low"], errors="coerce")
        high = pd.to_numeric(df[f"derived__{prefix}_Adj95CI_High"], errors="coerce")
        comparable = numeric.notna() & low.notna() & high.notna()
        ci_failures[metric] = int((comparable & ((low > numeric) | (numeric > high) | (low > high))).sum())

    record("A11", "Core metric nonblank values are numeric", sum(numeric_failures.values()) == 0, numeric_failures, "all zero")
    record("A12", "Core metric estimates are percentages between 0 and 100", sum(out_of_range.values()) == 0, out_of_range, "all zero")
    record("A13", "Core point estimates fall inside their supplied intervals", sum(ci_failures.values()) == 0, ci_failures, "all zero")

    metric_missing = pd.DataFrame(missing_rows)
    missing_state_sets = {
        row.metric: set(str(row.missing_states).split(";")) if row.missing_states else set()
        for row in metric_missing.itertuples()
    }
    missing_pattern_ok = all(states == EXPECTED_2023_MISSING_STATES for states in missing_state_sets.values())
    missing_counts_ok = bool((metric_missing["missing"] == 187).all())
    record(
        "A14",
        "Core 2023 metric gaps are the documented 187 KY/PA counties",
        missing_pattern_ok and missing_counts_ok,
        {row.metric: {"count": row.missing, "states": row.missing_states} for row in metric_missing.itertuples()},
        {"count": 187, "states": "KY;PA"},
    )

    for (state_abbr, state_desc), group in df.groupby(["StateAbbr", "StateDesc"], dropna=False):
        for metric in CORE_METRICS:
            missing = int(group[metric].isna().sum())
            state_missing_rows.append(
                {
                    "StateAbbr": state_abbr,
                    "StateDesc": state_desc,
                    "metric": metric,
                    "county_rows": len(group),
                    "missing": missing,
                    "missing_pct": round(missing / len(group) * 100, 2),
                }
            )

    longitude = pd.to_numeric(df["derived__Geolocation_Longitude"], errors="coerce")
    latitude = pd.to_numeric(df["derived__Geolocation_Latitude"], errors="coerce")
    invalid_coordinates = int((longitude.isna() | latitude.isna() | ~longitude.between(-180, 180) | ~latitude.between(-90, 90)).sum())
    record("A15", "Derived longitude and latitude are numeric and within world bounds", invalid_coordinates == 0, invalid_coordinates, 0)

    blank_labels = int(df["derived__CountyName_display"].isna().sum())
    record("A16", "Every row has a display county name", blank_labels == 0, blank_labels, 0)

    metric_missing.to_csv(OUT / "input_missingness_by_metric.csv", index=False)
    pd.DataFrame(state_missing_rows).to_csv(OUT / "input_missingness_by_state.csv", index=False)

    summary = {
        "cleaned_rows": len(df),
        "cleaned_columns": len(df.columns),
        "unique_county_fips": int(fips.nunique()),
        "states_and_dc": int(df["StateAbbr"].nunique()),
        "cleaned_sha256": sha256(DATA),
        "raw_sha256": observed_raw_hash,
    }
    write_results(checks, summary, numeric_failures, ci_failures)
    return 1 if any(check["status"] == "FAIL" for check in checks) else 0


def write_results(
    checks: list[dict[str, object]],
    summary: dict[str, object],
    numeric_failures: dict[str, int],
    ci_failures: dict[str, int],
) -> None:
    timestamp = datetime.now(ZoneInfo("Asia/Singapore")).isoformat(timespec="seconds")
    passed = sum(check["status"] == "PASS" for check in checks)
    failed = sum(check["status"] == "FAIL" for check in checks)
    payload = {
        "generated_at": timestamp,
        "status": "PASS" if failed == 0 else "FAIL",
        "passed": passed,
        "failed": failed,
        "summary": summary,
        "checks": checks,
    }
    (OUT / "input_validation.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# EDA input acceptance report",
        "",
        f"Generated: {timestamp}",
        "",
        f"**Overall status: {payload['status']} ({passed} passed, {failed} failed)**",
        "",
    ]
    if summary:
        lines.extend(
            [
                "## Input summary",
                "",
                f"- Cleaned table: {summary['cleaned_rows']:,} rows × {summary['cleaned_columns']:,} columns",
                f"- Unique county FIPS keys: {summary['unique_county_fips']:,}",
                f"- State/DC codes represented: {summary['states_and_dc']}",
                f"- Cleaned SHA-256: `{summary['cleaned_sha256']}`",
                "",
            ]
        )
    lines.extend(["## Checks", "", "| ID | Status | Check | Observed |", "| --- | --- | --- | --- |"])
    for check in checks:
        observed = json.dumps(check["observed"], ensure_ascii=False) if isinstance(check["observed"], (dict, list)) else str(check["observed"])
        lines.append(f"| {check['check_id']} | {check['status']} | {check['description']} | {observed} |")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The cleaned table is accepted as the formal EDA input." if failed == 0 else "The cleaned table is not accepted. Resolve failed checks before formal EDA.",
            "",
            "This acceptance does not remove the documented analytical limits: blanks are not zero; crude and age-adjusted estimates must remain separate; map joins use `CountyFIPS`; and modelled county estimates should not be presented as causal effects or an overall health ranking.",
            "",
        ]
    )
    (OUT / "input_validation_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
