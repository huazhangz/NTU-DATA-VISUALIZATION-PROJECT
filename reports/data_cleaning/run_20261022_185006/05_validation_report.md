# Phase 5 — Validation

Validation rereads the raw and cleaned files. It does not trust the cleaner's exit status. The checker is `scripts/validate_places_county.py`. The same checks are imported by `tests/test_places_cleaning.py`.

```bash
PYTHONPATH=scripts python3 scripts/validate_places_county.py
PYTHONPATH=scripts python3 -m pytest tests/test_places_cleaning.py -q
```

Pytest result, saved in `05_pytest_log.txt`: **4 passed**.

Independent validation result after the resume check: **24 PASS, 0 FAIL, 1 WARNING, 1 NOT TESTED**. The first run, before the gazetteer and release notes were available, was 22 PASS, 0 FAIL, 0 WARNING, 3 NOT TESTED. That earlier result is preserved in the execution log.

## What passed

| Tests | What they establish |
| --- | --- |
| V01, V21 | Raw SHA-256 is still the download hash after cleaning and after a rebuild. |
| V02, V03 | The cleaned CSV reopens as UTF-8 and has the same 3,143 rows. |
| V04, V05, V06 | 167 source columns are in order, including `FOODSTAMP_Crude95ci`, and every source cell matches the raw file. |
| V07, V08 | FIPS codes are unique five-digit strings, 318 still start with zero, and state abbreviation, state name, and FIPS prefix agree with Census ANSI codes. |
| V09, V10 | The 12 short-name collisions are flagged and kept. `CountyFIPS` is unique. |
| V11 | Only FIPS 35013 has a repaired display name, and its source `CountyName` is still the published token. |
| V12, V13 | Parsed interval bounds match the source text, respect low ≤ high, and the percent estimates lie inside 0–100 and inside those bounds. |
| V14 | Population tokens are positive integers and the adult count does not exceed the total. |
| V15 | Every centroid parses to the derived coordinates inside WGS84 limits. |
| V16, V17 | Kentucky and Pennsylvania remain blank for 2023 measures and populated for 2022 measures. The seven HRSN measures remain blank for the same 11 states. This is a check that imputation did not happen. |
| V18 | Kalawao County is still present, with adult population 75 and a non-blank insurance estimate. |
| V19 | `derived__source_row_number` is 1 through 3,143 in raw order. |
| V20 | Rebuilding from the raw file reproduces the cleaned SHA-256 `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`. |
| V22 | Every county FIPS is in the Census 2023 gazetteer, and the short name matches that name except for the legal-class suffix. FIPS 35013 is the Doña Ana mojibake. |
| V24 | The saved CDC release-notes excerpt names the Kentucky and Pennsylvania 2023 gap. |
| V25 | The Socrata computed region column was not added. |

The pytest file adds three further checks: the suite has no failures, a different file is refused by the hash lock, and a synthetic non-ASCII name is not repaired by the Doña Ana rule. The fourth test repeats the byte-level rebuild.

## Warning and not tested

| Test | Status | Why |
| --- | --- | --- |
| V26 | WARNING | Loving County, Texas (FIPS 48301) is the only 50-state or DC county in the 2023 gazetteer that is absent from this file. The under-50-adults rule is a possible reason. A population table for that county was not loaded, so the cause is not treated as proven. |
| V23 | NOT TESTED | The Windows path cited in the follow-up was not in the session on the original run or the resume check. |

No validation failure occurred. The earlier profiler mistake (treating `ND` as a sentinel) is preserved in `02_anomalies_scan1_nd_false_positive.csv` and was never a cleaning rule. The resume check is `07_resume_reference_check.md`.

## Cleaned-file integrity

See `05_cleaned_integrity.json` for the cleaned path, row and column counts, and SHA-256.
