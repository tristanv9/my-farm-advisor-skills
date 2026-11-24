# Field EDA Index

File-level navigation for the field-level EDA subskill.

## Entry points

- [SKILL.md](SKILL.md) — routing entrypoint: when to use, comparison axes, runtime contract, output policy.
- [README.md](README.md) — overview, artifact table, measured findings, usage, verification.
- [GUIDE.md](GUIDE.md) — metric definitions, figure/table catalogue, flags, determinism, troubleshooting.
- [PROVENANCE.md](PROVENANCE.md) — boundary, weather, and CDL sources, licences, and policy.
- [AGENTS.md](AGENTS.md) — local editing rules for this subskill.

## Code

- [`../../data-pipeline/src/scripts/reporting/generate_field_eda.py`](../../data-pipeline/src/scripts/reporting/generate_field_eda.py) — the generator (pandas, seaborn, matplotlib, geopandas, scipy).

## Runtime outputs

Generated under `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/`
and never committed:

- `fig_boundary_size_distribution.png`
- `fig_boundary_compactness.png`
- `fig_boundary_area_vs_compactness.png`
- `fig_boundary_field_locations.png`
- `fig_cdl_composition_2023.png`
- `fig_cdl_diversity.png`
- `fig_cdl_rotation_heatmap.png`
- `fig_weather_annual_precip.png`
- `fig_weather_gdd_curves.png`
- `fig_weather_crop_link.png`
- `field_metrics.csv`
- `analysis_boundary_correlation.csv`
- `analysis_cdl_transitions.csv`
- `analysis_weather_crop_link.csv`
- `manifest.json`

## Related

- [../INDEX.md](../INDEX.md) — EDA subtree index.
- [../../data-pipeline/README.md](../../data-pipeline/README.md) — runtime setup and pipeline commands.
- [../../data-pipeline/grower-web-map/INDEX.md](../../data-pipeline/grower-web-map/INDEX.md) — the nested-subskill layout this folder follows.
- [../eda-explore/GUIDE.md](../eda-explore/GUIDE.md) — first-pass inspection conventions.
- [../eda-visualize/GUIDE.md](../eda-visualize/GUIDE.md) — chart conventions.