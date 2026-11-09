---
name: grower-web-map
description: >
  Grower-level interactive web-map subskill for My Farm Advisor. Use when a farm
  or grower request needs a lightweight, shareable HTML map of real field
  polygons on an online satellite basemap, with click metadata and a field list.
license: Apache-2.0
metadata:
  author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  version: "0.1.0"
  skill-author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  skill-version: "0.1.0"
---

# Grower Web Map

Use this nested subskill inside `data-pipeline` to turn the real field polygons already produced by the pipeline into one small, self-contained interactive HTML map per grower.

## Start Here

- Read [README.md](README.md) for the human overview, inputs, outputs, usage, and verification.
- Read [GUIDE.md](GUIDE.md) for the workflow, CLI flags, output schema, and troubleshooting.
- Read [INDEX.md](INDEX.md) for file-level navigation.
- Read [PROVENANCE.md](PROVENANCE.md) before changing the basemap or boundary sources.
- Open [`../src/scripts/reporting/generate_grower_web_map.py`](../src/scripts/reporting/generate_grower_web_map.py) for the generator (standard-library only).
- Use this subskill for field-boundary source questions: [../references/field-boundary-sources.md](../references/field-boundary-sources.md).

## Routing Notes

- Invoke this subskill when the request mentions a grower map, field map, interactive web map, satellite basemap, field viewer, or a shareable HTML map of field boundaries.
- It reads the canonical runtime tree under `${DATA_PIPELINE_DATA_ROOT}/data-pipeline`; it does not download boundaries or run the farm pipeline.
- Boundaries come from the pipeline's own output (`growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson`), so the map always reflects the real seeded fields.
- Output is one HTML file per grower under `growers/<grower>/derived/maps/` and stays outside Git.
- For the generic, non-grower web-map workflow, see [../../admin/interactive-web-map/GUIDE.md](../../admin/interactive-web-map/GUIDE.md).

## Runtime Contract

- `DATA_PIPELINE_DATA_ROOT` is required and must be absolute, outside this repository.
- Runtime base is `${DATA_PIPELINE_DATA_ROOT}/data-pipeline`.
- Run the generator from the runtime copy: `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python ${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src/scripts/reporting/generate_grower_web_map.py --all-growers`.
- The generator is standard-library only; it needs no extra packages beyond the pipeline runtime venv.

## Output and Policy

- One file per grower: `growers/<grower>/derived/maps/<grower>_grower_map.html`.
- The HTML embeds only boundary coordinates (rounded) and a handful of attributes; it never embeds rasters, imagery, or data bundles, so it stays small.
- The basemap (ESRI World Imagery, with an OpenStreetMap toggle) loads from the internet in the browser.
- Generated maps are runtime artifacts and must not be committed to the repository.
