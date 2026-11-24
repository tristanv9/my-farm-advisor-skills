# Field EDA Guide

This guide documents the workflow, metric definitions, artifact catalogue, flags,
determinism, and troubleshooting for the field-level EDA subskill.

## Workflow

1. The data pipeline has already seeded one or more growers, each with one farm
   and real field polygons, CDL tables, and a farm weather CSV. See
   [`../../data-pipeline/README.md`](../../data-pipeline/README.md).
2. Copy the generator into the runtime source (if it changed) with
   `./scripts/install.sh --non-interactive --force-refresh --no-install-deps --persist none`.
3. Run [`../../data-pipeline/src/scripts/reporting/generate_field_eda.py`](../../data-pipeline/src/scripts/reporting/generate_field_eda.py)
   from the runtime copy with `DATA_PIPELINE_DATA_ROOT` exported.
4. The generator discovers farms, loads the three layers, derives metrics,
   writes four CSVs, renders ten PNGs, and writes `manifest.json`.
5. Read the manifest first: it records what was read, what was produced, the
   statistics behind each story, and the caveats.

There is no report, HTML, or dashboard step by design. A separate, one-time
report can be assembled from these artifacts later.

## Flags

| Flag | Meaning |
| --- | --- |
| `--growers <slug> ...` | Growers to include, in display order. Default is every grower with all three layers, in directory order. |
| `--run-name <name>` | Output subdirectory under `eda/field-eda/output/`. Default `default`. |
| `--out-dir <abs>` | Absolute output directory; overrides the runtime default. |
| `--cdl-years <start> <end>` | CDL window. Default `2019 2023`. |
| `--weather-years <start> <end>` | Weather window. Default `2021 2025`. |
| `--cdl-year <year>` | Snapshot year for the composition and map figures. Default is the last CDL year. |
| `--dpi <int>` | PNG resolution. Default `200`. |
| `--data-root <abs>` | Runtime data root; defaults to `$DATA_PIPELINE_DATA_ROOT`. Applied before path helpers import. |

## Input Contract

For each discovered farm the generator requires all three inputs. A farm missing
any one is skipped with a warning instead of failing the run.

```
growers/<grower>/grower.json
growers/<grower>/farms/<farm>/farm.json
growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson
growers/<grower>/farms/<farm>/derived/tables/<farm>_<start>_<end>_full_composition.csv
growers/<grower>/farms/<farm>/derived/tables/<farm>_weather_<start>_<end>.csv
```

The boundary `field_id` must be unique across the selected farms; the run stops
if it is not.

## Metric Definitions

### Boundaries

- **`area_ha`** — polygon area in EPSG:5070 (CONUS Albers, metres), divided by
  10,000. `area_ha_est` is the CSB selection-year reported area and `area_acres`
  its imperial equivalent; use `area_ha` for comparisons.
- **`perimeter_m`** — polygon perimeter in EPSG:5070.
- **`compactness`** — `4πA/P²`. A circle is 1.0; elongated or ragged shapes are
  lower. It is scale-free, so it measures shape regularity, not size.
- **`distance_to_farm_centroid_km`** — planar distance from each field centroid
  to the union centroid of the farm's fields. It exposes how scattered the
  selected fields are.
- **Kruskal–Wallis** — non-parametric test that at least one grower differs in
  a metric. `ε² = (H − k + 1) / (n − k)` is the effect size.
- **Spearman ρ** — rank correlation between area and compactness, computed per
  grower and pooled.

### CDL

- **`cdl_<year>_dominant`** — crop with the largest pixel share in that field-year.
- **`cdl_<year>_dominant_pct`** — its pixel share.
- **`cdl_residual_mean_pct`** — mean over years of `100 − Σ known-class pct`.
  This is the explicit `Other/unclassified` residual; it is never renormalized.
- **`cdl_distinct_classes`** — number of distinct CDL classes seen in any year,
  including small minority shares.
- **`cdl_mix_shannon_mean`** — mean within-year Shannon entropy of the crop mix.
  A field that is 100% one crop scores 0; a mixed field scores higher.
- **`cdl_rotation_distinct`** — number of distinct *dominant* crops across the
  CDL years.
- **`cdl_rotation_shannon`** — Shannon entropy of the five-year dominant-crop
  sequence. Monoculture = 0; strict corn–soy alternation ≈ 0.673; four crops in
  five years = higher. The diversity figure uses this metric.
- **`corn_years` / `soy_years`** — count of years in which corn or soybeans was
  the dominant crop.
- **Transition table** — for each consecutive year pair, counts and row shares
  of dominant-crop transitions, per grower and pooled.

### Weather

