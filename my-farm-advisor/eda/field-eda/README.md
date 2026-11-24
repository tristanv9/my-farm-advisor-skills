# Field EDA

A reproducible field-level EDA for My Farm Advisor. One Python run compares
field boundaries, CDL/cropland history, and weather across three growers and
writes ten static figures, four CSV tables, and one manifest. The report is a
separate, one-time artifact assembled later; this subskill deliberately stops at
reviewable outputs.

The first build covers the Assignment 2 growers:

| Grower | Farm | County | Fields | CDL | Weather |
| --- | --- | --- | --- | --- | --- |
| `il-grower` | `il-farm` | Iroquois, IL | 10 | 2019–2023 | 2021–2025 |
| `ia-grower` | `ia-farm` | Kossuth, IA | 10 | 2019–2023 | 2021–2025 |
| `ne-grower` | `ne-farm` | York, NE | 10 | 2019–2023 | 2021–2025 |

No soil, terrain, imagery, or NDVI layer is read. The legacy `il_*` / `ia_*`
soil and terrain tables cover only fields 1–3 and are stale; they are not joined.

## What It Compares

- **Boundaries**: field area, shape regularity, area-vs-shape correlation, and
  county-scale field locations.
- **CDL**: current crop mix per field, rotation diversity across five years, and
  the field-by-year dominant crop sequence.
- **Weather**: annual water supply, cumulative growing degree days, and the
  crop-year weather comparison for corn versus soybean years.

Each category covers within-field over time where the data support it, across
fields within a grower, and across growers.

## Inputs

Read from `${DATA_PIPELINE_DATA_ROOT}/data-pipeline`, never downloaded here:

- `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson`
- `growers/<grower>/farms/<farm>/derived/tables/<farm>_<start>_<end>_full_composition.csv`
- `growers/<grower>/farms/<farm>/derived/tables/<farm>_weather_<start>_<end>.csv`

The generator hashes every input and records its path, row count, and SHA-256 in
the manifest.

## Outputs

```
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/
```

| Artifact | Kind | Story |
| --- | --- | --- |
| `fig_boundary_size_distribution.png` | figure | NE fields cluster at 184–222 ha; IL/IA span wider ranges; IA carries the 57.6 ha outlier. |
| `fig_boundary_compactness.png` | figure | Compactness distributions overlap; shape does not separate growers. |
| `fig_boundary_area_vs_compactness.png` | figure | Pooled size–shape rank correlation is weak; NE alone shows none. |
| `fig_boundary_field_locations.png` | map | County-scale scatter of the individually selected fields, colored by CDL 2023. |
| `fig_cdl_composition_2023.png` | figure | 2023 crop mix per field with an explicit unclassified residual. |
| `fig_cdl_diversity.png` | figure | Shannon H′ of each field's five-year dominant-crop sequence. |
| `fig_cdl_rotation_heatmap.png` | figure | Field x year crop sequence, 2019–2023. |
| `fig_weather_annual_precip.png` | figure | Annual precipitation by field and year, with POWER-cell counts. |
| `fig_weather_gdd_curves.png` | figure | Cumulative GDD by year, averaged across distinct POWER cells with a min–max band. |
| `fig_weather_crop_link.png` | figure | Seasonal water and GDD for corn vs soybean years, with pooled tests. |
| `field_metrics.csv` | table | One row per field: geometry, CDL, rotation, weather, and cell id. |
| `analysis_boundary_correlation.csv` | table | Spearman area-vs-compactness by grower and pooled. |
| `analysis_cdl_transitions.csv` | table | Year-over-year dominant-crop transition counts and shares. |
| `analysis_weather_crop_link.csv` | table | Field-year weather joined to the CDL dominant crop, 2021–2023. |
| `manifest.json` | manifest | Parameters, input hashes, artifact catalogue, statistics, caveats. |

All outputs are runtime artifacts and stay out of Git.

## Measured Findings

These are the numbers the manifest and figures encode, not impressions:

