# Phase 2 — Initial profile

The profile reads the preserved CSV with Python's `csv` module and keeps every token as text. Numeric summaries use `decimal.Decimal`. Quartiles are Hyndman–Fan type 7 quantiles of the non-missing parsed values. The standard deviation is the population standard deviation of those county values. It describes the spread of county estimates. It is not the standard error of a PLACES estimate. Uncertainty stays in the confidence-interval columns.

Script: `scripts/profile_places_county.py`.

## Structure

- 3,143 rows, 167 columns, header unique, no ragged rows, no empty rows, no empty columns, no constant columns.
- No exact duplicate records. SHA-256 of the full row is unique for all 3,143 rows.
- Socrata types: geographic names and FIPS and confidence intervals are text; population and prevalence are numbers; `Geolocation` is a point. The CSV itself is text for every column. That is the representation this pipeline keeps for source fields.

## Identifiers

| Candidate | Distinct | Unique? |
| --- | ---: | --- |
| `CountyFIPS` | 3,143 | Yes |
| `StateAbbr` + `CountyFIPS` | 3,143 | Yes |
| `Geolocation` | 3,143 | Yes |
| Full record | 3,143 | Yes |
| `StateAbbr` | 51 | No. Expected. The District of Columbia is the only abbreviation that occurs once. |
| `CountyName` | 1,837 | No. 442 short names occur in more than one state. |
| `StateAbbr` + `CountyName` | 3,137 | No. Six short names occur twice inside one state. |

`CountyFIPS` is five digits on every row, including 318 codes with a leading zero (`01001` through `09190`, and California `06037` for Los Angeles). Every state prefix matches the Census ANSI state code for `StateAbbr`, and `StateDesc` matches the Census state name, including `District of Columbia`. The reference table is `data/reference/ansi_state_fips.csv`.

County short names do not carry a trailing class word such as `County` or `Parish`. Alaska borough and census-area names, Louisiana parish names, and most independent cities are stored as the short name only (`Anchorage`, `Tensas`, `Alexandria`). A few official names contain the word City, including `Charles City` and `James City`. Class words were not added or removed.

### Same short name, different county-equivalent

These 12 rows are valid distinct FIPS codes. They are not duplicates.

| State | Short name | FIPS | Identity of that FIPS code |
| --- | --- | --- | --- |
| MD | Baltimore | 24510 | Baltimore city |
| MD | Baltimore | 24005 | Baltimore County |
| MO | St. Louis | 29510 | St. Louis city |
| MO | St. Louis | 29189 | St. Louis County |
| VA | Fairfax | 51600 | Fairfax city |
| VA | Fairfax | 51059 | Fairfax County |
| VA | Franklin | 51620 | Franklin city |
| VA | Franklin | 51067 | Franklin County |
| VA | Richmond | 51760 | Richmond city |
| VA | Richmond | 51159 | Richmond County |
| VA | Roanoke | 51770 | Roanoke city |
| VA | Roanoke | 51161 | Roanoke County |

The legal-class labels are the published identities of those FIPS codes. A Census gazetteer file was not downloaded in this run (the 2023 national gazetteer URL returned HTTP 404), so those labels were not written into the cleaned table. The collision itself is fully determined by the CSV.

Connecticut has nine codes, `09110` through `09190`, not the historical eight county codes `09001`–`09015`. Those nine codes are the current county-equivalent planning regions. They were left as published.

## Encoding

One non-ASCII county name: row 1093, FIPS `35013`, the characters `Do` + U+00C3 + U+00B1 + `a Ana`. That is the standard double-encoding of `ñ` (UTF-8 bytes `C3 B1` saved again as Latin-1 characters). The county is Doña Ana County, New Mexico. No other cell contains a non-ASCII character. There is no leading or trailing whitespace, no whitespace-only cell, and no formula-like text (`=`, `+`, `@`).

## A sentinel scan that was wrong, then corrected

The first scan treated the token `nd` as a missing-value sentinel. Case-folding made the postal abbreviation `ND` match it. All 53 hits were North Dakota, which has 53 counties. That scan is preserved as `02_anomalies_scan1_nd_false_positive.csv`. The token `nd` was removed from the sentinel list, and identifier columns are no longer scanned for sentinels. The corrected scan found **zero** sentinel tokens (`N/A`, `Suppressed`, `*`, and the other listed tokens do not occur).

