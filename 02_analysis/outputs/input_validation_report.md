# EDA input acceptance report

Generated: 2026-10-29T23:31:14+08:00

**Overall status: PASS (16 passed, 0 failed)**

## Input summary

- Cleaned table: 3,143 rows × 332 columns
- Unique county FIPS keys: 3,143
- State/DC codes represented: 51
- Cleaned SHA-256: `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`

## Checks

| ID | Status | Check | Observed |
| --- | --- | --- | --- |
| A01 | PASS | Required input files exist | [] |
| A02 | PASS | Raw CSV hash matches the supplied provenance record | a47cad3a852c5b35a031d548bc6dd4e9b5f7836bb7c851b84382160beafe15ef |
| A03 | PASS | Cleaned table has the expected number of rows | 3143 |
| A04 | PASS | Cleaned table has the expected number of columns | 332 |
| A05 | PASS | Field dictionary has one row per cleaned column | 332 |
| A06 | PASS | Field dictionary names and order match the cleaned table | exact match |
| A07 | PASS | Required geographic, label, population, and core metric fields exist | [] |
| A08 | PASS | Every CountyFIPS is a five-digit text key | 0 |
| A09 | PASS | CountyFIPS is unique | 0 |
| A10 | PASS | Leading-zero FIPS codes were preserved | 318 |
| A11 | PASS | Core metric nonblank values are numeric | {"DIABETES_AdjPrev": 0, "OBESITY_AdjPrev": 0, "LPA_AdjPrev": 0, "CSMOKING_AdjPrev": 0, "ACCESS2_AdjPrev": 0} |
| A12 | PASS | Core metric estimates are percentages between 0 and 100 | {"DIABETES_AdjPrev": 0, "OBESITY_AdjPrev": 0, "LPA_AdjPrev": 0, "CSMOKING_AdjPrev": 0, "ACCESS2_AdjPrev": 0} |
| A13 | PASS | Core point estimates fall inside their supplied intervals | {"DIABETES_AdjPrev": 0, "OBESITY_AdjPrev": 0, "LPA_AdjPrev": 0, "CSMOKING_AdjPrev": 0, "ACCESS2_AdjPrev": 0} |
| A14 | PASS | Core 2023 metric gaps are the documented 187 KY/PA counties | {"DIABETES_AdjPrev": {"count": 187, "states": "KY;PA"}, "OBESITY_AdjPrev": {"count": 187, "states": "KY;PA"}, "LPA_AdjPrev": {"count": 187, "states": "KY;PA"}, "CSMOKING_AdjPrev": {"count": 187, "states": "KY;PA"}, "ACCESS2_AdjPrev": {"count": 187, "states": "KY;PA"}} |
| A15 | PASS | Derived longitude and latitude are numeric and within world bounds | 0 |
| A16 | PASS | Every row has a display county name | 0 |

## Decision

The cleaned table is accepted as the formal EDA input.

This acceptance does not remove the documented analytical limits: blanks are not zero; crude and age-adjusted estimates must remain separate; map joins use `CountyFIPS`; and modelled county estimates should not be presented as causal effects or an overall health ranking.
