# Grower Web Map

Turn the real field polygons produced by the My Farm Advisor data pipeline into
one lightweight, self-contained interactive HTML map per grower.

Each map shows every field of the grower on an online satellite basemap (ESRI
World Imagery by default, with an OpenStreetMap toggle), supports zoom and pan,
and lets the reader click a field to see basic metadata — grower, farm, and
field name, plus area, crop, county, state, and source. A sidebar lists the
fields grouped by farm and zooms to a field on click.

## Why this exists

The pipeline produces authoritative field boundaries plus reports, posters, and
PNGs. Those are excellent for a printed or single-farm read, but they are not a
quick, shareable, zoomable grower-level view. This subskill adds that view
without embedding imagery or rasters: the polygons are drawn over live basemap
tiles, so the file stays small and easy to email or host.

## Inputs

All read from the canonical runtime tree under
`${DATA_PIPELINE_DATA_ROOT}/data-pipeline`:

- `growers/<grower>/grower.json` — grower display name.
- `growers/<grower>/farms/<farm>/farm.json` — farm display name.
- `growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson` — the real
  field polygons written by the pipeline.

No boundaries are downloaded and the farm pipeline is not re-run.

## Output

One file per grower:

```
growers/<grower>/derived/maps/<grower>_grower_map.html
```

The HTML embeds only boundary coordinates (rounded to six decimals) and a
handful of attributes. It never embeds rasters, imagery, or data bundles, so it
stays small; the basemap tiles load from the internet when the file is opened.

## Usage

Install or refresh the runtime source, then run the generator from the runtime
copy:

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src/scripts/reporting/generate_grower_web_map.py" \
  --all-growers
```

Map a single grower:

```bash
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src/scripts/reporting/generate_grower_web_map.py" \
  --grower-slug il-grower
```

The command prints a JSON summary with each grower's field count, field ids,
output path, and file size.

## Verify

```bash
R="${DATA_PIPELINE_DATA_ROOT}/data-pipeline"
ls -lh "$R"/growers/*/derived/maps/*_grower_map.html
grep -c "World_Imagery" "$R"/growers/il-grower/derived/maps/il-grower_grower_map.html
```

Open a generated file in a browser: zoom in and out, click a field for its
metadata popup, and use the sidebar to zoom to individual fields. The satellite
tiles require internet access in the browser.

## See also

- [GUIDE.md](GUIDE.md) — workflow, flags, output schema, troubleshooting.
- [INDEX.md](INDEX.md) — file-level navigation.
- [PROVENANCE.md](PROVENANCE.md) — boundary, basemap, and licence record.
- [`../src/scripts/reporting/generate_grower_web_map.py`](../src/scripts/reporting/generate_grower_web_map.py) — the generator.
- [../../admin/interactive-web-map/GUIDE.md](../../admin/interactive-web-map/GUIDE.md) — generic web-map workflow.
