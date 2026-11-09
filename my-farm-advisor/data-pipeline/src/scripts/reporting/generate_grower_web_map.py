#!/usr/bin/env python3
"""Generate a lightweight grower-level interactive web map.

Reads the real field polygons produced by the data pipeline and writes one
self-contained Leaflet HTML file per grower. The map shows every field of the
grower on an online satellite basemap (ESRI World Imagery by default, with an
OpenStreetMap toggle), supports zoom/pan, and lets the reader click a field to
see basic metadata (grower, farm, field name, plus area, crop, county, state,
source). A sidebar lists the fields grouped by farm and zooms to a field on
click.

Output (one file per grower):
    growers/<grower>/derived/maps/<grower>_grower_map.html

The HTML embeds only the boundary coordinates (rounded) and a handful of
attributes. It never embeds rasters, imagery, or data bundles, so the file
stays small; the basemap tiles load from the internet in the browser.

This script is standard-library only and reads the canonical runtime tree under
``$DATA_PIPELINE_DATA_ROOT/data-pipeline``. Nothing is written outside that
root.

Usage:
    export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
    python generate_grower_web_map.py --all-growers
    python generate_grower_web_map.py --grower-slug il-grower
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

ESRI_WORLD_IMAGERY = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ESRI_ATTRIBUTION = (
    "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, "
    "and the GIS User Community"
)
OSM_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION = "&copy; OpenStreetMap contributors"

COORD_PRECISION = 6

MAP_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
  #container { display: flex; height: 100vh; }
  #sidebar { width: 320px; max-width: 40vw; background: #ffffff; border-right: 1px solid #ddd; padding: 16px; overflow-y: auto; }
  #sidebar h1 { font-size: 1.25rem; margin: 0 0 4px; }
  #sidebar .subtitle { color: #555; font-size: 0.85rem; margin-bottom: 12px; }
  #sidebar .farm-group { margin-bottom: 14px; }
  #sidebar .farm-heading { font-weight: 600; font-size: 0.95rem; margin: 0 0 6px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 4px; }
  #sidebar ul { list-style: none; margin: 0; padding: 0; }
  #sidebar li.field-item { padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; background: #f7f9f7; border: 1px solid #e6ebe6; }
  #sidebar li.field-item:hover { background: #eaf3ea; }
  #sidebar li.field-item.active { background: #dcefdc; border-color: #9cc79c; }
  #sidebar .field-name { font-weight: 600; font-size: 0.9rem; }
  #sidebar .field-meta { font-size: 0.78rem; color: #666; }
  #map { flex: 1; height: 100%; }
  .leaflet-popup-content { font-size: 0.85rem; }
  .leaflet-popup-content table { border-collapse: collapse; }
  .leaflet-popup-content th { text-align: left; padding-right: 8px; color: #555; font-weight: 600; vertical-align: top; }
  .leaflet-popup-content td { padding: 0; }
  .fit-btn { margin-top: 6px; padding: 6px 10px; font-size: 0.8rem; border: 1px solid #ccc; background: #fff; border-radius: 6px; cursor: pointer; }
  .fit-btn:hover { background: #f0f0f0; }
  @media (max-width: 700px) { #container { flex-direction: column; } #sidebar { width: 100%; max-width: none; height: 40%; border-right: none; border-bottom: 1px solid #ddd; } #map { height: 60%; } }
</style>
</head>
<body>
<div id="container">
  <div id="sidebar">
    <h1>__GROWER_NAME__</h1>
    <div class="subtitle">Grower map &middot; __FIELD_COUNT__ field__FIELD_S__ across __FARM_COUNT__ farm__FARM_S__</div>
    <button class="fit-btn" id="fit-all">Fit all fields</button>
    <div id="field-list">__SIDEBAR__</div>
  </div>
  <div id="map"></div>
</div>
<script>
const MAP_DATA = __MAP_DATA__;

const esri = L.tileLayer("__ESRI_URL__", {
  maxZoom: 19, maxNativeZoom: 18, attribution: "__ESRI_ATTR__"
});
const osm = L.tileLayer("__OSM_URL__", {
  maxZoom: 19, attribution: "__OSM_ATTR__"
});

const map = L.map("map", { preferCanvas: true, layers: [esri] });
const bounds = MAP_DATA.overall_bounds;
if (bounds) { map.fitBounds(bounds); } else { map.setView([39.5, -89.0], 6); }

L.control.layers({ "Satellite (ESRI World Imagery)": esri, "Street (OpenStreetMap)": osm }).addTo(map);

function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function popupHtml(p) {
  const rows = [
    ["Grower", p.grower_name],
    ["Farm", p.farm_name],
    ["Field", p.field_name],
    ["Crop", p.crop],
    ["Area (acres)", p.area_acres],
    ["County", p.county],
    ["State", p.state],
    ["Source", p.source]
  ].filter(function (r) { return r[1] !== undefined && r[1] !== null && r[1] !== ""; });
  return "<table>" + rows.map(function (r) {
    return "<tr><th>" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>";
  }).join("") + "</table>";
}

const BASE_STYLE = { color: "#2E7D32", weight: 2, fillColor: "#7CC47C", fillOpacity: 0.25 };
const HL_STYLE = { color: "#1B5E20", weight: 3, fillColor: "#2E7D32", fillOpacity: 0.45 };

const layerByKey = {};
const fieldLayer = L.geoJSON(MAP_DATA.geojson, {
  style: function () { return BASE_STYLE; },
  onEachFeature: function (feature, layer) {
    const p = feature.properties;
    layerByKey[p.key] = layer;
    layer.bindPopup(popupHtml(p), { maxWidth: 320 });
    layer.on("click", function () { highlight(p.key); });
  }
}).addTo(map);

function highlight(key) {
  Object.keys(layerByKey).forEach(function (k) {
    layerByKey[k].setStyle(k === key ? HL_STYLE : BASE_STYLE);
    if (k === key) { layerByKey[k].bringToFront(); }
  });
  document.querySelectorAll("#field-list li.field-item").forEach(function (el) {
    el.classList.toggle("active", el.dataset.key === key);
  });
}

document.querySelectorAll("#field-list li.field-item").forEach(function (el) {
  el.addEventListener("click", function () {
    const layer = layerByKey[el.dataset.key];
    if (!layer) { return; }
    map.fitBounds(layer.getBounds(), { padding: [40, 40] });
    layer.openPopup();
    highlight(el.dataset.key);
  });
});

const fitAll = document.getElementById("fit-all");
if (fitAll) {
  fitAll.addEventListener("click", function () {
    if (bounds) { map.fitBounds(bounds); }
    Object.keys(layerByKey).forEach(function (k) { layerByKey[k].setStyle(BASE_STYLE); });
    document.querySelectorAll("#field-list li.field-item").forEach(function (el) { el.classList.remove("active"); });
  });
}
</script>
</body>
</html>
"""


