"""Shared constants and helpers for the PLACES county cleaning run.

The cleaning pipeline uses the Python standard library on purpose. Reading the
CDC export with pandas type inference would risk turning CountyFIPS into
integers and dropping leading zeros.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

# Verified against every non-blank confidence interval and geolocation in the
# preserved raw file: zero parse failures in run_20261022_185006.
CI_RE = re.compile(r"^\(\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*\)$")
POINT_RE = re.compile(r"^POINT\s+\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)$")
MEASURE_RE = re.compile(r"^(?P<measure>.+)_(?P<kind>Crude|Adj)(?P<stat>Prev|95CI|95ci)$")

SGT = ZoneInfo("Asia/Singapore")
RUN_ID = "run_20261022_185006"
DATASET_ID = "i46a-9kgh"
DATASET_NAME = "PLACES: County Data (GIS Friendly Format), 2025 release"

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "places_county_gis_2025_i46a-9kgh.csv"
COLUMNS_JSON = ROOT / "data" / "metadata" / "i46a-9kgh_columns.json"
VIEW_JSON = ROOT / "data" / "metadata" / "i46a-9kgh_view_metadata.json"
RAW_SHA_PATH = ROOT / "data" / "metadata" / "raw_sha256.txt"
RUN_DIR = ROOT / "reports" / "data_cleaning" / RUN_ID
CLEAN_CSV = ROOT / "data" / "processed" / "places_county_gis_2025_i46a-9kgh_cleaned.csv"
EXECUTION_LOG = RUN_DIR / "execution_log.jsonl"

# Census Bureau state and state-equivalent FIPS codes.
# Source: U.S. Census Bureau, American National Standards Institute (ANSI) codes,
# https://www.census.gov/library/reference/code-lists/ansi.html
# Transcribed for cross-field checks. This is a reference table, not CDC data.
ANSI_STATE = {
    "AL": ("01", "Alabama"),
    "AK": ("02", "Alaska"),
    "AZ": ("04", "Arizona"),
    "AR": ("05", "Arkansas"),
    "CA": ("06", "California"),
    "CO": ("08", "Colorado"),
    "CT": ("09", "Connecticut"),
    "DE": ("10", "Delaware"),
    "DC": ("11", "District of Columbia"),
    "FL": ("12", "Florida"),
    "GA": ("13", "Georgia"),
    "HI": ("15", "Hawaii"),
    "ID": ("16", "Idaho"),
    "IL": ("17", "Illinois"),
    "IN": ("18", "Indiana"),
    "IA": ("19", "Iowa"),
    "KS": ("20", "Kansas"),
    "KY": ("21", "Kentucky"),
    "LA": ("22", "Louisiana"),
    "ME": ("23", "Maine"),
    "MD": ("24", "Maryland"),
    "MA": ("25", "Massachusetts"),
    "MI": ("26", "Michigan"),
    "MN": ("27", "Minnesota"),
    "MS": ("28", "Mississippi"),
    "MO": ("29", "Missouri"),
    "MT": ("30", "Montana"),
    "NE": ("31", "Nebraska"),
    "NV": ("32", "Nevada"),
    "NH": ("33", "New Hampshire"),
    "NJ": ("34", "New Jersey"),
    "NM": ("35", "New Mexico"),
    "NY": ("36", "New York"),
    "NC": ("37", "North Carolina"),
    "ND": ("38", "North Dakota"),
    "OH": ("39", "Ohio"),
    "OK": ("40", "Oklahoma"),
    "OR": ("41", "Oregon"),
    "PA": ("42", "Pennsylvania"),
    "RI": ("44", "Rhode Island"),
    "SC": ("45", "South Carolina"),
    "SD": ("46", "South Dakota"),
    "TN": ("47", "Tennessee"),
    "TX": ("48", "Texas"),
    "UT": ("49", "Utah"),
    "VT": ("50", "Vermont"),
    "VA": ("51", "Virginia"),
    "WA": ("53", "Washington"),
    "WV": ("54", "West Virginia"),
    "WI": ("55", "Wisconsin"),
    "WY": ("56", "Wyoming"),
}

# Category crosswalk for the 40 PLACES 2025 measures.
# Category counts are from the CDC methodology page (12/7/4/7/3/7).
# Assignment of each prefix uses the official column description, not the abbreviation alone.
MEASURE_CATEGORY = {
    "ARTHRITIS": "health_outcome",
    "BPHIGH": "health_outcome",
    "CANCER": "health_outcome",
    "CASTHMA": "health_outcome",
    "CHD": "health_outcome",
    "COPD": "health_outcome",
    "DEPRESSION": "health_outcome",
    "DIABETES": "health_outcome",
    "HIGHCHOL": "health_outcome",
    "OBESITY": "health_outcome",
    "STROKE": "health_outcome",
    "TEETHLOST": "health_outcome",
    "ACCESS2": "prevention",
    "CHECKUP": "prevention",
    "CHOLSCREEN": "prevention",
    "COLON_SCREEN": "prevention",
    "DENTAL": "prevention",
    "BPMED": "prevention",
    "MAMMOUSE": "prevention",
    "BINGE": "health_risk_behavior",
    "CSMOKING": "health_risk_behavior",
    "LPA": "health_risk_behavior",
    "SLEEP": "health_risk_behavior",
    "HEARING": "disability",
    "VISION": "disability",
    "COGNITION": "disability",
    "MOBILITY": "disability",
    "SELFCARE": "disability",
    "INDEPLIVE": "disability",
    "DISABILITY": "disability",
    "GHLTH": "health_status",
    "MHLTH": "health_status",
    "PHLTH": "health_status",
    "LONELINESS": "health_related_social_need",
    "FOODSTAMP": "health_related_social_need",
    "FOODINSECU": "health_related_social_need",
    "HOUSINSECU": "health_related_social_need",
    "SHUTUTILITY": "health_related_social_need",
    "LACKTRPT": "health_related_social_need",
    "EMOTIONSPT": "health_related_social_need",
}

# Dataset description on the CDC view names these five as the 2022 BRFSS measures.
EVEN_YEAR_MEASURES = {"TEETHLOST", "DENTAL", "MAMMOUSE", "COLON_SCREEN", "SLEEP"}

IDENTIFIER_COLUMNS = ["StateAbbr", "StateDesc", "CountyName", "CountyFIPS"]
POPULATION_COLUMNS = ["TotalPopulation", "TotalPop18plus"]
GEOLOCATION_COLUMN = "Geolocation"

# "nd" is intentionally absent. A case-insensitive match treated the postal
# abbreviation ND (North Dakota) as a not-determined token. That first scan is
# preserved at 02_anomalies_scan1_nd_false_positive.csv.
SENTINEL_TOKENS = {
    "n/a",
    "na",
    "null",
    "none",
    "suppressed",
    "*",
    "-",
    ".",
    "missing",
    "masked",
}


def now_stamps() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "timestamp_utc": now.isoformat(),
        "timestamp_sgt": now.astimezone(SGT).isoformat(),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def append_log(entry: dict) -> None:
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = {**now_stamps(), "run_id": RUN_ID, **entry}
    with EXECUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def read_raw_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read the CDC CSV as text. Empty fields stay empty strings."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV has no header: {path}") from exc
        rows: list[dict[str, str]] = []
        for line_no, values in enumerate(reader, start=2):
            if len(values) != len(header):
                raise ValueError(
                    f"Ragged row at file line {line_no}: {len(values)} fields, expected {len(header)}"
                )
            rows.append(dict(zip(header, values)))
    return header, rows


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=header,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def write_dicts(path: Path, rows: list[dict], header: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if header:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
                writer.writeheader()
        else:
            path.write_text("", encoding="utf-8")
        return
    header = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def decimal_or_none(token: str) -> Decimal | None:
    text = token.strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def percentile_type7(sorted_values: list[Decimal], p: float) -> Decimal | None:
    """Hyndman-Fan type 7 quantile. Descriptive only; not a survey standard error."""
    n = len(sorted_values)
    if n == 0:
        return None
    if n == 1:
        return sorted_values[0]
    position = Decimal(1) + (Decimal(n) - 1) * Decimal(str(p))
    lower_index = int(position)
    fraction = position - Decimal(lower_index)
    left = sorted_values[lower_index - 1]
    if fraction == 0 or lower_index >= n:
        return left
    right = sorted_values[lower_index]
    return left + (right - left) * fraction


def population_stdev(values: list[Decimal]) -> Decimal | None:
    n = len(values)
    if n == 0:
        return None
    mean = sum(values, Decimal(0)) / Decimal(n)
    variance = sum((value - mean) ** 2 for value in values) / Decimal(n)
    return variance.sqrt()


def fmt_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
