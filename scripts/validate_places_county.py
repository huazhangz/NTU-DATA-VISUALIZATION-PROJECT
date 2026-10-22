"""Independent checks of the cleaned PLACES county file against the raw source.

A zero exit from the cleaner is not treated as evidence. These checks reread
both files.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from clean_places_county import MOJIBAKE_DONA_ANA, REPAIRED_DONA_ANA, clean_table, derived_header
from places_common import (
    ANSI_STATE,
    CI_RE,
    CLEAN_CSV,
    EVEN_YEAR_MEASURES,
    GEOLOCATION_COLUMN,
    MEASURE_RE,
    POINT_RE,
    RAW_CSV,
    RAW_SHA_PATH,
    RUN_DIR,
    append_log,
    decimal_or_none,
    read_raw_table,
    sha256_file,
    write_csv,
)

HRSN_MEASURES = {
    "LONELINESS",
    "FOODSTAMP",
    "FOODINSECU",
    "HOUSINSECU",
    "SHUTUTILITY",
    "LACKTRPT",
    "EMOTIONSPT",
}
HRSN_BLANK_STATES = {"CO", "FL", "KY", "OR", "PA", "SD", "TN", "TX", "VT", "WA", "WY"}
COLLISION_FIPS = {"24510", "24005", "29189", "29510", "51600", "51059", "51620", "51067", "51760", "51159", "51770", "51161"}


def check(results: list[dict], test_id: str, status: str, validates: str, detail: str) -> None:
    results.append(
        {
            "test_id": test_id,
            "status": status,
            "validates": validates,
            "detail": detail,
        }
    )


def run_checks(raw_path: Path, cleaned_path: Path) -> list[dict]:
    results: list[dict] = []
    expected_hash = RAW_SHA_PATH.read_text(encoding="utf-8").strip()
    observed_hash = sha256_file(raw_path)
    check(
        results,
        "V01",
        "PASS" if observed_hash == expected_hash else "FAIL",
        "Preserved raw file is still the acquired CDC download.",
        f"observed={observed_hash}; expected={expected_hash}",
    )
    try:
        raw_header, raw_rows = read_raw_table(raw_path)
        cleaned_header, cleaned_rows = read_raw_table(cleaned_path)
        reopened = True
    except Exception as exc:
        check(results, "V02", "FAIL", "Cleaned CSV reopens with the same parser as the raw file.", str(exc))
        return results
    check(results, "V02", "PASS", "Cleaned CSV reopens with the csv module as UTF-8.", f"rows={len(cleaned_rows)}; columns={len(cleaned_header)}")

    check(
        results,
        "V03",
        "PASS" if len(cleaned_rows) == len(raw_rows) == 3143 else "FAIL",
        "Row count matches the raw file. 3143 is the observed count for this file, not a generic deletion rule.",
        f"raw={len(raw_rows)}; cleaned={len(cleaned_rows)}",
    )
    source_ok = cleaned_header[: len(raw_header)] == raw_header
    check(
        results,
        "V04",
        "PASS" if source_ok else "FAIL",
        "All 167 source columns are present, in the original order, including FOODSTAMP_Crude95ci.",
        f"source_columns={len(raw_header)}; foodstamp_name_preserved={'FOODSTAMP_Crude95ci' in cleaned_header}",
    )
    expected_derived = derived_header(raw_header)
    derived_ok = cleaned_header[len(raw_header) :] == expected_derived
    check(
        results,
        "V05",
        "PASS" if derived_ok else "FAIL",
        "Derived columns are exactly the documented set, after the source columns.",
        f"derived={len(cleaned_header) - len(raw_header)}; expected={len(expected_derived)}",
    )

    mismatches = 0
    first_mismatch = ""
    if source_ok and len(cleaned_rows) == len(raw_rows):
        for index, (raw, cleaned) in enumerate(zip(raw_rows, cleaned_rows), start=1):
            for column in raw_header:
                if cleaned[column] != raw[column]:
                    mismatches += 1
                    if not first_mismatch:
                        first_mismatch = f"row {index} {column}"
                    if mismatches >= 5:
                        break
            if mismatches >= 5:
                break
    check(
        results,
        "V06",
        "PASS" if mismatches == 0 and source_ok else "FAIL",
        "No source cell was changed, imputed, reformatted, or deleted.",
        f"mismatched_cells={mismatches}; first={first_mismatch or 'none'}",
    )

    fips_values = [row["CountyFIPS"] for row in cleaned_rows]
    fips_format_ok = all(re.fullmatch(r"\d{5}", value) for value in fips_values)
    fips_unique = len(set(fips_values)) == len(fips_values)
    leading = sum(value.startswith("0") for value in fips_values)
    check(
        results,
        "V07",
        "PASS" if fips_format_ok and fips_unique and leading == 318 else "FAIL",
        "CountyFIPS is a unique five-digit string and leading zeros are still present.",
        f"unique={len(set(fips_values))}; leading_zero_codes={leading}; format_ok={fips_format_ok}",
    )

    prefix_bad = 0
    name_bad = 0
    for row in cleaned_rows:
        reference = ANSI_STATE.get(row["StateAbbr"])
        if reference is None or not row["CountyFIPS"].startswith(reference[0]) or row["StateDesc"] != reference[1]:
            if reference is None or not row["CountyFIPS"].startswith(reference[0]):
                prefix_bad += 1
            if reference is None or row["StateDesc"] != reference[1]:
                name_bad += 1
    check(
        results,
        "V08",
        "PASS" if prefix_bad == 0 and name_bad == 0 else "FAIL",
        "State abbreviation, state name, and county FIPS prefix agree with Census ANSI state codes.",
        f"prefix_mismatches={prefix_bad}; name_mismatches={name_bad}; states={len({row['StateAbbr'] for row in cleaned_rows})}",
    )

    name_counts = Counter((row["StateAbbr"], row["CountyName"]) for row in cleaned_rows)
    flagged = {row["CountyFIPS"] for row in cleaned_rows if row["derived__short_name_collision"] == "yes"}
    expected_flagged = {row["CountyFIPS"] for row in cleaned_rows if name_counts[(row["StateAbbr"], row["CountyName"])] > 1}
    check(
        results,
        "V09",
        "PASS" if flagged == expected_flagged == COLLISION_FIPS else "FAIL",
        "Short-name collisions are flagged and not deleted. County name is not used as a key.",
        f"flagged={sorted(flagged)}; expected={sorted(expected_flagged)}",
    )
    check(
        results,
        "V10",
        "PASS" if len(fips_values) == len(set(fips_values)) else "FAIL",
        "CountyFIPS satisfies uniqueness. StateAbbr+CountyName does not, and that is expected.",
        f"CountyFIPS unique={fips_unique}; colliding_name_pairs={sum(1 for count in name_counts.values() if count > 1)}",
    )

    dona = [row for row in cleaned_rows if row["CountyFIPS"] == "35013"]
    dona_ok = (
        len(dona) == 1
        and dona[0]["CountyName"] == MOJIBAKE_DONA_ANA
        and dona[0]["derived__CountyName_display"] == REPAIRED_DONA_ANA
    )
    other_display = sum(
        1
        for row in cleaned_rows
        if row["CountyFIPS"] != "35013" and row["derived__CountyName_display"] != row["CountyName"]
    )
    check(
        results,
        "V11",
        "PASS" if dona_ok and other_display == 0 else "FAIL",
        "Only the Doña Ana display label is repaired, and the source CountyName remains the published token.",
        f"dona_ok={dona_ok}; other_display_changes={other_display}",
    )

    ci_fail = 0
    order_fail = 0
    outside = 0
    blank_mismatch = 0
    for row in cleaned_rows:
        for column in raw_header:
            match = MEASURE_RE.match(column)
            if not match:
                continue
            if match.group("stat") == "Prev":
                value = row[column]
                if value == "":
                    continue
                number = decimal_or_none(value)
                if number is None or number < 0 or number > 100:
                    outside += 1
                continue
            text = row[column]
            low = row[f"derived__{column}_Low"]
            high = row[f"derived__{column}_High"]
            if text == "":
                if low or high:
                    blank_mismatch += 1
                continue
            parsed = CI_RE.match(text)
            if not parsed or parsed.group(1) != low or parsed.group(2) != high:
                ci_fail += 1
                continue
            if Decimal(low) > Decimal(high):
                order_fail += 1
            estimate_column = f"{match.group('measure')}_{match.group('kind')}Prev"
            estimate = decimal_or_none(row[estimate_column])
            if estimate is not None and (estimate < Decimal(low) or estimate > Decimal(high)):
                outside += 1
    check(
        results,
        "V12",
        "PASS" if ci_fail == 0 and order_fail == 0 and blank_mismatch == 0 else "FAIL",
        "Parsed confidence limits equal the verified (low, high) text and stay blank when the source is blank.",
        f"parse_mismatches={ci_fail}; low_gt_high={order_fail}; blank_mismatches={blank_mismatch}",
    )
    check(
        results,
        "V13",
        "PASS" if outside == 0 else "FAIL",
        "Non-blank prevalence values are inside 0 to 100 and inside their published confidence interval.",
        f"violations={outside}",
    )

    pop_bad = 0
    for row in cleaned_rows:
        total = row["TotalPopulation"]
        adult = row["TotalPop18plus"]
        if not re.fullmatch(r"[1-9]\d*", total) or not re.fullmatch(r"[1-9]\d*", adult) or int(adult) > int(total):
            pop_bad += 1
    check(
        results,
        "V14",
        "PASS" if pop_bad == 0 else "FAIL",
        "Population fields are positive integer tokens and the adult count does not exceed the total count.",
        f"violations={pop_bad}",
    )

    geo_bad = 0
    for row in cleaned_rows:
        match = POINT_RE.match(row[GEOLOCATION_COLUMN])
        if not match or match.group(1) != row["derived__Geolocation_Longitude"] or match.group(2) != row["derived__Geolocation_Latitude"]:
            geo_bad += 1
            continue
        lon = Decimal(match.group(1))
        lat = Decimal(match.group(2))
        if not (Decimal("-180") <= lon <= Decimal("180") and Decimal("-90") <= lat <= Decimal("90")):
            geo_bad += 1
    check(
        results,
        "V15",
        "PASS" if geo_bad == 0 else "FAIL",
        "Every Geolocation WKT parses to the derived longitude and latitude and stays inside WGS84 degree limits.",
        f"violations={geo_bad}",
    )

    def states_all_blank(measure: str) -> set[str]:
        by_state = defaultdict(list)
        column = f"{measure}_CrudePrev"
        for row in cleaned_rows:
            by_state[row["StateAbbr"]].append(row[column] == "")
        return {state for state, flags in by_state.items() if all(flags)}

    access_blank = states_all_blank("ACCESS2")
    dental_blank = states_all_blank("DENTAL")
    hrsn_blank = states_all_blank("FOODSTAMP")
    hrsn_same = all(states_all_blank(measure) == HRSN_BLANK_STATES for measure in HRSN_MEASURES)
    year_2022_blank = {measure: states_all_blank(measure) for measure in EVEN_YEAR_MEASURES}
    check(
        results,
        "V16",
        "PASS" if access_blank == {"KY", "PA"} and dental_blank == set() and all(not value for value in year_2022_blank.values()) else "FAIL",
        "2023-description measures are blank for all Kentucky and Pennsylvania counties; the five 2022 measures are present in every state. Nothing was imputed.",
        f"ACCESS2_all_blank_states={sorted(access_blank)}; DENTAL_all_blank_states={sorted(dental_blank)}",
    )
    check(
        results,
        "V17",
        "PASS" if hrsn_blank == HRSN_BLANK_STATES and hrsn_same else "FAIL",
        "Health-related social needs are blank for the same 11 states and present for the other 39 states plus DC.",
        f"blank_states={sorted(hrsn_blank)}",
    )

    kalawao = [row for row in cleaned_rows if row["CountyFIPS"] == "15005"]
    kalawao_ok = len(kalawao) == 1 and kalawao[0]["TotalPop18plus"] == "75" and kalawao[0]["ACCESS2_CrudePrev"] != ""
    check(
        results,
        "V18",
        "PASS" if kalawao_ok else "FAIL",
        "Kalawao County is retained. Its adult population is 75, which is above the CDC reporting threshold of 50, and its estimates are present.",
        f"row={kalawao[0]['CountyName'] if kalawao else 'missing'}; adult={kalawao[0]['TotalPop18plus'] if kalawao else ''}",
    )

    row_numbers = [row["derived__source_row_number"] for row in cleaned_rows]
    check(
        results,
        "V19",
        "PASS" if row_numbers == [str(number) for number in range(1, len(cleaned_rows) + 1)] else "FAIL",
        "derived__source_row_number matches the raw row order and is not reused as a geographic identifier.",
        f"first={row_numbers[0] if row_numbers else ''}; last={row_numbers[-1] if row_numbers else ''}",
    )

    with tempfile.TemporaryDirectory() as tmp:
        header, rebuilt, _stats = clean_table(raw_header, raw_rows)
        tmp_path = Path(tmp) / "rebuilt.csv"
        write_csv(tmp_path, header, rebuilt)
        rebuilt_hash = sha256_file(tmp_path)
        cleaned_hash = sha256_file(cleaned_path)
    check(
        results,
        "V20",
        "PASS" if rebuilt_hash == cleaned_hash else "FAIL",
        "Re-running the cleaner on the same raw input reproduces the cleaned file byte for byte.",
        f"cleaned={cleaned_hash}; rebuilt={rebuilt_hash}",
    )
    check(
        results,
        "V21",
        "PASS" if sha256_file(raw_path) == expected_hash else "FAIL",
        "The raw hash is unchanged after cleaning and after the reproducibility rebuild.",
        expected_hash,
    )
    check(
        results,
        "V22",
        "NOT TESTED",
        "County short names were not matched to a Census county gazetteer.",
        "The 2023 national gazetteer URL returned HTTP 404 in this environment, so county legal-class suffixes were not added.",
    )
    check(
        results,
        "V23",
        "NOT TESTED",
        "Byte identity with the Windows file cited in the follow-up.",
        r"c:\Users\ASUS\Downloads\PLACES__County_Data__GIS_Friendly_Format___2025_release.csv was not present in the session.",
    )
    check(
        results,
        "V24",
        "NOT TESTED",
        "The CDC current-release-notes page naming Kentucky and Pennsylvania was not retrieved.",
        "data.cdc.gov metadata and the empirical blank pattern are tested. https://www.cdc.gov/places/current-release-notes/index.html returned HTTP 403 to the downloader and timed out in the page fetcher.",
    )
    check(
        results,
        "V25",
        "PASS" if "Counties" not in cleaned_header and ":@computed_region_skr5_azej" not in cleaned_header else "FAIL",
        "The Socrata computed region column was not in the CSV and was not invented.",
        "column absent from cleaned output",
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cleaned PLACES county data.")
    parser.add_argument("--raw", type=Path, default=RAW_CSV)
    parser.add_argument("--cleaned", type=Path, default=CLEAN_CSV)
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    args = parser.parse_args()
    results = run_checks(args.raw, args.cleaned)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.run_dir / "05_validation_results.csv", list(results[0].keys()), results)
    counts = Counter(row["status"] for row in results)
    payload = {"counts": dict(counts), "results": results}
    (args.run_dir / "05_validation_results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = counts.get("FAIL", 0)
    append_log(
        {
            "phase_id": "5",
            "action": "validate_cleaned_county_file",
            "command": "python3 scripts/validate_places_county.py",
            "exit_status": 0 if failed == 0 else 1,
            "inputs": [str(args.raw), str(args.cleaned)],
            "outputs": [str(args.run_dir / "05_validation_results.csv"), str(args.run_dir / "05_validation_results.json")],
            "input_hashes": {"raw_csv": sha256_file(args.raw), "cleaned_csv": sha256_file(args.cleaned)},
            "counts": dict(counts),
            "warnings": [row["test_id"] for row in results if row["status"] == "WARNING"],
            "errors": [row["test_id"] for row in results if row["status"] == "FAIL"],
            "decision": "Validation completed." if failed == 0 else "Validation found failures.",
            "rationale": "Checks reread the raw and cleaned files and rebuild the cleaned file for the hash comparison.",
        }
    )
    print(json.dumps(dict(counts), indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