def _data_root(cli_value: str | None) -> Path:
    raw = cli_value or os.environ.get("DATA_PIPELINE_DATA_ROOT")
    if not raw:
        sys.exit(
            "ERROR: DATA_PIPELINE_DATA_ROOT is required (or pass --data-root)."
        )
    root = Path(raw).expanduser()
    if not root.is_absolute():
        sys.exit(f"ERROR: data root must be absolute: {root}")
    runtime_base = root / "data-pipeline"
    if not runtime_base.is_dir():
        sys.exit(f"ERROR: runtime base not found: {runtime_base}")
    return runtime_base


def _round_numbers(value: object) -> object:
    if isinstance(value, float):
        return round(value, COORD_PRECISION)
    if isinstance(value, list):
        return [_round_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_numbers(item) for key, item in value.items()}
    return value


def _iter_coords(geometry: dict) -> list[list[float]]:
    coords: list[list[float]] = []
    stack: list[object] = [geometry.get("coordinates")]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            if item and isinstance(item[0], (int, float)):
                coords.append([float(item[0]), float(item[1])])
            else:
                stack.extend(item)
    return coords


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gather_grower(runtime_base: Path, grower_dir: Path) -> dict | None:
    grower_slug = grower_dir.name
    grower_meta_path = grower_dir / "grower.json"
    grower_name = grower_slug
    if grower_meta_path.exists():
        grower_name = str(_read_json(grower_meta_path).get("display_name") or grower_slug)

    farms_root = grower_dir / "farms"
    if not farms_root.is_dir():
        return None

    features: list[dict] = []
    field_index: list[dict] = []
    farms_seen: dict[str, str] = {}
    all_lons: list[float] = []
    all_lats: list[float] = []

    for farm_dir in sorted(p for p in farms_root.iterdir() if p.is_dir()):
        farm_slug = farm_dir.name
        boundary = farm_dir / "boundary" / "field_boundaries.geojson"
        if not boundary.exists():
            continue
        farm_name = farm_slug
        farm_meta_path = farm_dir / "farm.json"
        if farm_meta_path.exists():
            farm_name = str(_read_json(farm_meta_path).get("display_name") or farm_slug)
        farms_seen[farm_slug] = farm_name

        collection = _read_json(boundary)
        for feature in collection.get("features", []):
            props = dict(feature.get("properties") or {})
            geometry = feature.get("geometry") or {}
            if not geometry.get("coordinates"):
                continue
            field_id = str(props.get("field_id") or props.get("field_slug") or "field")
            field_name = str(
                props.get("field_name")
                or props.get("name")
                or field_id
            )
            key = f"{farm_slug}/{field_id}"
            rounded_geometry = _round_numbers(geometry)
            coords = _iter_coords(rounded_geometry)
            if not coords:
                continue
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            all_lons.extend(lons)
            all_lats.extend(lats)
            center = [round(sum(lats) / len(lats), COORD_PRECISION), round(sum(lons) / len(lons), COORD_PRECISION)]

            merged = {
                "key": key,
                "grower_slug": grower_slug,
                "grower_name": grower_name,
                "farm_slug": farm_slug,
                "farm_name": farm_name,
                "field_id": field_id,
                "field_name": field_name,
                "crop": props.get("crop"),
                "area_acres": props.get("area_acres"),
                "county": props.get("county_name") or props.get("county"),
                "state": props.get("state"),
                "source": props.get("source"),
            }
            features.append(
                {
                    "type": "Feature",
                    "properties": merged,
                    "geometry": rounded_geometry,
                }
            )
            field_index.append({**merged, "center": center})

    if not features:
        return None

    field_index.sort(key=lambda item: (item["farm_slug"], item["field_id"]))
    overall_bounds = [
        [round(min(all_lats), COORD_PRECISION), round(min(all_lons), COORD_PRECISION)],
        [round(max(all_lats), COORD_PRECISION), round(max(all_lons), COORD_PRECISION)],
    ]

    return {
        "grower_slug": grower_slug,
        "grower_name": grower_name,
        "farms": [{"farm_slug": s, "farm_name": n} for s, n in sorted(farms_seen.items())],
        "fields": field_index,
        "geojson": {"type": "FeatureCollection", "features": features},
        "overall_bounds": overall_bounds,
    }