- **`annual_precip_mm`** — sum of `PRECTOTCORR` over the calendar year.
- **`seasonal_precip_mm`** — sum over April–September.
- **`gdd_total`** — full-year sum of daily GDD.
- **`seasonal_gdd`** — April–September sum of daily GDD.
- **Daily GDD** — `max((T2M_MAX + T2M_MIN)/2 − 10, 0)`, base 10 °C, mean method.
- **`weather_cell`** — a cell label assigned by hashing the full daily weather
  series for each field. Fields with byte-identical weather share a label.
  Labels are global across growers (`C1`…`C10`) and stored with their grower.
- **`weather_cell_fields`** — number of fields in the same grower that share the
  cell. Use this to judge pseudo-replication.

## Figure Catalogue

### Boundaries

**A1 `fig_boundary_size_distribution.png`** — box plus strip plot of field area,
one panel per grower, shared y-axis.

- Story: NE clusters tightly at 184–222 ha (median 208 ha); IL and IA span
  wider ranges (medians 245 and 214 ha); IA carries the 57.6 ha `ia-4` outlier.
- Statistic: Kruskal–Wallis H=12.11, p=0.0023, ε²=0.374.
- Read it as: field size is a real grower-level difference in this sample.

**A2 `fig_boundary_compactness.png`** — box plus strip plot of compactness, one
panel per grower.

- Story: distributions overlap heavily; compactness does not separate growers
  (H=0.65, p=0.722, ε²=−0.050).
- Read it as: do not use shape as a grower signature. Individual fields still
  vary from 0.135 to 0.564.

**A3 `fig_boundary_area_vs_compactness.png`** — scatter of area against
compactness, colored by grower, with per-grower Spearman ρ in the legend.

- Story: pooled ρ=−0.471 (p=0.0086) is weak and driven by IA's small irregular
  field; IA ρ=−0.709 (p=0.022), IL ρ=−0.576 (p=0.082), NE ρ=−0.079 (p=0.829).
- Read it as: size does not generally predict shape, and the pooled
  significance should not be generalized to a grower.

**A4 `fig_boundary_field_locations.png`** — county-scale map, one panel per
grower, fields filled by CDL 2023 dominant crop.

- Story: the ten fields per grower are individually selected CSB polygons
  scattered across the county, not a contiguous farm. Extents are roughly
  IL 28 × 48 km, IA 17 × 40 km, and NE 37 × 37 km.
- Read it as: spatial scatter and crop pattern, not farm layout. Field ids and
  crops are in the other figures and `field_metrics.csv`.

### CDL

**B1 `fig_cdl_composition_2023.png`** — 100% stacked horizontal bars, one bar per
field, colored by crop, with the residual shown as `Other/unclassified`.

- Story: in 2023 IL has 7 corn-dominant and 3 soybean-dominant fields; IA has
  3 corn, 6 soybean, and 1 alfalfa; NE has 5 corn and 5 soybean. Most fields are
  ≥97% one crop; `ia-4` is the visible alfalfa exception.
- Residual: typical 0.4–0.8%; largest is 6.65% (`ia-4`, 2023, mostly rye).

**B2 `fig_cdl_diversity.png`** — horizontal bars of `cdl_rotation_shannon` with
the number of distinct dominant crops annotated.

- Story: most fields follow a strict corn–soy alternation (H′=0.673). Four
  fields are monocultures over five years (H′=0; `il-3`, `ne-2`, `ne-3`,
  `ne-6`). `ia-4` is the most diverse field (four dominant crops, H′=1.332).
- Read it as: rotation discipline, not within-year crop-mix entropy. Use
  `cdl_mix_shannon_mean` if the question is about how mixed a field is within a
  year.

**B3 `fig_cdl_rotation_heatmap.png`** — field x year grid, 2019–2023, cells
colored by dominant crop and labelled with a short crop code.

- Story: clean corn–soy alternation across most IL and IA fields; NE contains
  four monoculture blocks; `ia-4` runs fallow → soy → corn → soy → alfalfa.
- Read it as: within-field change over time and rotation discipline.

### Weather

**C1 `fig_weather_annual_precip.png`** — box plus strip plot of annual
precipitation by year and grower.

- Story: NE is the driest grower (field means 606–611 mm), IL the wettest
  (918–919 mm), IA in between (759–823 mm). Within-grower annual values range
  from about 440 to 1,080 mm.
- Replication: IL 3 cells (5/3/2 fields), IA 4 (1/4/3/2), NE 3 (8/1/1). Points
  within a cell are identical.

**C2 `fig_weather_gdd_curves.png`** — cumulative GDD from April to September,
one line per year, averaged across distinct POWER cells, with a min–max band.

- Story: NE accumulates the most heat (seasonal median 2069 °C-day), then IL
  (1856), then IA (1690). In all three growers 2025 is the highest curve and
  2021 the lowest.
- Read it as: season heat accumulation by year, with the band showing
  within-grower cell spread.

**C3 `fig_weather_crop_link.png`** — seasonal precipitation and seasonal GDD,
corn vs soybean dominant years, grouped by grower, with pooled Mann–Whitney p
in the panel titles.

