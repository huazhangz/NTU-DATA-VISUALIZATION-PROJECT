# Handoff — CDC PLACES county GIS, 2025 release

Stop here. This handoff is for the next visualisation stage. Do not treat the cleaned file as a direct survey.

## How to rerun

From the repository root, with Python 3.12 and pytest:

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=scripts python3 scripts/profile_places_county.py
PYTHONPATH=scripts python3 scripts/clean_places_county.py
PYTHONPATH=scripts python3 scripts/validate_places_county.py
PYTHONPATH=scripts python3 -m pytest tests/test_places_cleaning.py -q
```

The cleaner reads `data/metadata/raw_sha256.txt` and exits if `data/raw/places_county_gis_2025_i46a-9kgh.csv` has changed. That is intentional. Profiling rewrites the Phase 1 and Phase 2 evidence files; do that only when you mean to refresh the audit.

The pipeline does not use pandas. Source fields stay text so county FIPS codes keep leading zeros.

## Where the files are

| Role | Path |
| --- | --- |
| Raw CDC CSV (do not edit) | `data/raw/places_county_gis_2025_i46a-9kgh.csv` |
| View metadata | `data/metadata/i46a-9kgh_view_metadata.json` |
| Column metadata | `data/metadata/i46a-9kgh_columns.json` |
| Cleaned table | `data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv` |
| Field dictionary | `data/processed/places_county_gis_2025_field_dictionary.csv` |
| State FIPS reference | `data/reference/ansi_state_fips.csv` |
| This run | `reports/data_cleaning/run_20261022_185006/` |
| Execution log | `reports/data_cleaning/run_20261022_185006/execution_log.jsonl` |

The log is append-only in the order each event was written. Profiling and cleaning were recorded before the Phase 0 and Phase 3 report files were flushed, so those phase numbers are not sorted. Each entry still names its phase.

Cleaned dimensions: 3,143 rows, 332 columns. Raw dimensions: 3,143 rows, 167 columns.

## What the next stage must respect

1. Join maps on `CountyFIPS`, not on `CountyName`. Twelve rows share a short name with another county-equivalent in the same state (`derived__short_name_collision` = `yes`). Connecticut codes are planning regions (`09110`–`09190`).
2. For labels, prefer `derived__CountyName_display`. It differs from `CountyName` only for Doña Ana.
3. Blank prevalence is unpublished, not zero. Leave Kentucky and Pennsylvania off 2023 measures. Leave these states off all seven health-related social needs measures: CO, FL, KY, OR, PA, SD, TN, TX, VT, WA, WY. The five 2022 measures (dental visit, mammography, colorectal screening, short sleep, all teeth lost) are present in every state, including Kentucky and Pennsylvania.
4. Plot crude and age-adjusted estimates as different series. Do not average them.
5. Draw uncertainty from `derived__*_Low` and `derived__*_High`. The source interval text is still in the `*95CI` columns, including `FOODSTAMP_Crude95ci`. Intervals are Monte Carlo percentiles from a small-area model, not design-based survey intervals.
6. Do not multiply a prevalence by `TotalPopulation` unless the denominator matches that measure's population. Prevalence is a percent. Census 2023 population is not the denominator for mammography, teeth lost, insurance, or blood-pressure medication.
7. Do not rank counties on a point estimate alone. CDC advises against using these modelled estimates as an overall health ranking.
8. Do not compare a 2022 measure with a 2023 measure as if they were the same year.
9. `derived__source_row_number` only locates the raw row.

## Unresolved items the next stage inherits

- The Windows download named in the follow-up was never hashed against this raw file.
- The CDC release-notes sentence on Kentucky and Pennsylvania was not retrieved. The blank pattern is still binding.
- A full Census name gazetteer was not attached, so legal-class suffixes were not added.

## Not in this task

No charts, dashboards, slides, or analytical narrative were built.
