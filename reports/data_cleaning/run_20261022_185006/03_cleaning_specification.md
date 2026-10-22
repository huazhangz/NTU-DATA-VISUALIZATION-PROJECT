# Phase 3 — Cleaning specification

Rules were settled from the Phase 1 metadata and the Phase 2 profile, before any source cell was rewritten. The machine-readable list is `03_cleaning_rules.csv`. Open items are `03_open_questions.csv`.

The governing choice is minimal change. The published file is already a coherent county table. The defects that justify a derived field are the Doña Ana encoding and the text form of the confidence intervals and centroids. Structural blanks and shared short names are real features of the release.

## Evidence classes used here

- **CDC text:** view description, column descriptions, methodology page, and the PLACES FAQ retrieved on this run.
- **Empirical:** counts and patterns computed from the preserved CSV.
- **Our rule:** a decision in `03_cleaning_rules.csv`.
- **Unverified:** a claim we could not read from a primary page. Those claims did not authorise a change.

## Identifiers

`CountyFIPS` stays a five-character string. Leading zeros stay. Codes are not padded, truncated, or recomputed. The check against Census ANSI state codes passed for every row, so no code was "corrected."

`StateAbbr` and `StateDesc` already match those state codes, including the District of Columbia. They are not recoded.

County short names keep CDC's spelling and punctuation, including `Ste. Genevieve` and hyphenated Alaska names. Trailing class words such as County or Parish are not in the file and were not invented. The six within-state name collisions stay as two rows each. `derived__short_name_collision` marks them. County name is not a key.

Connecticut planning-region codes `09110`–`09190` stay. They are the county equivalents in this release.

## Text and encoding

No whitespace normalisation: the profile found none to remove.

`FOODSTAMP_Crude95ci` keeps its published spelling. Renaming it to `95CI` was rejected.

FIPS `35013` is a confirmed encoding defect. The source value stays in `CountyName`. `derived__CountyName_display` is `Doña Ana` only when the FIPS and the exact mojibake token both match. No other name is passed through a Latin-1 repair.

## Numeric fields

Population columns stay as the published integer tokens. They are counts, not percentages. The adult count is never above the total, so no row was altered for consistency.

Prevalence columns stay as published percent tokens. The CDC FAQ defines the percent scale (`N = Pop × p / 100`). Observed values lie in 0 to 100. Mixed zero- and one-decimal tokens are kept. No generic z-score or IQR rule is applied. Kalawao (population 81) and Los Angeles (population 9,663,345) both stay.

Crude and age-adjusted columns are separate and are not averaged or substituted for each other.

## Confidence intervals and centroids

The interval format was verified on all 229,152 non-blank interval cells. Parsing into `derived__{source}_Low` and `derived__{source}_High` is therefore allowed. The source text, including its padding spaces, stays. Blank intervals produce blank bounds. The same rule parses `Geolocation` into longitude and latitude and keeps the WKT.

## Missing values

Blank means not reported. It is not zero, and it is not imputed.

- Kentucky and Pennsylvania are blank for every 2023-description measure and complete for the five 2022 measures. The official release-notes sentence was not retrieved (`Q02`). The empirical block is still a reason to leave the cells blank.
- Seven health-related social needs measures are blank for 11 states and complete elsewhere. The count matches CDC's "39 states and the District of Columbia." The membership list is empirical (`Q03`).
- No county has fewer than 50 adults, so the FAQ's small-population rule does not create blanks here.

## Duplicates and outliers

There is no exact duplicate row, so there is no exclusion log. Shared names are not duplicates. Extremes are retained.

## What the cleaned table is

3,143 rows. 167 source columns, unchanged, followed by 165 derived columns:

- `derived__source_row_number`
- `derived__CountyName_display`
- `derived__short_name_collision`
- `derived__Geolocation_Longitude`
- `derived__Geolocation_Latitude`
- 160 confidence-limit columns (low and high for each of 80 interval fields)

No source column is dropped. The Socrata computed region column was never in the CSV and is not created.
