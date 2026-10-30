# CDC PLACES county data, 2025 release — cleaning and EDA

Reproducible cleaning and exploratory analysis of the CDC PLACES county file in GIS-friendly format, dataset `i46a-9kgh`.

The raw file is the official CSV from:

https://data.cdc.gov/api/views/i46a-9kgh/rows.csv?accessType=DOWNLOAD

Retrieved 22 October 2026, 6:50 pm Asia/Singapore. SHA-256:

`a47cad3a852c5b35a031d548bc6dd4e9b5f7836bb7c851b84382160beafe15ef`

A local Windows copy was cited during the run and was not present in this environment, so it was not compared byte for byte. See the provenance report.

## Layout

| Path | Contents |
| --- | --- |
| `data/raw/places_county_gis_2025_i46a-9kgh.csv` | Immutable source, 3,143 × 167 |
| `data/processed/places_county_gis_2025_i46a-9kgh_cleaned.csv` | Cleaned table, 3,143 × 332 |
| `data/processed/places_county_gis_2025_field_dictionary.csv` | Source and derived column descriptions |
| `scripts/clean_places_county.py` | Cleaning program |
| `reports/data_cleaning/run_20261022_185006/` | Phase reports, profiles, and the execution log |
| `02_analysis/` | EDA input acceptance, current Chinese EDA report, and reproducible analysis scripts |
| `03_visualisations/exploratory/` | Current exploratory SVG charts |

Source columns are copied unchanged. Derived columns are prefixed with `derived__` and hold parsed confidence limits, centroid coordinates, a display name, a short-name collision flag, and the raw row number.

## Run

Python 3.12. The cleaner uses the standard library. Tests need pytest.

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=scripts python3 scripts/profile_places_county.py
PYTHONPATH=scripts python3 scripts/clean_places_county.py
PYTHONPATH=scripts python3 scripts/validate_places_county.py
PYTHONPATH=scripts python3 -m pytest tests/test_places_cleaning.py -q
```

The cleaner will not run if the raw file hash changes.

## Run the accepted basic EDA

The formal EDA currently covers the 2023 age-adjusted estimates for diagnosed
diabetes, obesity, and no leisure-time physical activity.

```bash
python3 02_analysis/validate_eda_input.py
python3 02_analysis/basic_eda.py
python3 02_analysis/relationship_analysis.py
```

Read `02_analysis/EDA_report.md` and `02_analysis/RELATIONSHIP_report.md` for
the current results. The scripts stop if the accepted input is missing,
validation fails, or the cleaned-file hash changes after validation.

## Read this before visualising

`reports/data_cleaning/run_20261022_185006/06_cleaning_handoff.md`

In short: join on `CountyFIPS`; do not treat blanks as zero; keep crude and age-adjusted estimates apart; the estimates are model-based percents with published 95% intervals.
