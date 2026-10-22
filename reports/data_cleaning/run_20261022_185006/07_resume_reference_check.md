# Resume check — gazetteer and release notes

Estimated effort before this check: 15–20 minutes. Scope stayed inside the unfinished provenance items. The cleaned table was not rebuilt and its SHA-256 is unchanged.

## User file

`c:\Users\ASUS\Downloads\PLACES__County_Data__GIS_Friendly_Format___2025_release.csv` is still not in the session. No byte comparison. V23 remains NOT TESTED.

## CDC release notes

The page https://www.cdc.gov/places/current-release-notes/index.html still returns HTTP 403 to a direct download. The page fetcher returned the December 2025 text. The official sentence is now on record in `data/reference/cdc_places_2025_release_notes_excerpt.txt`:

Kentucky and Pennsylvania do not have 2023 BRFSS measures. The five 2022 measures were carried over. That matches the blank pattern already left unchanged in the cleaned file. No imputation was added.

The same page says the 2024 release was the first to use Connecticut planning regions. This file's nine Connecticut FIPS codes are those regions.

## Census 2023 county gazetteer

Downloaded from the national zip, not the `.txt` URL that previously returned 404.

- Zip: `data/reference/2023_Gaz_counties_national.zip`
- Text: `data/reference/2023_Gaz_counties_national.txt`
- Crosswalk: `data/reference/places_to_2023_gazetteer.csv`

Result:

- All 3,143 PLACES county FIPS codes are in the gazetteer.
- 3,140 short names are the gazetteer name without the legal-class suffix (`County`, `Parish`, `city`, `Borough`, `Census Area`, `Municipality`, `City and Borough`, or `Planning Region`).
- Two names match in full: District of Columbia (`11001`) and Carson City (`32510`).
- The only name that does not match as a prefix is FIPS `35013`: the file has the mojibake, and the gazetteer name is `Doña Ana County`. That confirms the derived display repair. `CountyName` was still not rewritten.
- The 12 within-state short-name collisions match the expected pairs (Baltimore city/County, St. Louis city/County, and the four Virginia city/county pairs).
- One county in the 50 states and DC is in the gazetteer and not in PLACES: Loving County, Texas, FIPS `48301`. Puerto Rico is in the gazetteer and outside PLACES coverage, which the dataset description already states. CDC does not report a place with fewer than 50 adults. This run did not load Loving County's 2023 adult population, so that rule is a possible reason, not a proven cause. The row was not invented.

Legal-class words were not copied into the cleaned county name. The crosswalk is the place to find them.