def _sidebar_html(grower: dict) -> str:
    by_farm: dict[str, list[dict]] = {}
    for field in grower["fields"]:
        by_farm.setdefault(field["farm_slug"], []).append(field)

    farm_names = {f["farm_slug"]: f["farm_name"] for f in grower["farms"]}
    blocks: list[str] = []
    for farm_slug in sorted(by_farm):
        blocks.append('<div class="farm-group">')
        blocks.append(
            f'<div class="farm-heading">{html.escape(farm_names.get(farm_slug, farm_slug))}</div>'
        )
        blocks.append("<ul>")
        for field in sorted(by_farm[farm_slug], key=lambda x: x["field_id"]):
            meta_bits = []
            if field.get("crop"):
                meta_bits.append(html.escape(str(field["crop"])))
            if field.get("area_acres") is not None:
                meta_bits.append(f"{field['area_acres']} ac")
            meta = " &middot; ".join(meta_bits)
            blocks.append(
                f'<li class="field-item" data-key="{html.escape(field["key"], quote=True)}">'
                f'<div class="field-name">{html.escape(field["field_name"])}</div>'
                f'<div class="field-meta">{meta}</div></li>'
            )
        blocks.append("</ul></div>")
    return "".join(blocks)


def _render_html(grower: dict) -> str:
    map_data = {
        "grower_slug": grower["grower_slug"],
        "grower_name": grower["grower_name"],
        "overall_bounds": grower["overall_bounds"],
        "fields": grower["fields"],
        "geojson": grower["geojson"],
    }
    map_json = json.dumps(map_data, separators=(",", ":"), sort_keys=True)
    # Guard against a stray "</script>" inside string data.
    map_json = map_json.replace("</", "<\\/")

    doc = MAP_TEMPLATE
    replacements = {
        "__TITLE__": html.escape(f"{grower['grower_name']} — Grower Field Map"),
        "__GROWER_NAME__": html.escape(grower["grower_name"]),
        "__FIELD_COUNT__": str(len(grower["fields"])),
        "__FIELD_S__": "" if len(grower["fields"]) == 1 else "s",
        "__FARM_COUNT__": str(len(grower["farms"])),
        "__FARM_S__": "" if len(grower["farms"]) == 1 else "s",
        "__SIDEBAR__": _sidebar_html(grower),
        "__MAP_DATA__": map_json,
        "__ESRI_URL__": ESRI_WORLD_IMAGERY,
        "__ESRI_ATTR__": ESRI_ATTRIBUTION,
        "__OSM_URL__": OSM_URL,
        "__OSM_ATTR__": OSM_ATTRIBUTION,
    }
    for token, value in replacements.items():
        doc = doc.replace(token, value)
    return doc


