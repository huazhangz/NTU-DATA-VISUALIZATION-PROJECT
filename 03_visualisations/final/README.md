# Final visualisations

## County health choropleth

- `county_diabetes_choropleth.svg`: static, presentation-ready diabetes map.
- `interactive_county_map/index.html`: interactive map with metric switching,
  county hover/focus details, 95% intervals, and pinned county selection.
- `build_county_map.py`: dependency-free reproducible builder.

Rebuild from the repository root:

```bash
python3 03_visualisations/final/build_county_map.py
```

Preview locally:

```bash
python3 -m http.server 8000 --directory 03_visualisations/final/interactive_county_map
```

Then open <http://localhost:8000/>.

The map uses U.S. Census Bureau 2023 county cartographic boundaries and joins
them to the validated CDC PLACES table by `CountyFIPS`. Colors use five
metric-specific quantile classes from a sequential ColorBrewer Blues palette.
Gray means the 2023 estimate was not published or no PLACES row exists.

## Diabetes–physical inactivity relationship

- `diabetes_inactivity_relationship.svg`: static, presentation-ready scatterplot.
- `interactive_relationship/index.html`: interactive scatterplot with Census
  region filtering, LOWESS trend updates, county hover details, 95% intervals,
  and pinned county selection.
- `build_relationship_scatter.py`: dependency-free reproducible builder.

Rebuild from the repository root:

```bash
python3 03_visualisations/final/build_relationship_scatter.py
```

Preview locally:

```bash
python3 -m http.server 8002 --directory 03_visualisations/final/interactive_relationship
```

The chart uses 2,956 counties with both 2023 age-adjusted estimates. The LOWESS
curve summarizes the relationship without forcing a straight line. Pearson
correlation, R-squared, and all regional views are descriptive rather than
causal or individual-level results.

## Upper-quartile estimate overlap

- `upper_quartile_overlap_map.svg`: static combination of a county overlap map
  and a compact 0/1/2/3-measure count distribution.
- `interactive_overlap/index.html`: interactive map with category filters,
  clickable distribution bars, county details, and metric-level threshold flags.
- `build_overlap_map.py`: dependency-free reproducible builder that reuses the
  verified 2023 county projection from `build_county_map.py`.

Rebuild from the repository root:

```bash
python3 03_visualisations/final/build_overlap_map.py
```

Preview locally:

```bash
python3 -m http.server 8004 --directory 03_visualisations/final/interactive_overlap
```

The upper-quartile thresholds are diabetes 12.5%, obesity 40.6%, and physical
inactivity 30.5%. Exactly 377 of 2,956 complete counties meet all three. These
are descriptive, project-defined thresholds—not clinical cutoffs, causal
effects, policy priority designations, or an overall county health ranking.

## Extended views (revised 2026-10-31)

Built by `build_extended_views.py` from `02_analysis/extended_analysis.py`
outputs. Validation: `02_analysis/outputs/extended_views_validation.json`.

- `interactive_related_measures/` + `related_measures_diabetes.svg`: pick a
  2023 measure; ranked bars show how closely each other measure moves with it
  across counties (Spearman correlation, plain strength words); click a bar for
  the county scatterplot. Correlations of 0.9+ are flagged as mostly reflecting
  the shared CDC model.
- `interactive_state_tiles/` + `state_tile_small_multiples.svg`: each state's
  typical (median) county versus the typical U.S. county, for 39 measures, on an
  equal-size state tile map linked to a ranked dot plot. Unpublished states are
  hatched, never zero.
- `index.html`: gallery linking all five interactive views.

The earlier measure-landscape (clustered heatmap) and age-gap (ridgeline) views
were removed in the 2026-10-31 review as too technical for the audience; see
`docs/02_technical_summary.md`.

Preview everything:

```bash
python3 -m http.server 8000 --directory 03_visualisations/final
```
