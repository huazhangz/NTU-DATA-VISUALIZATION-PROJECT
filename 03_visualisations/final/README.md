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
