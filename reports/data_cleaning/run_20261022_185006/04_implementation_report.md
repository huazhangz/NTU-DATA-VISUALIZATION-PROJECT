# Phase 4 — Implementation

## Script

`scripts/clean_places_county.py`

```bash
PYTHONPATH=scripts python3 scripts/clean_places_county.py \
  --raw data/raw/places_county_gis_2025_i46a-9kgh.csv \
  --output data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv \
  --run-dir reports/data_cleaning/run_20261022_185006
```

Shared patterns and the state FIPS table are in `scripts/places_common.py`. The script refuses to run if the raw SHA-256 is not `a47cad3a852c5b35a031d548bc6dd4e9b5f7836bb7c851b84382160beafe15ef`.

## Method

1. Read the raw CSV as UTF-8 text with `csv.reader`. Empty fields stay empty strings.
2. Copy the 167 source fields in order.
3. Append derived fields from rules R09–R13. Interval and WKT parses use the regular expressions that had zero failures in the profile. Numeric pieces are the matched substrings, not reformatted floats.
4. Stop if any interval, centroid, or unexpected non-ASCII name fails. That did not happen.
5. Write the cleaned CSV with `\n` line endings and minimal quoting, plus the field dictionary.

The procedure reads only the raw file. A second run does not stack transformations. Pytest and validation check V20 both rebuild the file and compare SHA-256.

## Counts

| Item | Count |
| --- | ---: |
| Input rows | 3,143 |
| Input columns | 167 |
| Output rows | 3,143 |
| Output columns | 332 |
| Derived columns | 165 |
| Source cells changed | 0 |
| Rows excluded | 0 |
| Columns excluded | 0 |
| Imputed cells | 0 |
| Confidence intervals parsed | 229,152 |
| Confidence intervals left blank | 22,288 |
| Interval parse failures | 0 |
| Centroids parsed | 3,143 |
| Short-name collision rows | 12 |
| Display-name repairs | 1 (FIPS 35013, derived column only) |

Cleaned SHA-256: `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`

## Outputs

- `data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv`
- `data/processed/places_county_gis_2025_field_dictionary.csv`
- `04_transformation_log.csv`
- `04_transformation_summary.json`

Rejected rules R03, R07, and R08 are in the transformation log with count 0 so the decision not to rename, winsorise, or deduplicate is part of the run record.

## Techniques

- Hashing: SHA-256 of the file bytes.
- Parsing: Python `csv`, not pandas. This avoids integer coercion of FIPS codes.
- Interval and point parsing: one regular expression each, anchored, applied only after a full-file success count.
- Display repair: `str.encode("latin-1").decode("utf-8")` on one exact token, checked against `Do\u00f1a Ana` before it is written.
- Collision flag: a count of `(StateAbbr, CountyName)` in the file being cleaned, not a hard-coded list of six names. The validation then checks that the result is the known 12 FIPS codes.

No approach was abandoned after partially rewriting the data. The first sentinel scan was abandoned as a profiler heuristic because it flagged North Dakota. It never entered the cleaner.
