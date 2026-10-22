# Phase 1 — Source provenance

## Dataset identity

| Item | Value |
| --- | --- |
| Publisher | Centers for Disease Control and Prevention, National Center for Chronic Disease Prevention and Health Promotion, Division of Population Health |
| Name | PLACES: County Data (GIS Friendly Format), 2025 release |
| Socrata id | `i46a-9kgh` |
| License | Public domain |
| About page | https://data.cdc.gov/500-Cities-Places/PLACES-County-Data-GIS-Friendly-Format-2025-releas/i46a-9kgh/about_data |
| CSV | https://data.cdc.gov/api/views/i46a-9kgh/rows.csv?accessType=DOWNLOAD |
| View metadata | https://data.cdc.gov/api/views/i46a-9kgh.json |
| Column metadata | https://data.cdc.gov/api/views/i46a-9kgh/columns.json |

The view metadata `id` is `i46a-9kgh` and the `name` is the 2025 county GIS-friendly release. This is the wide county file: one row per county, all measures on that row. It is not the place, census-tract, ZCTA, or one-measure-per-row open-data extract.

## Retrieval

- Started: 22 October 2026, 6:50:06 pm Asia/Singapore (2026-10-22T10:50:06Z)
- HTTP status: 200 for the CSV and both JSON files
- CSV `Content-Type`: `text/csv; charset=utf-8`
- CSV `Last-Modified`: Thu, 04 Dec 2025 10:43:36 GMT, which is 4 December 2025, 6:43:36 pm Asia/Singapore
- User agent: `academic-data-cleaning/1.0 (CDC PLACES county GIS 2025 reproducibility)`

Preserved files:

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `data/raw/places_county_gis_2025_i46a-9kgh.csv` | 4,808,551 | `a47cad3a852c5b35a031d548bc6dd4e9b5f7836bb7c851b84382160beafe15ef` |
| `data/metadata/i46a-9kgh_view_metadata.json` | 313,141 | `a258a9828b32056bfb101dafdab890f0f2baf56f3aff26afcb7d2654f616e76f` |
| `data/metadata/i46a-9kgh_columns.json` | 281,217 | `f1ef486b89f26097b92bee4f8b128a25db9c4b8000eacb47e2d19f431525ba91` |

The raw CSV was not edited after download. `data/metadata/raw_sha256.txt` stores the same digest so the cleaner can refuse a different file.

## File format, observed rather than assumed

- Encoding: UTF-8, strict decode succeeded, no byte-order mark. The file starts with the ASCII header `StateAbbr`.
- Delimiter: comma. Python's `csv` module reads every data row as 167 fields.
- Newline: `\n` (4,144 line-feed bytes). The file ends with a newline.
- Header: present. Names are the Socrata display names (`StateAbbr`), not the lowercase API field names (`stateabbr`).
- No duplicate header names.
- Dimensions: **3,143 data rows and 167 columns**.

The assignment's comparison point was 3,143 rows and 167 columns. This file matches that point. The match was not used to drop or pad rows.

## What the dates mean

From the view metadata, as Unix seconds converted to Asia/Singapore:

| Field | Asia/Singapore | UTC |
| --- | --- | --- |
| `createdAt` | 14 September 2020, 10:47 pm | 2020-09-14T14:47:47Z |
| `rowsUpdatedAt` | 4 December 2025, 6:43:02 pm | 2025-12-04T10:43:02Z |
| `publicationDate` | 4 December 2025, 6:43:35 pm | 2025-12-04T10:43:35Z |
| `viewLastModified` | 23 September 2026, 6:42:43 am | 2026-09-22T22:42:43Z |

`createdAt` is when this Socrata view was first created. It is not the vintage of the 2025 estimates. The row-update time and the CSV `Last-Modified` header agree on 4 December 2025. `viewLastModified` is later, so the dataset page was touched again after the rows were updated. That later page edit is not evidence that the CSV bytes changed. The bytes in this project are the ones retrieved on 22 October 2026.

The metadata custom field `Issued: 7/27/2023` is older than the December 2025 row update. It is treated as stale catalog text, not as the data vintage. No cell was changed because of it.

## Scope documented by CDC

The view description, which is CDC text stored with the download, says:

- Model-based county estimates in GIS-friendly format.
- Coverage is the 50 states and the District of Columbia.
- Sources named for this release: BRFSS 2023 or 2022, Census Bureau 2023 county population estimates, and ACS 2019–2023 or 2018–2022.
- 35 measures use 2023 BRFSS. Five measures use 2022 BRFSS because the survey asks them every other year: all teeth lost, dental visits, mammograms, colorectal cancer screening, and short sleep duration.
- The file is meant to join to the Census 2023 county boundary file.

Column descriptions repeat the year on each estimate field. Those descriptions agree with the five-measure list above. See the profile for the check.

CDC methodology (https://www.cdc.gov/places/methodology/, page dated 7 December 2025) describes multilevel regression and poststratification. County estimates are model-based. The 95% intervals are the 2.5th and 97.5th percentiles of 1,000 Monte Carlo draws. The 2025 release has 40 measures, including 7 health-related social needs measures for 39 states and the District of Columbia.

The PLACES FAQ (https://www.cdc.gov/places/faqs/index.html, page dated 11 December 2025) states that prevalence is on a percent scale: an aggregate count is `N = Pop × p / 100`. The same FAQ says estimates are produced for geographic units with an adult population of at least 50, and that age-adjusted estimates exist at county and place level. Confidence intervals are published with the estimates.

## Columns in metadata but not in the CSV

`columns.json` has 168 entries. The CSV has 167. The extra metadata column is Socrata's computed region field:

- display name `Counties`
- field name `:@computed_region_skr5_azej`
- description: created automatically so the geolocation point can be placed in a polygon from dataset `skr5-azej`

It has no cached values in the column metadata, and it is absent from the CSV export. It was not added. This is not a deleted column.

## User-cited file

The follow-up named `PLACES__County_Data__GIS_Friendly_Format___2025_release.csv` on a Windows Downloads path and asked that it be the standard. It was not attached to the session. Provenance for that copy is unresolved. The official `i46a-9kgh` download above is the raw source for every later step.

## Machine-readable companions

- `01_source_metadata.json`
- `01_source_schema.csv`
- `01_raw_data_integrity.json`
