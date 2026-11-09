# Grower Web Map Provenance

This file records the sources, licences, and policy decisions for the
grower-level interactive web map. Generated HTML maps are runtime artifacts and
stay outside this repository.

## Field boundary polygons

- **Source**: the My Farm Advisor data pipeline's own output at
  `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson`.
- **Upstream**: for the United States the pipeline seeds these from USDA NASS
  Crop Sequence Boundaries via the FIBOA GeoParquet mirror
  (`https://data.source.coop/fiboa/us-usda-cropland/us_usda_cropland.parquet`,
  `source=usda_csb_fiboa`), or from OpenStreetMap/Overpass where OSM coverage is
  used. Country routing is documented in
  [../references/field-boundary-sources.md](../references/field-boundary-sources.md).
- **Policy**: this subskill reads the pipeline's persisted polygons and never
  re-downloads or re-samples boundaries. It carries forward the pipeline's
  provenance fields (`source`, `csb_id`, `county`, `state`) into the map
  popups.

## Basemap tiles

- **ESRI World Imagery** (default): `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`.
  Attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and
  the GIS User Community". Tiles are requested by the browser at view time; they
  are not embedded in the generated HTML.
- **OpenStreetMap** (optional toggle): `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`.
  Attribution: "© OpenStreetMap contributors", ODbL 1.0.
- **Leaflet** (map library): `https://unpkg.com/leaflet@1.9.4/`, BSD-2-Clause.

## Policy decisions

- **No embedded imagery or rasters.** The generated HTML embeds only boundary
  coordinates (rounded to six decimals) and a small set of attributes. Basemap
  imagery loads from the internet in the browser, keeping the file small and the
  repository asset-free.
- **No new Python dependencies.** The generator uses only the standard library;
  it runs inside the existing data-pipeline runtime venv.
- **Runtime-only outputs.** Maps are written under
  `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/<grower>/derived/maps/` and
  must not be committed. See the repository `ASSET_POLICY.md`.
- **Deterministic output.** Sorted iteration, fixed coordinate rounding, and no
  timestamps make repeated runs byte-identical.
