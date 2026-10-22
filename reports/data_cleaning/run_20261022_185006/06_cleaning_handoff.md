# Handoff — CDC PLACES county GIS, 2025 release

Cleaning is closed. The next stage is Data Visualization preparation, then charts. Do not treat the cleaned file as a direct survey. Do not rerun cleaning or add cross-checks for the items closed below.

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

## Closed / Accepted

These three items are closed because the project scope does not require more investigation. The underlying validation words are unchanged.

| Item | Record that still stands | Decision |
| --- | --- | --- |
| HRSN blanks in 11 states (Q03) | V17 lists CO, FL, KY, OR, PA, SD, TN, TX, VT, WA, WY. The saved release notes do not name those states one by one. | Closed / Accepted. Do not search for an official name list. Leave the seven HRSN measures unpublished in those states. Do not draw the blanks as zero. |
| Loving County missing cause (Q08, V26 WARNING) | FIPS `48301` is absent. No population table was checked. | Closed / Accepted. The cause is still unknown. Do not add a row. Do not change V26 from WARNING to PASS. |
| V23 | `05_validation_results.csv` still says NOT TESTED. | Closed / Accepted. Do not run another byte comparison. Do not rewrite V23 as PASS. |

Kentucky and Pennsylvania remain a data rule, not an open investigation: 2023 measures are unpublished there, and the five 2022 measures are present. The catalog `Issued` date of 7/27/2023 is still only a labeling caveat. Do not call the estimates a July 2023 release.

## Visualization preparation

Use `data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv` and `data/processed/places_county_gis_2025_field_dictionary.csv`. The dictionary has 332 field rows. Forty measures each have crude prevalence, crude interval, age-adjusted prevalence, and age-adjusted interval.

Map key: `CountyFIPS`. Labels: `derived__CountyName_display`. Uncertainty: `derived__*_Low` and `derived__*_High` (160 columns). Source interval text remains in the 80 `*95CI` / `*95ci` columns.

A first map can use `OBESITY_AdjPrev` or `DIABETES_AdjPrev` with its Low/High columns. A 2022 example that V16 recorded as present in every state is `DENTAL_CrudePrev`. Do not put `COLON_SCREEN`, `MAMMOUSE`, `TEETHLOST`, or `ACCESS2` on the same population footing as all-adult measures. Field descriptions give the age or sex group.

No chart or dashboard has been built.

## Not in this task

No charts, dashboards, slides, or analytical narrative were built.
