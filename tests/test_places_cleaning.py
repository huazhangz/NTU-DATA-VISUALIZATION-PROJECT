"""Focused tests for the PLACES county cleaning rules.

The suite rereads the preserved raw file. It does not treat a script exit
code as evidence that the data are clean.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from clean_places_county import MOJIBAKE_DONA_ANA, REPAIRED_DONA_ANA, clean_table, require_raw_hash
from places_common import CLEAN_CSV, RAW_CSV, read_raw_table, sha256_file, write_csv
from validate_places_county import run_checks


def test_validation_suite_has_no_failures():
    results = run_checks(RAW_CSV, CLEAN_CSV)
    failures = [row for row in results if row["status"] == "FAIL"]
    assert failures == []
    statuses = {row["status"] for row in results}
    assert "PASS" in statuses
    assert "NOT TESTED" in statuses


def test_cleaner_refuses_a_different_raw_file(tmp_path: Path):
    bogus = tmp_path / "not-the-cdc-file.csv"
    bogus.write_text("StateAbbr\nZZ\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        require_raw_hash(bogus)


def test_display_repair_does_not_guess_other_non_ascii_names():
    header = [
        "StateAbbr",
        "StateDesc",
        "CountyName",
        "CountyFIPS",
        "TotalPopulation",
        "TotalPop18plus",
        "ACCESS2_CrudePrev",
        "ACCESS2_Crude95CI",
        "Geolocation",
    ]
    rows = [
        {
            "StateAbbr": "NM",
            "StateDesc": "New Mexico",
            "CountyName": MOJIBAKE_DONA_ANA,
            "CountyFIPS": "35013",
            "TotalPopulation": "225210",
            "TotalPop18plus": "171000",
            "ACCESS2_CrudePrev": "12.3",
            "ACCESS2_Crude95CI": "( 10.1, 14.5)",
            "Geolocation": "POINT (-106.768 32.347)",
        },
        {
            "StateAbbr": "NM",
            "StateDesc": "New Mexico",
            "CountyName": "Caf\u00e9",
            "CountyFIPS": "35000",
            "TotalPopulation": "10",
            "TotalPop18plus": "9",
            "ACCESS2_CrudePrev": "",
            "ACCESS2_Crude95CI": "",
            "Geolocation": "POINT (-106.000 34.000)",
        },
        {
            "StateAbbr": "MD",
            "StateDesc": "Maryland",
            "CountyName": "Baltimore",
            "CountyFIPS": "24510",
            "TotalPopulation": "565239",
            "TotalPop18plus": "450000",
            "ACCESS2_CrudePrev": "8.0",
            "ACCESS2_Crude95CI": "( 7.0,  9.0)",
            "Geolocation": "POINT (-76.610 39.300)",
        },
        {
            "StateAbbr": "MD",
            "StateDesc": "Maryland",
            "CountyName": "Baltimore",
            "CountyFIPS": "24005",
            "TotalPopulation": "844703",
            "TotalPop18plus": "660000",
            "ACCESS2_CrudePrev": "6.0",
            "ACCESS2_Crude95CI": "(5.0, 7.0)",
            "Geolocation": "POINT (-76.610 39.400)",
        },
    ]
    _header, cleaned, stats = clean_table(header, rows)
    by_fips = {row["CountyFIPS"]: row for row in cleaned}
    assert by_fips["35013"]["CountyName"] == MOJIBAKE_DONA_ANA
    assert by_fips["35013"]["derived__CountyName_display"] == REPAIRED_DONA_ANA
    assert by_fips["35000"]["derived__CountyName_display"] == "Caf\u00e9"
    assert by_fips["35000"]["CountyName"] == "Caf\u00e9"
    assert by_fips["24510"]["derived__short_name_collision"] == "yes"
    assert by_fips["24005"]["derived__short_name_collision"] == "yes"
    assert by_fips["35013"]["derived__short_name_collision"] == "no"
    assert by_fips["35013"]["derived__ACCESS2_Crude95CI_Low"] == "10.1"
    assert by_fips["35013"]["derived__ACCESS2_Crude95CI_High"] == "14.5"
    assert by_fips["35000"]["derived__ACCESS2_Crude95CI_Low"] == ""
    assert stats["county_display_repairs"] == 1
    assert stats["source_cells_changed"] == 0
    assert stats["ci_parse_failures"] == 0


def test_repeat_clean_of_preserved_file_is_stable(tmp_path: Path):
    header, rows = read_raw_table(RAW_CSV)
    first_header, first_rows, _stats = clean_table(header, rows)
    second_header, second_rows, _stats = clean_table(header, rows)
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    write_csv(first_path, first_header, first_rows)
    write_csv(second_path, second_header, second_rows)
    assert sha256_file(first_path) == sha256_file(second_path)
    assert sha256_file(first_path) == sha256_file(CLEAN_CSV)
    assert first_header == second_header
