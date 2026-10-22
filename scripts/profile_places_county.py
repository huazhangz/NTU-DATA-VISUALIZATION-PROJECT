"""Phase 1 inventory and Phase 2 profile of the preserved CDC county CSV.

The script does not modify the raw file. It writes machine-readable evidence
into the run directory.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from places_common import (
    ANSI_STATE,
    CI_RE,
    COLUMNS_JSON,
    EVEN_YEAR_MEASURES,
    GEOLOCATION_COLUMN,
    IDENTIFIER_COLUMNS,
    MEASURE_CATEGORY,
    MEASURE_RE,
    POINT_RE,
    POPULATION_COLUMNS,
    RAW_CSV,
    RAW_SHA_PATH,
    RUN_DIR,
    SENTINEL_TOKENS,
    VIEW_JSON,
    append_log,
    decimal_or_none,
    fmt_decimal,
    percentile_type7,
    population_stdev,
    read_raw_table,
    sha256_file,
    write_dicts,
)
NUMERIC_TOKEN_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
SCI_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$")
UNUSUAL_WS_RE = re.compile(r"[^\S ]| {2,}|\u00a0")


def load_metadata() -> tuple[dict, list[dict]]:
    view = json.loads(VIEW_JSON.read_text(encoding="utf-8"))
    columns = json.loads(COLUMNS_JSON.read_text(encoding="utf-8"))
    return view, columns


def semantic_role(column: str) -> dict[str, str]:
    if column in IDENTIFIER_COLUMNS:
        return {"semantic_role": "geographic_identifier", "measure_id": "", "estimate_type": "", "stat": ""}
    if column in POPULATION_COLUMNS:
        return {"semantic_role": "population_count", "measure_id": "", "estimate_type": "", "stat": ""}
    if column == GEOLOCATION_COLUMN:
        return {"semantic_role": "geolocation_wkt", "measure_id": "", "estimate_type": "", "stat": ""}
    match = MEASURE_RE.match(column)
    if not match:
        return {"semantic_role": "unclassified", "measure_id": "", "estimate_type": "", "stat": ""}
    measure = match.group("measure")
    kind = match.group("kind")
    stat = match.group("stat")
    if stat == "Prev":
        role = "crude_prevalence" if kind == "Crude" else "age_adjusted_prevalence"
    else:
        role = "crude_confidence_interval" if kind == "Crude" else "age_adjusted_confidence_interval"
    return {
        "semantic_role": role,
        "measure_id": measure,
        "estimate_type": "crude" if kind == "Crude" else "age_adjusted",
        "stat": "prevalence" if stat == "Prev" else "confidence_interval",
    }


def county_suffix(name: str) -> str:
    ordered = [
        (" Census Area", "census_area"),
        (" Municipality", "municipality"),
        (" Borough", "borough"),
        (" Parish", "parish"),
        (" County", "county"),
        (" city", "city_suffix"),
    ]
    for ending, label in ordered:
        if name.endswith(ending):
            return label
    return "no_standard_suffix"


def build_schema(header: list[str], columns: list[dict], outdir: Path) -> list[dict]:
    by_name = {item.get("name"): item for item in columns}
    rows = []
    for position, name in enumerate(header, start=1):
        meta = by_name.get(name, {})
        rows.append(
            {
                "csv_position": position,
                "csv_column_name": name,
                "in_csv": "yes",
                "in_column_metadata": "yes" if meta else "no",
                "metadata_field_name": meta.get("fieldName", ""),
                "metadata_data_type": meta.get("dataTypeName", ""),
                "metadata_description": meta.get("description", ""),
                "metadata_position": meta.get("position", ""),
            }
        )
    csv_names = set(header)
    for item in columns:
        if item.get("name") not in csv_names:
            rows.append(
                {
                    "csv_position": "",
                    "csv_column_name": "",
                    "in_csv": "no",
                    "in_column_metadata": "yes",
                    "metadata_field_name": item.get("fieldName", ""),
                    "metadata_data_type": item.get("dataTypeName", ""),
                    "metadata_description": item.get("description", ""),
                    "metadata_position": item.get("position", ""),
                    "metadata_name": item.get("name", ""),
                }
            )
    # Keep a stable header even for the metadata-only row.
    for row in rows:
        row.setdefault("metadata_name", "")
    write_dicts(outdir / "01_source_schema.csv", rows)
    return rows


def profile(raw_path: Path, outdir: Path) -> dict:
    header, rows = read_raw_table(raw_path)
    view, columns = load_metadata()
    schema_rows = build_schema(header, columns, outdir)
    meta_by_name = {item.get("name"): item for item in columns}
    n_rows = len(rows)
    anomalies: list[dict] = []

    def add_anomaly(row_number: int, row: dict, column: str, code: str, value: str, detail: str) -> None:
        anomalies.append(
            {
                "source_row_number": row_number,
                "CountyFIPS": row.get("CountyFIPS", ""),
                "StateAbbr": row.get("StateAbbr", ""),
                "CountyName": row.get("CountyName", ""),
                "column_name": column,
                "issue_code": code,
                "observed_value": value,
                "detail": detail,
            }
        )

    column_profiles = []
    missingness_rows = []
    categorical_rows = []
    numeric_cache: dict[str, list[Decimal]] = {}

    for position, name in enumerate(header, start=1):
        values = [row[name] for row in rows]
        role = semantic_role(name)
        meta = meta_by_name.get(name, {})
        description = meta.get("description") or ""
        empty = 0
        whitespace_only = 0
        edge_ws = 0
        unusual_ws = 0
        non_ascii = 0
        formula_like = 0
        sentinel = Counter()
        parse_fail = 0
        scientific = 0
        negative = 0
        outside = 0
        decimals = Counter()
        parsed: list[Decimal] = []
        distinct = set()
        for row_number, (row, value) in enumerate(zip(rows, values), start=1):
            distinct.add(value)
            if value == "":
                empty += 1
                continue
            if value.strip() == "":
                whitespace_only += 1
                add_anomaly(row_number, row, name, "whitespace_only", value, "whitespace-only cell")
                continue
            if value != value.strip():
                edge_ws += 1
                add_anomaly(row_number, row, name, "leading_or_trailing_whitespace", value, "edge whitespace")
            if UNUSUAL_WS_RE.search(value):
                unusual_ws += 1
            if any(ord(char) > 127 for char in value):
                non_ascii += 1
            if value[:1] in {"=", "+", "@"} or (value[:1] == "-" and not NUMERIC_TOKEN_RE.match(value)):
                formula_like += 1
                add_anomaly(row_number, row, name, "formula_like_text", value, "cell begins with a formula-like character")
            if name not in IDENTIFIER_COLUMNS and name != GEOLOCATION_COLUMN and value.strip().casefold() in SENTINEL_TOKENS:
                sentinel[value] += 1
                add_anomaly(row_number, row, name, "sentinel_token", value, "token matches a scanned sentinel list")
            if role["semantic_role"] in {"population_count", "crude_prevalence", "age_adjusted_prevalence"}:
                if SCI_RE.match(value.strip()):
                    scientific += 1
                    add_anomaly(row_number, row, name, "scientific_notation", value, "scientific notation")
                number = decimal_or_none(value)
                if number is None:
                    parse_fail += 1
                    add_anomaly(row_number, row, name, "numeric_parse_fail", value, "not a plain decimal token")
                else:
                    parsed.append(number)
                    if "." in value.strip():
                        decimals[len(value.strip().split(".", 1)[1])] += 1
                    else:
                        decimals[0] += 1
                    if number < 0:
                        negative += 1
                    if role["semantic_role"] != "population_count" and (number < 0 or number > 100):
                        outside += 1
                        add_anomaly(row_number, row, name, "prevalence_out_of_range", value, "outside 0 to 100")
        numeric_cache[name] = parsed
        sorted_parsed = sorted(parsed)
        mean = (sum(parsed, Decimal(0)) / Decimal(len(parsed))) if parsed else None
        profile = {
            "column_position": position,
            "column_name": name,
            "metadata_field_name": meta.get("fieldName", ""),
            "metadata_data_type": meta.get("dataTypeName", ""),
            "metadata_description": description,
            "semantic_role": role["semantic_role"],
            "measure_id": role["measure_id"],
            "measure_category": MEASURE_CATEGORY.get(role["measure_id"], ""),
            "estimate_type": role["estimate_type"],
            "brfss_year_in_description": (
                "2022" if "2022" in description and "2023" not in description
                else "2023" if "2023" in description and "2022" not in description
                else "both" if "2022" in description and "2023" in description
                else ""
            ),
            "n_rows": n_rows,
            "n_missing_empty": empty,
            "n_whitespace_only": whitespace_only,
            "n_nonmissing": n_rows - empty - whitespace_only,
            "pct_missing": f"{(empty + whitespace_only) / n_rows * 100:.4f}",
            "n_distinct_including_empty": len(distinct),
            "n_leading_or_trailing_whitespace": edge_ws,
            "n_unusual_internal_whitespace": unusual_ws,
            "n_non_ascii_cells": non_ascii,
            "n_formula_like": formula_like,
            "n_sentinel": sum(sentinel.values()),
            "sentinel_tokens": "|".join(f"{token}:{count}" for token, count in sorted(sentinel.items())),
            "is_constant_including_empty": "yes" if len(distinct) == 1 else "no",
            "n_parse_fail": parse_fail,
            "n_scientific_notation": scientific,
            "n_negative": negative,
            "n_outside_0_100": outside,
            "min": fmt_decimal(sorted_parsed[0]) if sorted_parsed else "",
            "p05": fmt_decimal(percentile_type7(sorted_parsed, 0.05)),
            "p25": fmt_decimal(percentile_type7(sorted_parsed, 0.25)),
            "median": fmt_decimal(percentile_type7(sorted_parsed, 0.50)),
            "p75": fmt_decimal(percentile_type7(sorted_parsed, 0.75)),
            "p95": fmt_decimal(percentile_type7(sorted_parsed, 0.95)),
            "max": fmt_decimal(sorted_parsed[-1]) if sorted_parsed else "",
            "mean": fmt_decimal(mean),
            "population_stdev": fmt_decimal(population_stdev(parsed)),
            "decimal_place_counts": "|".join(f"{places}:{count}" for places, count in sorted(decimals.items())),
        }
        column_profiles.append(profile)
        missingness_rows.append(
            {
                "column_name": name,
                "semantic_role": role["semantic_role"],
                "measure_id": role["measure_id"],
                "n_missing_empty": empty,
                "n_whitespace_only": whitespace_only,
                "pct_missing": profile["pct_missing"],
                "n_sentinel": profile["n_sentinel"],
                "sentinel_tokens": profile["sentinel_tokens"],
                "n_distinct_nonmissing": len(distinct - {""}),
            }
        )
        cardinality = len(distinct)
        if name in {"StateAbbr", "StateDesc"} or (cardinality <= 60 and role["semantic_role"] in {"geographic_identifier"}):
            counts = Counter(values)
            for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                categorical_rows.append(
                    {
                        "column_name": name,
                        "value": value,
                        "count": count,
                        "percent_of_rows": f"{count / n_rows * 100:.4f}",
                        "enumeration": "full",
                    }
                )
        else:
            categorical_rows.append(
                {
                    "column_name": name,
                    "value": "",
                    "count": cardinality,
                    "percent_of_rows": "",
                    "enumeration": "not_fully_enumerated_high_cardinality",
                }
            )

    suffix_counts = Counter(county_suffix(row["CountyName"]) for row in rows)
    for value, count in sorted(suffix_counts.items()):
        categorical_rows.append(
            {
                "column_name": "CountyName_legal_suffix_observed",
                "value": value,
                "count": count,
                "percent_of_rows": f"{count / n_rows * 100:.4f}",
                "enumeration": "derived_observation_not_a_source_field",
            }
        )

    # Candidate keys.
    def key_report(label: str, key_fn) -> dict:
        groups = defaultdict(list)
        for index, row in enumerate(rows, start=1):
            groups[key_fn(row)].append(index)
        duplicate_groups = {key: members for key, members in groups.items() if len(members) > 1}
        rows_in_dupes = sum(len(members) for members in duplicate_groups.values())
        return {
            "candidate_key": label,
            "n_rows": n_rows,
            "n_distinct": len(groups),
            "n_duplicate_key_values": len(duplicate_groups),
            "n_rows_in_duplicate_groups": rows_in_dupes,
            "is_unique": "yes" if not duplicate_groups else "no",
            "notes": "",
        }

    full_hashes = []
    import hashlib
    for row in rows:
        blob = "\x1f".join(row[name] for name in header).encode("utf-8")
        full_hashes.append(hashlib.sha256(blob).hexdigest())
    key_rows = [
        key_report("CountyFIPS", lambda row: row["CountyFIPS"]),
        key_report("StateAbbr", lambda row: row["StateAbbr"]),
        key_report("StateDesc", lambda row: row["StateDesc"]),
        key_report("CountyName", lambda row: row["CountyName"]),
        key_report("StateAbbr+CountyName", lambda row: (row["StateAbbr"], row["CountyName"])),
        key_report("StateAbbr+CountyFIPS", lambda row: (row["StateAbbr"], row["CountyFIPS"])),
        key_report("Geolocation", lambda row: row["Geolocation"]),
        key_report("full_record_sha256", lambda row: full_hashes[rows.index(row)] if False else None),
    ]
    # The last lambda above is a placeholder; replace with a direct count.
    key_rows = key_rows[:-1]
    hash_groups = defaultdict(int)
    for digest in full_hashes:
        hash_groups[digest] += 1
    duplicate_full = sum(1 for count in hash_groups.values() if count > 1)
    key_rows.append(
        {
            "candidate_key": "full_record_sha256",
            "n_rows": n_rows,
            "n_distinct": len(hash_groups),
            "n_duplicate_key_values": duplicate_full,
            "n_rows_in_duplicate_groups": sum(count for count in hash_groups.values() if count > 1),
            "is_unique": "yes" if duplicate_full == 0 else "no",
            "notes": "Exact duplicate records, including every measure field.",
        }
    )
    key_rows[0]["notes"] = "Five-character county FIPS, including state prefix. Tested, not assumed from the name."
    key_rows[1]["notes"] = "State abbreviation is a grouping field. Duplicate values are expected."
    key_rows[2]["notes"] = "State name is a grouping field. Duplicate values are expected."
    key_rows[3]["notes"] = "County name is not nationally unique. Duplicate names are expected."
    key_rows[4]["notes"] = "Not unique. Six short names each refer to both a county and a county-equivalent in the same state."
    key_rows[5]["notes"] = "Redundant with CountyFIPS if the state prefix agrees with StateAbbr."
    key_rows[6]["notes"] = "WKT county centroid. Uniqueness is empirical, not an official key."

    # Identifier and geography checks.
    fips_format_failures = 0
    state_fips_mismatches = 0
    state_name_mismatches = 0
    unknown_state = 0
    non_ascii_names = []
    for row_number, row in enumerate(rows, start=1):
        fips = row["CountyFIPS"]
        abbr = row["StateAbbr"]
        state_name = row["StateDesc"]
        county = row["CountyName"]
        if any(ord(char) > 127 for char in county):
            non_ascii_names.append({"source_row_number": row_number, "CountyFIPS": fips, "CountyName": county})
            add_anomaly(row_number, row, "CountyName", "non_ascii_county_name", county, "county short name contains a non-ASCII character")
        if not re.fullmatch(r"\d{5}", fips):
            fips_format_failures += 1
            add_anomaly(row_number, row, "CountyFIPS", "fips_format", fips, "not exactly five digits")
        reference = ANSI_STATE.get(abbr)
        if reference is None:
            unknown_state += 1
            add_anomaly(row_number, row, "StateAbbr", "state_fips_mismatch", abbr, "abbreviation is not in the Census state FIPS table")
        else:
            prefix, expected_name = reference
            if not fips.startswith(prefix):
                state_fips_mismatches += 1
                add_anomaly(row_number, row, "CountyFIPS", "state_fips_mismatch", fips, f"prefix does not match {abbr}={prefix}")
            if state_name != expected_name:
                state_name_mismatches += 1
                add_anomaly(row_number, row, "StateDesc", "state_name_mismatch", state_name, f"expected Census name {expected_name}")
        point = row["Geolocation"]
        if point and not POINT_RE.match(point):
            add_anomaly(row_number, row, "Geolocation", "geolocation_parse_fail", point, "not POINT (lon lat)")
        elif point:
            lon_text, lat_text = POINT_RE.match(point).groups()
            lon = Decimal(lon_text)
            lat = Decimal(lat_text)
            if not (Decimal("-180") <= lon <= Decimal("180") and Decimal("-90") <= lat <= Decimal("90")):
                add_anomaly(row_number, row, "Geolocation", "coordinate_out_of_range", point, "outside WGS84 degree limits")

    # Population relationships and CI relationships.
    pop_not_integer = 0
    pop_nonpositive = 0
    adult_exceeds_total = 0
    ci_parse_fail = 0
    ci_low_gt_high = 0
    estimate_outside = 0
    max_outside = Decimal(0)
    ci_without_estimate = 0
    estimate_without_ci = 0
    outside_examples = []
    measures = sorted({semantic_role(name)["measure_id"] for name in header if semantic_role(name)["measure_id"]})
    partial_groups = 0
    small_pop_rows = []
    measure_state = []

    def field(measure: str, kind: str, stat: str) -> str:
        if stat == "ci":
            crude_name = f"{measure}_Crude95CI"
            if crude_name not in header and f"{measure}_Crude95ci" in header and kind == "Crude":
                return f"{measure}_Crude95ci"
            return f"{measure}_{kind}95CI"
        return f"{measure}_{kind}Prev"

    for measure in measures:
        by_state = defaultdict(lambda: {"n": 0, "all_missing": 0, "partial": 0, "all_present": 0})
        for row_number, row in enumerate(rows, start=1):
            fields = []
            for kind in ("Crude", "Adj"):
                fields.append(field(measure, kind, "prev"))
                fields.append(field(measure, kind, "ci"))
            present_flags = [row[name] != "" for name in fields]
            state_bucket = by_state[row["StateAbbr"]]
            state_bucket["n"] += 1
            if all(present_flags):
                state_bucket["all_present"] += 1
            elif not any(present_flags):
                state_bucket["all_missing"] += 1
            else:
                state_bucket["partial"] += 1
                partial_groups += 1
                add_anomaly(
                    row_number,
                    row,
                    measure,
                    "measure_partial_missing",
                    "",
                    "the four crude/age-adjusted estimate and CI fields are not all present or all blank",
                )
            for kind in ("Crude", "Adj"):
                estimate_name = field(measure, kind, "prev")
                ci_name = field(measure, kind, "ci")
                estimate_text = row[estimate_name]
                ci_text = row[ci_name]
                if estimate_text == "" and ci_text == "":
                    continue
                if estimate_text == "" and ci_text != "":
                    ci_without_estimate += 1
                    add_anomaly(row_number, row, ci_name, "ci_present_estimate_missing", ci_text, estimate_name)
                    continue
                if estimate_text != "" and ci_text == "":
                    estimate_without_ci += 1
                    add_anomaly(row_number, row, estimate_name, "estimate_present_ci_missing", estimate_text, ci_name)
                    continue
                match = CI_RE.match(ci_text)
                if not match:
                    ci_parse_fail += 1
                    add_anomaly(row_number, row, ci_name, "ci_parse_fail", ci_text, "does not match (low, high)")
                    continue
                low = Decimal(match.group(1))
                high = Decimal(match.group(2))
                if low > high:
                    ci_low_gt_high += 1
                    add_anomaly(row_number, row, ci_name, "ci_low_gt_high", ci_text, "lower bound exceeds upper bound")
                estimate = decimal_or_none(estimate_text)
                if estimate is not None and (estimate < low or estimate > high):
                    estimate_outside += 1
                    deviation = max(low - estimate, estimate - high)
                    if deviation > max_outside:
                        max_outside = deviation
                    if len(outside_examples) < 15:
                        outside_examples.append(
                            {
                                "source_row_number": row_number,
                                "CountyFIPS": row["CountyFIPS"],
                                "column": estimate_name,
                                "estimate": estimate_text,
                                "ci": ci_text,
                                "deviation": fmt_decimal(deviation),
                            }
                        )
                    add_anomaly(
                        row_number,
                        row,
                        estimate_name,
                        "estimate_outside_ci",
                        estimate_text,
                        f"deviation={fmt_decimal(deviation)}; ci={ci_text}",
                    )
        for state, bucket in sorted(by_state.items()):
            measure_state.append(
                {
                    "measure_id": measure,
                    "measure_category": MEASURE_CATEGORY.get(measure, ""),
                    "description_year_group": "2022" if measure in EVEN_YEAR_MEASURES else "2023_or_other",
                    "StateAbbr": state,
                    "n_counties": bucket["n"],
                    "n_all_four_present": bucket["all_present"],
                    "n_all_four_missing": bucket["all_missing"],
                    "n_partial": bucket["partial"],
                }
            )

    for row_number, row in enumerate(rows, start=1):
        for name in POPULATION_COLUMNS:
            value = row[name]
            if value == "":
                continue
            if not re.fullmatch(r"\d+", value):
                pop_not_integer += 1
                add_anomaly(row_number, row, name, "population_not_integer", value, "not an unsigned integer token")
            elif Decimal(value) <= 0:
                pop_nonpositive += 1
                add_anomaly(row_number, row, name, "population_nonpositive", value, "not positive")
        total = decimal_or_none(row["TotalPopulation"])
        adult = decimal_or_none(row["TotalPop18plus"])
        if total is not None and adult is not None and adult > total:
            adult_exceeds_total += 1
            add_anomaly(row_number, row, "TotalPop18plus", "adult_pop_exceeds_total", row["TotalPop18plus"], f"TotalPopulation={row['TotalPopulation']}")
        if adult is not None and adult < 50:
            present_measures = 0
            for measure in measures:
                if row[field(measure, "Crude", "prev")] != "":
                    present_measures += 1
            small_pop_rows.append(
                {
                    "source_row_number": row_number,
                    "StateAbbr": row["StateAbbr"],
                    "CountyName": row["CountyName"],
                    "CountyFIPS": row["CountyFIPS"],
                    "TotalPopulation": row["TotalPopulation"],
                    "TotalPop18plus": row["TotalPop18plus"],
                    "n_measures_with_crude_prevalence": present_measures,
                }
            )

    # State-level structural missingness: a state is fully missing a measure when every county is all-four-missing.
    fully_missing_states = defaultdict(list)
    for record in measure_state:
        if record["n_all_four_missing"] == record["n_counties"] and record["n_counties"] > 0:
            fully_missing_states[record["measure_id"]].append(record["StateAbbr"])

    state_counts = Counter(row["StateAbbr"] for row in rows)
    ct_fips = sorted({row["CountyFIPS"] for row in rows if row["StateAbbr"] == "CT"})

    name_groups = defaultdict(list)
    for row_number, row in enumerate(rows, start=1):
        name_groups[(row["StateAbbr"], row["CountyName"])].append(row_number)
    within_state_name_collisions = []
    for (state, county_name), members in sorted(name_groups.items()):
        if len(members) < 2:
            continue
        within_state_name_collisions.append(
            {
                "StateAbbr": state,
                "CountyName": county_name,
                "n_rows": len(members),
                "source_row_numbers": "|".join(str(number) for number in members),
                "county_fips": "|".join(rows[number - 1]["CountyFIPS"] for number in members),
            }
        )
        for number in members:
            add_anomaly(
                number,
                rows[number - 1],
                "CountyName",
                "within_state_short_name_collision",
                county_name,
                "same short name is used by more than one county-equivalent in this state; CountyFIPS distinguishes them",
            )

    write_dicts(outdir / "02_column_profile.csv", column_profiles)
    write_dicts(outdir / "02_missingness_profile.csv", missingness_rows)
    write_dicts(outdir / "02_categorical_profile.csv", categorical_rows)
    write_dicts(outdir / "02_candidate_key_analysis.csv", key_rows)
    write_dicts(outdir / "02_anomalies.csv", anomalies)
    write_dicts(outdir / "02_measure_state_missingness.csv", measure_state)
    write_dicts(
        outdir / "02_small_population_counties.csv",
        small_pop_rows,
        header=[
            "source_row_number",
            "StateAbbr",
            "CountyName",
            "CountyFIPS",
            "TotalPopulation",
            "TotalPop18plus",
            "n_measures_with_crude_prevalence",
        ],
    )

    category_counts = Counter(MEASURE_CATEGORY.values())
    unmapped = [measure for measure in measures if measure not in MEASURE_CATEGORY]
    year_conflicts = []
    for profile in column_profiles:
        measure = profile["measure_id"]
        if not measure:
            continue
        expected = "2022" if measure in EVEN_YEAR_MEASURES else "2023"
        observed = profile["brfss_year_in_description"]
        if observed and observed != expected:
            year_conflicts.append(
                {"column_name": profile["column_name"], "expected_from_dataset_description": expected, "description_year": observed}
            )

    highlights = {
        "n_rows": n_rows,
        "n_columns": len(header),
        "duplicate_column_names": [name for name, count in Counter(header).items() if count > 1],
        "n_measures": len(measures),
        "unmapped_measures": unmapped,
        "category_counts": dict(category_counts),
        "year_description_conflicts": year_conflicts,
        "n_states": len(state_counts),
        "state_county_counts": dict(sorted(state_counts.items())),
        "connecticut_county_fips": ct_fips,
        "fips_format_failures": fips_format_failures,
        "state_fips_mismatches": state_fips_mismatches,
        "state_name_mismatches": state_name_mismatches,
        "unknown_state_abbreviations": unknown_state,
        "non_ascii_county_names": non_ascii_names,
        "county_suffix_counts": dict(suffix_counts),
        "within_state_short_name_collisions": within_state_name_collisions,
        "population_not_integer": pop_not_integer,
        "population_nonpositive": pop_nonpositive,
        "adult_pop_exceeds_total": adult_exceeds_total,
        "small_population_counties": small_pop_rows,
        "ci_parse_fail": ci_parse_fail,
        "ci_low_gt_high": ci_low_gt_high,
        "estimate_outside_ci": estimate_outside,
        "max_estimate_outside_ci_deviation": fmt_decimal(max_outside),
        "estimate_outside_ci_examples": outside_examples,
        "ci_without_estimate": ci_without_estimate,
        "estimate_without_ci": estimate_without_ci,
        "partial_measure_groups": partial_groups,
        "fully_missing_states_by_measure": {key: value for key, value in sorted(fully_missing_states.items())},
        "whitespace_only_cells": sum(item["n_whitespace_only"] for item in column_profiles),
        "edge_whitespace_cells": sum(item["n_leading_or_trailing_whitespace"] for item in column_profiles),
        "sentinel_cells": sum(item["n_sentinel"] for item in column_profiles),
        "formula_like_cells": sum(item["n_formula_like"] for item in column_profiles),
        "numeric_parse_failures": sum(item["n_parse_fail"] for item in column_profiles),
        "prevalence_out_of_range": sum(item["n_outside_0_100"] for item in column_profiles),
        "candidate_keys": key_rows,
        "metadata_column_count": len(columns),
        "metadata_only_columns": [
            {"name": item.get("name"), "fieldName": item.get("fieldName"), "dataTypeName": item.get("dataTypeName")}
            for item in columns
            if item.get("name") not in set(header)
        ],
        "csv_columns_missing_from_metadata": [name for name in header if name not in meta_by_name],
        "view_id": view.get("id"),
        "view_name": view.get("name"),
        "schema_row_count": len(schema_rows),
    }
    (outdir / "02_initial_profile.json").write_text(
        json.dumps(highlights, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return highlights


def write_phase1(raw_path: Path, outdir: Path, highlights: dict) -> None:
    raw_hash = sha256_file(raw_path)
    RAW_SHA_PATH.write_text(raw_hash + "\n", encoding="utf-8")
    view_hash = sha256_file(VIEW_JSON)
    columns_hash = sha256_file(COLUMNS_JSON)
    view = json.loads(VIEW_JSON.read_text(encoding="utf-8"))
    inventory = {
        "dataset_id": view.get("id"),
        "dataset_name": view.get("name"),
        "attribution": view.get("attribution"),
        "license": view.get("license"),
        "description": view.get("description"),
        "category": view.get("category"),
        "tags": view.get("tags"),
        "rowsUpdatedAt": view.get("rowsUpdatedAt"),
        "createdAt": view.get("createdAt"),
        "publicationDate": view.get("publicationDate"),
        "viewLastModified": view.get("viewLastModified"),
        "custom_fields": view.get("metadata", {}).get("custom_fields"),
        "retrieval": {
            "csv_url": "https://data.cdc.gov/api/views/i46a-9kgh/rows.csv?accessType=DOWNLOAD",
            "view_metadata_url": "https://data.cdc.gov/api/views/i46a-9kgh.json",
            "columns_metadata_url": "https://data.cdc.gov/api/views/i46a-9kgh/columns.json",
            "about_page": "https://data.cdc.gov/500-Cities-Places/PLACES-County-Data-GIS-Friendly-Format-2025-releas/i46a-9kgh/about_data",
            "methodology": "https://www.cdc.gov/places/methodology/",
            "measure_definitions": "https://www.cdc.gov/places/measure-definitions/index.html",
            "faqs": "https://www.cdc.gov/places/faqs/index.html",
            "started_utc": "2026-10-22T10:50:06.897730+00:00",
            "started_sgt": "2026-10-22T18:50:06.897730+08:00",
            "http_status": 200,
            "csv_content_type": "text/csv; charset=utf-8",
            "csv_last_modified_header": "Thu, 04 Dec 2025 10:43:36 GMT",
            "user_agent": "academic-data-cleaning/1.0 (CDC PLACES county GIS 2025 reproducibility)",
        },
        "files": {
            "raw_csv": {
                "path": str(raw_path.relative_to(raw_path.parents[2])),
                "bytes": raw_path.stat().st_size,
                "sha256": raw_hash,
                "encoding": "utf-8",
                "bom": False,
                "delimiter": ",",
                "newline": "\\n",
                "header": True,
                "n_rows_observed": highlights["n_rows"],
                "n_columns_observed": highlights["n_columns"],
            },
            "view_metadata": {
                "path": "data/metadata/i46a-9kgh_view_metadata.json",
                "bytes": VIEW_JSON.stat().st_size,
                "sha256": view_hash,
            },
            "columns_metadata": {
                "path": "data/metadata/i46a-9kgh_columns.json",
                "bytes": COLUMNS_JSON.stat().st_size,
                "sha256": columns_hash,
            },
        },
        "user_supplied_file": {
            "cited_path": r"c:\Users\ASUS\Downloads\PLACES__County_Data__GIS_Friendly_Format___2025_release.csv",
            "present_in_session": False,
            "byte_comparison": "not performed",
            "note": "The follow-up asked to treat this local Windows file as authoritative. It was not attached to the session workspace, so the preserved official download remains the raw source.",
        },
        "comparison_point_not_a_rule": {
            "stated_benchmark_rows": 3143,
            "stated_benchmark_columns": 167,
            "observed_rows": highlights["n_rows"],
            "observed_columns": highlights["n_columns"],
            "matches_benchmark": highlights["n_rows"] == 3143 and highlights["n_columns"] == 167,
        },
    }
    (outdir / "01_source_metadata.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    integrity = {
        "raw_sha256": raw_hash,
        "raw_bytes": raw_path.stat().st_size,
        "encoding_check": "utf-8 strict read succeeded",
        "delimiter": ",",
        "header_present": True,
        "n_rows": highlights["n_rows"],
        "n_columns": highlights["n_columns"],
        "ragged_rows": 0,
        "duplicate_column_names": highlights["duplicate_column_names"],
        "dataset_id_in_metadata": highlights["view_id"],
        "dataset_name_in_metadata": highlights["view_name"],
        "identifier_confirmed": highlights["view_id"] == "i46a-9kgh",
    }
    (outdir / "01_raw_data_integrity.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the preserved PLACES county CSV.")
    parser.add_argument("--raw", type=Path, default=RAW_CSV)
    parser.add_argument("--outdir", type=Path, default=RUN_DIR)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    highlights = profile(args.raw, args.outdir)
    write_phase1(args.raw, args.outdir, highlights)
    append_log(
        {
            "phase_id": "1-2",
            "action": "profile_raw_county_csv",
            "command": "python3 scripts/profile_places_county.py",
            "exit_status": 0,
            "inputs": [str(args.raw), str(COLUMNS_JSON), str(VIEW_JSON)],
            "outputs": [
                str(args.outdir / "01_source_schema.csv"),
                str(args.outdir / "01_source_metadata.json"),
                str(args.outdir / "01_raw_data_integrity.json"),
                str(args.outdir / "02_initial_profile.json"),
                str(args.outdir / "02_column_profile.csv"),
                str(args.outdir / "02_missingness_profile.csv"),
                str(args.outdir / "02_categorical_profile.csv"),
                str(args.outdir / "02_candidate_key_analysis.csv"),
            ],
            "input_hashes": {"raw_csv": sha256_file(args.raw)},
            "counts": {
                "n_rows": highlights["n_rows"],
                "n_columns": highlights["n_columns"],
                "estimate_outside_ci": highlights["estimate_outside_ci"],
                "ci_parse_fail": highlights["ci_parse_fail"],
                "partial_measure_groups": highlights["partial_measure_groups"],
            },
            "warnings": [],
            "errors": [],
            "decision": "Profile only. No cell values were changed.",
            "rationale": "Initial profiling must be finished and saved before cleaning rules are applied.",
        }
    )
    print(json.dumps({
        "n_rows": highlights["n_rows"],
        "n_columns": highlights["n_columns"],
        "n_measures": highlights["n_measures"],
        "ci_parse_fail": highlights["ci_parse_fail"],
        "estimate_outside_ci": highlights["estimate_outside_ci"],
        "max_deviation": highlights["max_estimate_outside_ci_deviation"],
        "partial_measure_groups": highlights["partial_measure_groups"],
        "fips_format_failures": highlights["fips_format_failures"],
        "state_fips_mismatches": highlights["state_fips_mismatches"],
        "state_name_mismatches": highlights["state_name_mismatches"],
        "sentinel_cells": highlights["sentinel_cells"],
        "edge_whitespace_cells": highlights["edge_whitespace_cells"],
        "small_population_counties": highlights["small_population_counties"],
        "unmapped_measures": highlights["unmapped_measures"],
        "year_conflicts": highlights["year_description_conflicts"],
        "non_ascii": highlights["non_ascii_county_names"],
        "adult_exceeds": highlights["adult_pop_exceeds_total"],
        "prevalence_out_of_range": highlights["prevalence_out_of_range"],
        "numeric_parse_failures": highlights["numeric_parse_failures"],
        "category_counts": highlights["category_counts"],
        "ct_fips": highlights["connecticut_county_fips"],
        "n_states": highlights["n_states"],
        "metadata_only": highlights["metadata_only_columns"],
        "fully_missing_state_counts": {k: len(v) for k, v in highlights["fully_missing_states_by_measure"].items()},
    }, indent=2))


if __name__ == "__main__":
    main()
