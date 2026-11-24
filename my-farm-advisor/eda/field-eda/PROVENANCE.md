# Field EDA Provenance

This file records the sources, licences, and policy decisions for the field-level
EDA subskill. Generated figures, tables, and manifests are runtime artifacts and
stay outside this repository.

## Field boundary polygons

- **Source**: the My Farm Advisor data pipeline's own output at
  `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson`.
- **Upstream**: USDA NASS Crop Sequence Boundaries via the FIBOA GeoParquet
  mirror (`source=usda_csb_fiboa`):
  `https://data.source.coop/fiboa/us-usda-cropland/us_usda_cropland.parquet`.
  Country routing is documented in
  [`../../data-pipeline/references/field-boundary-sources.md`](../../data-pipeline/references/field-boundary-sources.md).
- **Licence**: US Government work, public domain.
- **Policy**: this subskill reads the persisted polygons and never re-downloads
  or re-samples boundaries. The generator carries forward `source`, `csb_id`,
  `county`, `state`, and the CSB selection-year attributes. The boundary layer's
  own `crop` field is renamed `csb_crop` so it can never be confused with CDL.

## Weather

- **Source**: the pipeline's farm weather CSV at
  `growers/<grower>/farms/<farm>/derived/tables/<farm>_weather_<start>_<end>.csv`.
- **Upstream**: NASA POWER daily data, MERRA-2 and SYN1Deg, via the public
  NASA POWER S3 Zarr stores:
  `https://nasa-power.s3.us-west-2.amazonaws.com/merra2/temporal/power_merra2_daily_temporal_lst.zarr`
  and the corresponding `syn1deg` store. The pipeline's legacy fallback is the
  NASA POWER point API (`https://power.larc.nasa.gov/api/temporal/daily/point`).
- **Licence**: NASA open data; no key required. Attribution: NASA POWER
  (Prediction Of Worldwide Energy Resources), NASA Langley Research Center.
- **Policy**: this subskill does not query NASA POWER. It reads the cached farm
  CSV, filters the requested years, and never refetches.

## CDL / cropland

- **Source**: the pipeline's full-composition table at
  `growers/<grower>/farms/<farm>/derived/tables/<farm>_<start>_<end>_full_composition.csv`.
- **Upstream**: USDA NASS Cropland Data Layer, downloaded by the pipeline from
  the NASS Geospatial Data Cache (`https://nassgeodata.gmu.edu/nass_data_cache/`).
- **Licence**: US Government work, public domain.
- **Policy**: the composition table retains only the hardcoded classes in the
  cropland module. The residual `100 − Σ known-class pct` is plotted as
  `Other/unclassified` and is never renormalized. Do not extend `CDL_CODES` to
  absorb the residual; keep it explicit.

## Crop palette

The generator defines a fixed semantic palette in `CROP_COLORS`:

| Crop | Color |
| --- | --- |
| Corn | `#E8B33A` |
| Soybeans | `#4E9F3D` |
| Winter Wheat | `#D8B26A` |
| Alfalfa | `#8E6BBE` |
| Grass/Pasture | `#A3C585` |
| Forest | `#2F6B3A` |
| Open Water | `#4A90D9` |
| Fallow/Idle | `#BDBDBD` |
| Other | `#9E9E9E` |
| Other/unclassified | `#E6E6E6` |

Colors are assigned by crop name, never by rank, so the same crop keeps the same
color across figures and a later report.

## Policy decisions

- **Static outputs only.** The generator writes PNG, CSV, and JSON. It produces
  no HTML, dashboard, or assembled report. A one-time report is a separate
  artifact assembled later.
- **No new downloads.** Every input is a persisted pipeline output. The run has
  no network dependency at plot time.
- **No soil, terrain, imagery, or NDVI.** The legacy `il_*` / `ia_*` soil and
  DEM tables cover only fields 1–3 and are stale; they are not joined.
- **Runtime-only outputs.** Artifacts are written under
  `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/`
  and must not be committed.
- **Determinism.** Sorted iteration, a fixed palette, a fixed random seed, and
  no timestamps make repeated runs byte-identical.

## Code

[`../../data-pipeline/src/scripts/reporting/generate_field_eda.py`](../../data-pipeline/src/scripts/reporting/generate_field_eda.py)
was written for Assignment 2. It follows the path helpers in
[`../../data-pipeline/src/scripts/lib/paths.py`](../../data-pipeline/src/scripts/lib/paths.py)
and the reporting conventions of the existing weather-chart and grower-web-map
scripts. It is not copied from an external skill.