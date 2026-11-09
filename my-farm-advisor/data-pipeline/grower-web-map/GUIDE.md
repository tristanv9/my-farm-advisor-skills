# Grower Web Map Guide

This guide documents the workflow, flags, output schema, and troubleshooting for
the grower-level interactive web map.

## Workflow

1. The data pipeline has already seeded one or more growers, each with one or
   more farms and real field polygons. See [`../README.md`](../README.md) for the
   runtime contract and pipeline commands.
2. Run [`../src/scripts/reporting/generate_grower_web_map.py`](../src/scripts/reporting/generate_grower_web_map.py)
   from the installed runtime copy.
3. For every discovered grower, the generator reads `grower.json`, each
   `farm.json`, and each `boundary/field_boundaries.geojson`, then writes one
   HTML map under `growers/<grower>/derived/maps/`.
4. Open the HTML in a browser. The map fits all of the grower's fields, draws
   them over the ESRI World Imagery basemap, and lists the fields in a sidebar.

## Flags

| Flag | Meaning |
| --- | --- |
| `--all-growers` | Map every grower under `growers/` (default). |
| `--grower-slug <slug>` | Map a single grower; mutually exclusive with `--all-growers`. |
| `--data-root <abs>` | Runtime data root; defaults to `$DATA_PIPELINE_DATA_ROOT`. |

## Output schema

```
growers/<grower>/derived/maps/<grower>_grower_map.html
```

The generated file is a single self-contained HTML document:

- **Leaflet 1.9.4** loaded from a CDN (CSS and JS).
- **Basemaps**: ESRI World Imagery (default) and OpenStreetMap, toggled through
  the Leaflet layers control.
- **`MAP_DATA`** embedded JSON with:
  - `grower_slug`, `grower_name`
  - `overall_bounds` — `[[min_lat, min_lon], [max_lat, max_lon]]`
  - `farms` — `[{farm_slug, farm_name}]`
  - `fields` — per-field metadata (`key`, grower/farm/field names, crop,
    area, county, state, source, centroid)
  - `geojson` — a `FeatureCollection` of the boundary polygons with the same
    per-field properties
- **Sidebar** field list grouped by farm; clicking an entry zooms to the field
  and opens its popup.
- **Click a polygon** to open a popup with grower, farm, field name, crop, area,
  county, state, and source.

## Determinism

- Growers and farms are iterated in sorted order; fields are ordered by
  `field_id`.
- Coordinates are rounded to six decimals; JSON is emitted with sorted keys and
  compact separators.
- The HTML contains no timestamps, so identical inputs produce byte-identical
  output.

## Performance and size

Only boundary coordinates and a few attributes are embedded. For a handful of
fields the HTML is well under 100 KB. The basemap tiles are fetched by the
browser at view time, so the file never carries imagery.

## Troubleshooting

- **`DATA_PIPELINE_DATA_ROOT is required`** — export it, or pass `--data-root`.
- **`runtime base not found`** — the path must contain a `data-pipeline/`
  directory created by the installer.
- **`no field boundaries found`** — the grower has no
  `farms/<farm>/boundary/field_boundaries.geojson`; run the farm pipeline first.
- **Blank basemap** — the browser needs internet access for the ESRI/OSM tiles;
  the field polygons still render without it.
- **Map shows stale fields** — re-run the generator after the pipeline changes
  boundaries; it overwrites the HTML in place.

## See also

- [README.md](README.md) — overview and usage.
- [INDEX.md](INDEX.md) — file-level navigation.
- [PROVENANCE.md](PROVENANCE.md) — sources and licences.
- [`../references/field-boundary-sources.md`](../references/field-boundary-sources.md) — boundary sourcing by country.
