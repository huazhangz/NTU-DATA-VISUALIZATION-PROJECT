# Phase 0 — Execution plan

This plan was fixed from the assignment and from the empty repository. No visualisation, imputation for modelling, or narrative filtering is in scope.

1. Preserve an immutable raw copy of CDC PLACES County Data (GIS Friendly Format), 2025 release, dataset `i46a-9kgh`. Do not use place, tract, ZCTA, or long-format releases.
2. Store official view metadata and column metadata beside the CSV. Record URL, retrieval time, hashes, encoding, delimiter, and dimensions. Compare 3,143 rows and 167 columns only as a published benchmark, not as a rule that rewrites the file.
3. Profile the raw text before any transformation: structure, missingness, keys, numeric range, confidence-interval text, and geography.
4. Write a rule list. Accept a change only when the profile and an official description support it. Prefer no change when the evidence is incomplete.
5. Implement one deterministic script, `scripts/clean_places_county.py`. It reads the preserved CSV, checks the recorded SHA-256, copies source cells unchanged, and appends derived fields.
6. Validate by rereading raw and cleaned files, rebuilding the cleaned file, and running pytest. A successful script exit is not treated as proof.
7. Stop after the handoff. Do not build charts.

Decisions reserved for the evidence, and then settled by it:

- Do not impute blanks.
- Do not drop rows or columns.
- Do not rename `FOODSTAMP_Crude95ci`.
- Do not deduplicate on county name.
- Parse confidence intervals and WKT centroids only if every non-blank value matches a verified pattern, and keep the source text.
- Repair text only in a derived display field, and only for an exact encoding defect.

The user-cited Windows file could not be read. The plan continued with the official download and records that limitation instead of inventing a match.
