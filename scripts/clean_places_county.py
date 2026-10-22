"""Reproducible cleaning for CDC PLACES county GIS data, 2025 release.

The raw CSV is read as text and never overwritten. Source cells are copied
unchanged. Derived columns are appended and named with a derived__ prefix.
Running this script again on the same raw file produces the same cleaned bytes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collections import Counter

from places_common import (
    CI_RE,
    CLEAN_CSV,
    COLUMNS_JSON,
    GEOLOCATION_COLUMN,
    MEASURE_CATEGORY,
    MEASURE_RE,
    POINT_RE,
    RAW_CSV,
    RAW_SHA_PATH,
    ROOT,
    RUN_DIR,
    append_log,
    read_raw_table,
    sha256_file,
    write_csv,
)

# The only non-ASCII county short name in the raw file. U+00C3 U+00B1 is the
# UTF-8 byte pair for ñ (C3 B1) after it was decoded as Latin-1 and saved again.
MOJIBAKE_DONA_ANA = "Do\u00c3\u00b1a Ana"
REPAIRED_DONA_ANA = "Do\u00f1a Ana"
DONA_ANA_FIPS = "35013"


def is_confidence_interval(column: str) -> bool:
    match = MEASURE_RE.match(column)
    return bool(match and match.group("stat") in {"95CI", "95ci"})


def derived_header(source_header: list[str]) -> list[str]:
    derived = [
        "derived__source_row_number",
        "derived__CountyName_display",
        "derived__short_name_collision",
        "derived__Geolocation_Longitude",
        "derived__Geolocation_Latitude",
    ]
    for column in source_header:
        if is_confidence_interval(column):
            derived.append(f"derived__{column}_Low")
            derived.append(f"derived__{column}_High")
    return derived


def clean_table(source_header: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]], dict]:
    """Return cleaned header, cleaned rows, and machine-readable counts.

    Source values are not rewritten. Derived fields are deterministic.
    """
    name_counts = Counter((row["StateAbbr"], row["CountyName"]) for row in rows)
    collisions = {key for key, count in name_counts.items() if count > 1}

    header = list(source_header) + derived_header(source_header)
    cleaned: list[dict[str, str]] = []
    stats = {
        "n_rows": len(rows),
        "n_source_columns": len(source_header),
        "n_derived_columns": len(header) - len(source_header),
        "n_output_columns": len(header),
        "ci_cells_parsed": 0,
        "ci_cells_blank": 0,
        "ci_parse_failures": 0,
        "geolocation_parsed": 0,
        "geolocation_blank": 0,
        "geolocation_parse_failures": 0,
        "short_name_collision_rows": 0,
        "county_display_repairs": 0,
        "county_display_unresolved_non_ascii": 0,
        "source_cells_changed": 0,
        "repair_details": [],
        "parse_failure_details": [],
    }

    for row_number, source in enumerate(rows, start=1):
        output = {column: source[column] for column in source_header}
        output["derived__source_row_number"] = str(row_number)
        name = source["CountyName"]
        fips = source["CountyFIPS"]
        if fips == DONA_ANA_FIPS and name == MOJIBAKE_DONA_ANA:
            repaired = name.encode("latin-1").decode("utf-8")
            if repaired != REPAIRED_DONA_ANA:
                raise RuntimeError("Doña Ana repair did not produce the expected Census spelling.")
            output["derived__CountyName_display"] = repaired
            stats["county_display_repairs"] += 1
            stats["repair_details"].append(
                {
                    "source_row_number": row_number,
                    "CountyFIPS": fips,
                    "original": name,
                    "derived__CountyName_display": repaired,
                }
            )
        else:
            output["derived__CountyName_display"] = name
            if any(ord(char) > 127 for char in name):
                stats["county_display_unresolved_non_ascii"] += 1
                stats["parse_failure_details"].append(
                    {"source_row_number": row_number, "CountyFIPS": fips, "CountyName": name, "issue": "unresolved_non_ascii"}
                )

        collision = "yes" if (source["StateAbbr"], name) in collisions else "no"
        output["derived__short_name_collision"] = collision
        if collision == "yes":
            stats["short_name_collision_rows"] += 1

        point = source[GEOLOCATION_COLUMN]
        if point == "":
            output["derived__Geolocation_Longitude"] = ""
            output["derived__Geolocation_Latitude"] = ""
            stats["geolocation_blank"] += 1
        else:
            match = POINT_RE.match(point)
            if not match:
                output["derived__Geolocation_Longitude"] = ""
                output["derived__Geolocation_Latitude"] = ""
                stats["geolocation_parse_failures"] += 1
                stats["parse_failure_details"].append(
                    {"source_row_number": row_number, "CountyFIPS": fips, "issue": "geolocation_parse_fail", "value": point}
                )
            else:
                output["derived__Geolocation_Longitude"] = match.group(1)
                output["derived__Geolocation_Latitude"] = match.group(2)
                stats["geolocation_parsed"] += 1

        for column in source_header:
            if not is_confidence_interval(column):
                continue
            value = source[column]
            low_key = f"derived__{column}_Low"
            high_key = f"derived__{column}_High"
            if value == "":
                output[low_key] = ""
                output[high_key] = ""
                stats["ci_cells_blank"] += 1
                continue
            match = CI_RE.match(value)
            if not match:
                output[low_key] = ""
                output[high_key] = ""
                stats["ci_parse_failures"] += 1
                stats["parse_failure_details"].append(
                    {"source_row_number": row_number, "CountyFIPS": fips, "issue": "ci_parse_fail", "column": column, "value": value}
                )
                continue
            output[low_key] = match.group(1)
            output[high_key] = match.group(2)
            stats["ci_cells_parsed"] += 1

        for column in source_header:
            if output[column] != source[column]:
                stats["source_cells_changed"] += 1
        cleaned.append(output)

    return header, cleaned, stats


def field_dictionary(source_header: list[str], cleaned_header: list[str]) -> list[dict[str, str]]:
    metadata = json.loads(COLUMNS_JSON.read_text(encoding="utf-8"))
    by_name = {item.get("name"): item for item in metadata}
    rows = []
    for position, column in enumerate(cleaned_header, start=1):
        if column in source_header:
            meta = by_name.get(column, {})
            match = MEASURE_RE.match(column)
            measure = match.group("measure") if match else ""
            rows.append(
                {
                    "column_position": position,
                    "column_name": column,
                    "origin": "source",
                    "measure_id": measure,
                    "measure_category": MEASURE_CATEGORY.get(measure, ""),
                    "metadata_data_type": meta.get("dataTypeName", ""),
                    "description": meta.get("description", ""),
                    "rule_id": "R01",
                }
            )
            continue
        description, rule_id = derived_description(column)
        rows.append(
            {
                "column_position": position,
                "column_name": column,
                "origin": "derived",
                "measure_id": "",
                "measure_category": "",
                "metadata_data_type": "",
                "description": description,
                "rule_id": rule_id,
            }
        )
    return rows


def derived_description(column: str) -> tuple[str, str]:
    if column == "derived__source_row_number":
        return ("1-based data-row position in the preserved raw CSV, excluding the header. Audit key only.", "R11")
    if column == "derived__CountyName_display":
        return (
            "County short name for display. Equal to CountyName except FIPS 35013, where the published mojibake DoÃ±a Ana is repaired to Doña Ana. The source CountyName column is unchanged.",
            "R13",
        )
    if column == "derived__short_name_collision":
        return (
            "yes when this StateAbbr and CountyName pair occurs on more than one row. Those rows are different county-equivalents and must be keyed by CountyFIPS.",
            "R12",
        )
    if column == "derived__Geolocation_Longitude":
        return ("Longitude parsed from the source Geolocation WKT POINT. The source field is unchanged. WGS84 degree text as published inside the point.", "R10")
    if column == "derived__Geolocation_Latitude":
        return ("Latitude parsed from the source Geolocation WKT POINT. The source field is unchanged.", "R10")
    if column.endswith("_Low"):
        return ("Lower 95% confidence limit parsed from the source confidence-interval text. Blank when the source interval is blank. Not a new estimate.", "R09")
    if column.endswith("_High"):
        return ("Upper 95% confidence limit parsed from the source confidence-interval text. Blank when the source interval is blank. Not a new estimate.", "R09")
    return ("Derived field.", "")


def transformation_log(stats: dict) -> list[dict[str, str]]:
    rows = [
        {
            "rule_id": "R00",
            "status": "accepted",
            "action": "lock_raw_file",
            "affected": "raw csv",
            "count": "1",
            "detail": "SHA-256 of the raw file is checked before cleaning. The raw file is not opened for writing.",
        },
        {
            "rule_id": "R01",
            "status": "accepted",
            "action": "copy_source_cells",
            "affected": "all 167 source columns",
            "count": str(stats["n_rows"] * stats["n_source_columns"]),
            "detail": "Every source cell is copied as text. Numeric tokens, confidence-interval text, and FIPS codes keep their published characters.",
        },
        {
            "rule_id": "R02",
            "status": "accepted",
            "action": "retain_all_rows",
            "affected": "rows",
            "count": str(stats["n_rows"]),
            "detail": "No row is deleted. There were no exact duplicate records.",
        },
        {
            "rule_id": "R03",
            "status": "rejected",
            "action": "rename_FOODSTAMP_Crude95ci",
            "affected": "FOODSTAMP_Crude95ci",
            "count": "0",
            "detail": "The lowercase ci suffix is the published Socrata column name, including in the 2024 release. It is preserved.",
        },
        {
            "rule_id": "R04",
            "status": "accepted",
            "action": "no_imputation",
            "affected": "blank measure cells",
            "count": "0",
            "detail": "Blank cells stay blank. Kentucky, Pennsylvania, and health-related social needs gaps are structured nonresponse, not values to fill.",
        },
        {
            "rule_id": "R05",
            "status": "accepted",
            "action": "preserve_fips_text",
            "affected": "CountyFIPS",
            "count": str(stats["n_rows"]),
            "detail": "CountyFIPS stays a five-character string. Leading zeros are not stripped and codes are not padded or recalculated.",
        },
        {
            "rule_id": "R06",
            "status": "accepted_no_change",
            "action": "no_whitespace_normalisation",
            "affected": "text fields",
            "count": "0",
            "detail": "Profiling found no leading, trailing, or whitespace-only cells.",
        },
        {
            "rule_id": "R07",
            "status": "rejected",
            "action": "delete_or_winsorise_extremes",
            "affected": "prevalence and population",
            "count": "0",
            "detail": "Extreme counties such as Kalawao and Los Angeles are valid. No IQR or z-score deletion is applied.",
        },
        {
            "rule_id": "R08",
            "status": "rejected",
            "action": "deduplicate_by_county_name",
            "affected": "rows",
            "count": "0",
            "detail": "CountyName is not unique within Maryland, Missouri, or Virginia. CountyFIPS is the unique key. No rows are removed.",
        },
        {
            "rule_id": "R09",
            "status": "accepted",
            "action": "parse_confidence_intervals",
            "affected": "derived CI low and high columns",
            "count": str(stats["ci_cells_parsed"]),
            "detail": f"Parsed cells={stats['ci_cells_parsed']}; blank source intervals={stats['ci_cells_blank']}; failures={stats['ci_parse_failures']}. Source interval text is kept.",
        },
        {
            "rule_id": "R10",
            "status": "accepted",
            "action": "parse_geolocation_wkt",
            "affected": "derived longitude and latitude",
            "count": str(stats["geolocation_parsed"]),
            "detail": f"Parsed={stats['geolocation_parsed']}; blank={stats['geolocation_blank']}; failures={stats['geolocation_parse_failures']}.",
        },
        {
            "rule_id": "R11",
            "status": "accepted",
            "action": "add_source_row_number",
            "affected": "derived__source_row_number",
            "count": str(stats["n_rows"]),
            "detail": "Audit index back to the raw file. Not a CDC field and not a geographic key.",
        },
        {
            "rule_id": "R12",
            "status": "accepted",
            "action": "flag_short_name_collisions",
            "affected": "derived__short_name_collision",
            "count": str(stats["short_name_collision_rows"]),
            "detail": "Flag is computed from the file. It does not rewrite CountyName.",
        },
        {
            "rule_id": "R13",
            "status": "accepted",
            "action": "repair_dona_ana_display_name",
            "affected": "derived__CountyName_display",
            "count": str(stats["county_display_repairs"]),
            "detail": "Only CountyFIPS 35013 with the exact mojibake token is repaired, and only in the derived display column.",
        },
    ]
    for detail in stats["repair_details"]:
        rows.append(
            {
                "rule_id": "R13",
                "status": "accepted",
                "action": "cell_display_repair",
                "affected": f"row {detail['source_row_number']} FIPS {detail['CountyFIPS']}",
                "count": "1",
                "detail": f"source CountyName kept as {detail['original']!r}; derived display set to {detail['derived__CountyName_display']!r}",
            }
        )
    return rows


def require_raw_hash(raw_path: Path) -> str:
    expected = RAW_SHA_PATH.read_text(encoding="utf-8").strip()
    observed = sha256_file(raw_path)
    if observed != expected:
        raise SystemExit(
            f"Raw file hash {observed} does not match provenance hash {expected}. "
            "Refusing to clean. The raw file must be the preserved CDC download."
        )
    return observed


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def run(raw_path: Path, output_path: Path, run_dir: Path, write_log: bool = True) -> dict:
    raw_hash = require_raw_hash(raw_path)
    source_header, rows = read_raw_table(raw_path)
    cleaned_header, cleaned_rows, stats = clean_table(source_header, rows)
    if stats["source_cells_changed"] != 0:
        raise SystemExit("Internal error: a source cell was modified.")
    if stats["ci_parse_failures"] or stats["geolocation_parse_failures"] or stats["county_display_unresolved_non_ascii"]:
        raise SystemExit(f"Parsing failures prevent a silent clean: {stats}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output_path, cleaned_header, cleaned_rows)
    dictionary = field_dictionary(source_header, cleaned_header)
    dictionary_path = output_path.with_name("places_county_gis_2025_field_dictionary.csv")
    write_csv(
        dictionary_path,
        list(dictionary[0].keys()),
        dictionary,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    log_rows = transformation_log(stats)
    write_csv(run_dir / "04_transformation_log.csv", list(log_rows[0].keys()), log_rows)
    output_hash = sha256_file(output_path)
    summary = {
        "raw_path": _relative(raw_path),
        "raw_sha256": raw_hash,
        "cleaned_path": _relative(output_path),
        "cleaned_sha256": output_hash,
        "field_dictionary": _relative(dictionary_path),
        "stats": {key: value for key, value in stats.items() if key not in {"repair_details", "parse_failure_details"}},
        "repair_details": stats["repair_details"],
        "rules_accepted": ["R00", "R01", "R02", "R04", "R05", "R06", "R09", "R10", "R11", "R12", "R13"],
        "rules_rejected": ["R03", "R07", "R08"],
        "rows_excluded": 0,
        "columns_excluded": 0,
        "imputed_cells": 0,
    }
    # Prefer repo-relative paths even if parents differ in a test temp run.
    (run_dir / "04_transformation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if write_log:
        append_log(
        {
            "phase_id": "4",
            "action": "clean_places_county",
            "command": "python3 scripts/clean_places_county.py",
            "exit_status": 0,
            "inputs": [str(raw_path)],
            "outputs": [str(output_path), str(dictionary_path), str(run_dir / "04_transformation_log.csv")],
            "input_hashes": {"raw_csv": raw_hash},
            "output_hashes": {"cleaned_csv": output_hash},
            "counts": summary["stats"],
            "warnings": [],
            "errors": [],
            "decision": "Source cells copied unchanged. Derived columns added for CI bounds, centroid coordinates, row index, name collision, and one display-name repair.",
            "rationale": "Phase 3 rules R01 through R13. No imputation, deletion, or renaming.",
        }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the preserved PLACES county CSV.")
    parser.add_argument("--raw", type=Path, default=RAW_CSV)
    parser.add_argument("--output", type=Path, default=CLEAN_CSV)
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    args = parser.parse_args()
    summary = run(args.raw, args.output, args.run_dir)
    print(json.dumps(summary["stats"], indent=2))
    print("cleaned_sha256", summary["cleaned_sha256"])


if __name__ == "__main__":
    main()