- Story: no significant corn-vs-soy difference (pooled p=0.82 precipitation,
  p=0.81 GDD; every per-grower p≥0.31).
- Read it as: exploratory. Only ten POWER cells underpin 89 field-years, so the
  field-level n is pseudo-replicated. Absence of a significant difference here
  is not proof of no effect.

## Table Schemas

**`field_metrics.csv`** — 30 rows, one per field. Key columns:

| Column | Meaning |
| --- | --- |
| `field_id`, `grower_slug`, `farm_slug`, `county`, `state` | Identity. |
| `area_ha`, `perimeter_m`, `compactness` | Computed geometry. |
| `area_ha_est`, `area_acres`, `csb_crop`, `csb_id`, `source` | CSB selection-year attributes; `csb_crop` is not CDL. |
| `distance_to_farm_centroid_km` | Scatter from the farm centroid. |
| `cdl_2023_dominant`, `cdl_2023_dominant_pct` | CDL 2023 snapshot. |
| `cdl_residual_mean_pct`, `cdl_distinct_classes` | Residual and class count. |
| `cdl_mix_shannon_mean`, `cdl_rotation_distinct`, `cdl_rotation_shannon` | Mix and rotation diversity. |
| `corn_years`, `soy_years` | Dominant-crop year counts. |
| `annual_precip_mean_mm`, `seasonal_precip_mean_mm`, `gdd_seasonal_mean` | Weather means over 2021–2025. |
| `weather_cell`, `weather_cell_fields` | POWER-cell label and cell population. |

**`analysis_boundary_correlation.csv`** — 4 rows: one per grower plus pooled,
with `n_fields`, `spearman_rho`, and `spearman_p`.

**`analysis_cdl_transitions.csv`** — 46 rows: `grower_slug` (including `all`),
`from_year`, `to_year`, `from_crop`, `to_crop`, `count`, `share_pct`.

**`analysis_weather_crop_link.csv`** — 89 rows (corn/soy dominant field-years,
2021–2023): weather columns plus `crop` and `grower_label`.

## Manifest

`manifest.json` contains:

- `action`, `generator`, `output_dir`;
- `parameters` — growers, year windows, snapshot year, DPI, GDD base, season;
- `inputs` — per layer, grower/farm, relative path, SHA-256, row count;
- `farms` — field count, POWER cells, per-cell field counts;
- `artifacts` — file, kind, category, axis, story, absolute path;
- `statistics` — Kruskal–Wallis results, Spearman rows, weather/crop tests, and
  the maximum CDL residual;
- `caveats`, `warnings`.

## Determinism

- Fields, cells, and artifact order are sorted deterministically.
- Crop colors come from a fixed semantic palette, never from a rank-based map.
- `np.random.seed(0)` is set before jittered strip plots.
- The generator has no timestamps; PNGs carry no clock metadata.
- A repeated run with identical inputs produces byte-identical artifacts
  (verified by comparing SHA-256 checksums of all 15 outputs).

Grower display order follows `--growers`; the default path uses directory order.
The Assignment 2 run uses `il-grower ia-grower ne-grower`.

## Caveats

- CDL tables keep only the hardcoded classes; the residual is explicit and is
  not redistributed.
- Weather cells are few; fields in one cell are not independent samples.
- Weather lat/lon columns are field centroids, not POWER cell coordinates.
- The fields are scattered across each county, so the map is county-scale.
- There is no soil, terrain, imagery, or NDVI input.
- The weather/crop join covers only 2021–2023.

## Troubleshooting

- **`DATA_PIPELINE_DATA_ROOT is required`** — export it or pass `--data-root`.
- **`no farm has boundary + weather + CDL outputs`** — check the three input
  paths and the year windows; the CSV filenames embed the windows.
- **`field_id is not unique across the selected farms`** — two farms reuse a
  field id; rename one or run them separately.
- **Missing artifact after a run** — the generator raises with the missing file
  names; check the run log for a render error.
- **A figure looks unchanged after an edit** — the runtime source was not
  refreshed; run `install.sh --force-refresh` and rerun.

## Extending

- **Add a grower**: seed it upstream, then add its slug to `--growers`. The
  generator discovers farms under that grower automatically.
- **Change years**: pass `--cdl-years` / `--weather-years`. Keep the weather and
  CDL windows overlapping if the crop link matters.
- **Add a figure**: add it to `ARTIFACTS` and render it in `main`; the artifact
  existence check and manifest pick it up automatically.
- **Keep the first build reviewable**: add figures in the same three-category
  structure and give each one a measured story in `ARTIFACTS`.

## See Also

- [README.md](README.md) — overview and findings.
- [INDEX.md](INDEX.md) — file-level navigation.
- [PROVENANCE.md](PROVENANCE.md) — sources and licences.
- [`../../data-pipeline/grower-web-map/GUIDE.md`](../../data-pipeline/grower-web-map/GUIDE.md) — nested-subskill guide style.