def _discover_growers(runtime_base: Path, only: str | None) -> list[Path]:
    growers_root = runtime_base / "growers"
    if not growers_root.is_dir():
        sys.exit(f"ERROR: growers root not found: {growers_root}")
    if only:
        target = growers_root / only
        if not target.is_dir():
            sys.exit(f"ERROR: grower not found: {target}")
        return [target]
    return sorted(p for p in growers_root.iterdir() if p.is_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=None, help="Runtime data root (defaults to $DATA_PIPELINE_DATA_ROOT)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all-growers", action="store_true", help="Map every grower (default)")
    group.add_argument("--grower-slug", default=None, help="Map a single grower by slug")
    args = parser.parse_args(argv)

    runtime_base = _data_root(args.data_root)
    grower_dirs = _discover_growers(runtime_base, args.grower_slug)

    results = []
    for grower_dir in grower_dirs:
        grower = _gather_grower(runtime_base, grower_dir)
        if grower is None:
            print(f"skip {grower_dir.name}: no field boundaries found")
            continue
        out_dir = grower_dir / "derived" / "maps"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{grower['grower_slug']}_grower_map.html"
        out_path.write_text(_render_html(grower), encoding="utf-8")
        results.append(
            {
                "grower_slug": grower["grower_slug"],
                "grower_name": grower["grower_name"],
                "farms": len(grower["farms"]),
                "fields": len(grower["fields"]),
                "field_ids": [f["field_id"] for f in grower["fields"]],
                "output": str(out_path),
                "bytes": out_path.stat().st_size,
            }
        )

    print(json.dumps({"action": "grower_web_maps", "maps": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