- **Field size differs by grower.** Kruskal–Wallis H=12.11, p=0.0023,
  ε²=0.374. Medians: IL 245 ha, IA 214 ha, NE 208 ha. NE is tight
  (184–222 ha); IA includes a 57.6 ha field (`ia-4`).
- **Compactness does not separate growers.** Medians IL 0.329, IA 0.402,
  NE 0.354; H=0.65, p=0.722, ε²=−0.050. Do not read the shape figure as a
  grower signature.
- **Area and shape have only a weak pooled link.** Spearman ρ=−0.471
  (p=0.0086) pooled; IA ρ=−0.709 (p=0.022), IL ρ=−0.576 (p=0.082), NE ρ=−0.079
  (p=0.829). The pooled result is driven by IA's small irregular field.
- **Rotation is the norm, with exceptions.** Most fields follow a strict
  corn–soy alternation (dominant-sequence H′=0.673). Four fields are
  monocultures over five years (H′=0; `il-3`, `ne-2`, `ne-3`, `ne-6`), and
  `ia-4` has the most diverse sequence (four dominant crops, H′=1.332:
  fallow → soy → corn → soy → alfalfa).
- **Weather differs mainly by grower, not by crop.** Seasonal (Apr–Sep)
  precipitation medians: IL 537 mm, IA 583 mm, NE 448 mm. Seasonal GDD
  medians: IL 1856, IA 1690, NE 2069 °C-day. Corn-vs-soy comparisons are not
  significant (pooled Mann–Whitney p=0.82 for precipitation, p=0.81 for GDD;
  every per-grower p≥0.31) and are exploratory because fields share only ten
  POWER cells.
- **Weather is pseudo-replicated.** IL has 3 cells (5/3/2 fields), IA has 4
  (1/4/3/2), NE has 3 (8/1/1). Fields in one cell carry identical series.

## Usage

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd my-farm-advisor/data-pipeline
./scripts/install.sh --non-interactive --force-refresh --no-install-deps --persist none
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  src/scripts/reporting/generate_field_eda.py \
  --growers il-grower ia-grower ne-grower \
  --run-name assignment-2
```

The generator prints a JSON summary with each grower's field count, POWER-cell
count, output directory, and warnings. It fails if any listed artifact is
missing.

## Verify

```bash
OUT="${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/assignment-2"
ls -1 "$OUT" | wc -l          # 15 files: 10 PNG + 4 CSV + manifest.json
python3 -c "import json,sys; m=json.load(open(sys.argv[1])); print(len(m['artifacts']), m['statistics']['boundary_area_kruskal'])" "$OUT/manifest.json"
```

A repeated run with identical inputs produces byte-identical artifacts.

## Known Limits

- The 10 fields per grower are individually selected CSB polygons scattered
  across each county (up to 29 km from the farm centroid), not one contiguous
  farm. The location panel is county-scale and does not depict farm layout.
- Weather is sampled at field centroids but reported by POWER grid cell; field
  counts overstate independent weather samples.
- CDL composition keeps only the hardcoded crop classes; the residual is
  plotted as `Other/unclassified` and never renormalized. The largest residual
  is 6.65% (`ia-4`, 2023, mostly rye).
- The weather/crop join is limited to 2021–2023, the overlap of CDL 2019–2023
  and weather 2021–2025, and to corn/soy dominant years.
- No report, HTML, dashboard, soil, terrain, imagery, or NDVI is produced.

## See Also

- [SKILL.md](SKILL.md) — routing entrypoint.
- [GUIDE.md](GUIDE.md) — metric definitions, catalogue, flags, troubleshooting.
- [INDEX.md](INDEX.md) — file-level navigation.
- [PROVENANCE.md](PROVENANCE.md) — sources, licences, and policy.
- [`../../data-pipeline/src/scripts/reporting/generate_field_eda.py`](../../data-pipeline/src/scripts/reporting/generate_field_eda.py) — the generator.
- [`../../data-pipeline/README.md`](../../data-pipeline/README.md) — runtime setup.