## Missingness

Blanks are empty fields, not a documented suppression symbol. Within each measure, the four fields (crude estimate, crude interval, age-adjusted estimate, age-adjusted interval) are all present or all blank. There is no partial group.

Blank measure cells: **44,576**. Every one of them is explained by the two patterns below. There is no leftover county-level hole.

1. **Kentucky and Pennsylvania, 2023 measures.** All 120 Kentucky counties and all 67 Pennsylvania counties (187 counties) are blank for every measure whose column description does not say 2022, and they are complete for the five 2022 measures (teeth lost, dental visit, mammography, colorectal screening, sleeping less than 7 hours). `ACCESS2_CrudePrev` has 187 blanks, which is exactly 120 + 67. The CDC FAQ page retrieved for this run does not name these two states. The current release-notes page could not be fetched (HTTP 403 / timeout). A secondary write-up attributes a Kentucky and Pennsylvania note to that CDC page. The blank pattern is an empirical fact. The official sentence was not re-read. Nothing was filled in.

2. **Health-related social needs, 11 states.** All seven HRSN measures are blank in Colorado, Florida, Kentucky, Oregon, Pennsylvania, South Dakota, Tennessee, Texas, Vermont, Washington, and Wyoming (844 counties) and present in every county of the other 39 states and the District of Columbia. CDC's methodology and FAQ say these measures cover 39 states and the District of Columbia. The count matches. The 2024 exclusion list circulated by a secondary source (Arkansas, Colorado, Hawaii, Illinois, Louisiana, New York, North Dakota, Oregon, Pennsylvania, South Dakota, Virginia) does **not** match this file, so it was not reused. This file's 11 states are an empirical finding.

`TotalPop18plus` ranges from 75 (Kalawao County, Hawaii, FIPS `15005`) to 7,710,575 (Los Angeles County). `TotalPopulation` ranges from 81 to 9,663,345 for the same two counties. No county has fewer than 50 adults, so the CDC rule "do not report estimates below 50 adults" does not explain any blank in this file. Kalawao is above that threshold and has estimates. Both population fields are positive integers, and the adult count never exceeds the total.

## Prevalence, intervals, and precision

- 40 measures, in the CDC category counts 12 / 7 / 4 / 7 / 3 / 7 (health outcomes, prevention, risk behaviors, disability, health status, health-related social needs). No measure prefix was left unclassified. Description years match the dataset's 2022 and 2023 lists.
- Non-missing prevalence is inside 0 to 100. The smallest observed value is 1.7 (`STROKE_CrudePrev`, Madison County, Idaho). The largest is 93.3 (`CHOLSCREEN_CrudePrev`, Sumter County, Florida). These are plausible percent estimates, not candidates for deletion.
- Published numeric tokens use either no decimal place or one decimal place. Thirty-two prevalence columns mix the two, for example `35` beside `34.6`. There is no scientific notation and no parse failure. Tokens were not rewritten to a common number of decimals.
- Every non-blank confidence interval matches `(low, high)` with optional spaces, such as `( 2.8,  3.5)`. Zero intervals have the lower bound above the upper bound. Zero point estimates fall outside their published interval. There are 229,152 non-blank intervals and 22,288 blank intervals.

## Geolocation

Every row has `POINT (longitude latitude)`. All 3,143 parse, all are unique, and all coordinates lie inside WGS84 degree limits. The column description calls this the county centroid. The source string keeps its full printed precision.

## What is unusual but valid

Small populations, prevalence near 2% or above 90%, duplicated short names, Connecticut planning-region codes, and integer prevalence tokens are retained. They are properties of the published file, not defects to be smoothed away.

## Artifacts

- `02_column_profile.csv`
- `02_missingness_profile.csv`
- `02_categorical_profile.csv`
- `02_candidate_key_analysis.csv`
- `02_initial_profile.json`
- `02_anomalies.csv` (the encoding defect and the 12 name collisions)
- `02_anomalies_scan1_nd_false_positive.csv`
- `02_measure_state_missingness.csv`
- `02_small_population_counties.csv` (header only: no county has fewer than 50 adults)
