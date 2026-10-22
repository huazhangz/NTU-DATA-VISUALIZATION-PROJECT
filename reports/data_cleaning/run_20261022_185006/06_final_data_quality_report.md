# Phase 6 — Final data-quality assessment

The cleaned table is fit for county-level visualisation **with the caveats below**. "The script finished" is not the claim. The claim is: source cells match the CDC file, the derived fields reparse exactly, and the blanks are structural.

## 1. Source dimensions and identifiers

The preserved file has **3,143 rows and 167 columns**. The unique geographic key is `CountyFIPS`, a five-character string. `StateAbbr` plus `CountyFIPS` is also unique. `Geolocation` happens to be unique in this extract. `CountyName` is not unique nationally, and it is not unique inside Maryland, Missouri, or Virginia.

The output has the same 3,143 rows and **332 columns** (167 source + 165 derived).

## 2. Important data-quality findings

- One encoding defect: Doña Ana County is published as the mojibake of `ñ`.
- Twelve county-equivalents share a short name with another unit in the same state. They are different FIPS codes.
- 44,576 measure cells are blank, in two complete blocks: Kentucky and Pennsylvania for 2023 measures, and 11 states for all seven health-related social needs measures.
- `FOODSTAMP_Crude95ci` uses a lowercase `ci`.
- Prevalence tokens mix `35` and `34.6`.
- The Socrata catalog `Issued` date (27 July 2023) lags the 4 December 2025 row update.
- A first missing-value scan falsely flagged North Dakota. That was a bug in the scanner, not in the data.

## 3. What was corrected, and why

Only one value is corrected, and only in a derived column. `derived__CountyName_display` for FIPS `35013` is `Doña Ana`. The source bytes are the double-encoded form of `ñ`, and `35013` is that county. Rule R13. The source `CountyName` is unchanged.

Confidence limits and centroid coordinates were parsed into derived columns after every non-blank value matched one pattern (rules R09 and R10). That is a representation change, not a change of the published number. A row index and a collision flag were added from the file itself (R11, R12).

## 4. What was retained, and why

- All 3,143 rows, including Kalawao and Los Angeles.
- All 167 source columns and every source character, including the Doña Ana mojibake, the `FOODSTAMP_Crude95ci` spelling, integer prevalence tokens, and interval spacing.
- All blanks. They are not errors to fill. They are unpublished estimates.
- Shared short names. Deleting one of a pair would delete a real county or city.
- Connecticut planning-region FIPS codes.

## 5. Rows or columns excluded

None. There is no exclusion log because nothing was excluded. `04_transformation_log.csv` records the rejected deletion and deduplication rules with count 0.

The Socrata computed column `:@computed_region_skr5_azej` was not in the CSV. It was not dropped from a file we held.

## 6. Imputation

None. No field was filled by mean, model, carry-forward, or zero. Blank stays blank in both the source columns and the derived interval bounds.

## 7. Limitations

- The user's Windows file was not available to hash (`Q01`).
- Kentucky and Pennsylvania are confirmed by the CDC December 2025 release notes: 2023 measures are unavailable, and the five 2022 measures were carried over (`Q02`, resolved on the resume check).
- The 11-state HRSN list is empirical. It matches the CDC coverage count and does not match a 2024 secondary list (`Q03`).
- Census 2023 gazetteer names now confirm every FIPS code. Legal-class suffixes are in `data/reference/places_to_2023_gazetteer.csv` and were not written into `CountyName` (`Q04`, resolved). Loving County, Texas (`48301`) is absent (`Q08`).
- Estimates are model-based small-area estimates, not direct survey percentages. Intervals can be wide. CDC says not to rank areas on the point estimate alone.
- Crude and age-adjusted estimates answer different questions.
- Measures do not all refer to the same people or the same year. Insurance is adults 18–64. Blood-pressure medication is adults with high blood pressure. Mammography is women 50–74. All teeth lost is adults 65 and older. Five measures are 2022 BRFSS; the rest are 2023. Population columns are Census 2023 total and age-18-plus counts, not the denominator of every measure.
- Multiplying a prevalence by `TotalPopulation` is not justified. The FAQ formula uses the population that matches the measure, then divides by 100 because the estimate is a percent.
- HRSN measures cannot be compared for the 11 unpublished states.
- Kentucky and Pennsylvania cannot be compared on 2023 measures.
- `derived__source_row_number` is an audit index, not a geographic code.

## 8. Tests

- PASS: 24 checks, including the gazetteer match (V22) and the saved release-notes excerpt (V24), plus 4 pytest tests.
- FAIL: none.
- WARNING: V26. Loving County, Texas is missing from the file. The cause was not verified against a population table.
- NOT TESTED: V23, the user-file bytes.

Reproducibility: rebuilding the cleaned file from the raw file produced the same SHA-256.

## 9. Cleaned file

`data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv`

SHA-256 `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`

## 10. Can another student reproduce this?

Yes, from this repository, if they use the preserved raw file and do not replace it. The commands are in `06_cleaning_handoff.md`. They do not need network access to rerun the profile, cleaner, or tests. They cannot reproduce a comparison to the unread Windows file. The release-notes sentence and the 2023 gazetteer are now stored in `data/reference/`.
