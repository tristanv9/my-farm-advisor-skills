#!/usr/bin/env python3
# ruff: noqa: E402
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false
"""Backfill county FIPS routing keys on a farm boundary.

`download_csb_fields.py` writes `field_id`, `country`, `state`, `county`, etc.,
but not the `state_fips` / `county_fips` / `county_name` routing keys that CDL
and other FIPS-based workflows read. This step assigns them from the cached
GeoAdmin L2 county layer (centroid containment with a largest-overlap fallback)
and rewrites the farm boundary plus each per-field boundary, so CSB farms carry
the same routing keys as bootstrap farms.

Environment:
  DATA_PIPELINE_DATA_ROOT  required (runtime root)
  AG_GROWER_SLUG           required
  AG_FARM_SLUG             required
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

# TIGER/GADM county geojsons hold multi-megabyte multipolygons; GDAL's default
# 500 MB single-feature guard rejects them on read.
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")

import geopandas as gpd
import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR / "lib"))

ROUTING_KEYS = ("state_fips", "county_fips", "county_name")


def main() -> int:
    from paths import (
        farm_boundary_path,
        farm_manifest_dir,
        field_boundary_path,
        shared_geoadmin_counties_dir,
    )
    from reporting_bootstrap import ensure_skill_path, field_slug_map_from_inventory

    grower = os.environ.get("AG_GROWER_SLUG", "default-grower")
    farm = os.environ.get("AG_FARM_SLUG", "default-farm")
    boundary_path = farm_boundary_path(grower, farm)
    if not boundary_path.exists():
        print(f"boundary not found: {boundary_path}")
        return 1

    ensure_skill_path("geoadmin-admin")
    geoadmin_admin = importlib.import_module("geoadmin_admin")

    fields = gpd.read_file(boundary_path)
    counties = gpd.read_file(shared_geoadmin_counties_dir() / "counties_usa.geojson")
    counties_canada_path = shared_geoadmin_counties_dir() / "counties_canada.geojson"
    if counties_canada_path.exists():
        counties = gpd.GeoDataFrame(
            pd.concat([counties, gpd.read_file(counties_canada_path)], ignore_index=True),
            geometry="geometry",
            crs="EPSG:4326",
        )

    inventory_path = farm_manifest_dir(grower, farm) / "field-inventory.csv"
    field_slug_map = field_slug_map_from_inventory(
        inventory_path if inventory_path.exists() else None
    )

    mapping, ambiguity = geoadmin_admin.assign_fields_to_counties(
        fields, counties, field_slug_map=field_slug_map
    )
    lookup = mapping.set_index(mapping["field_id"].astype(str)).to_dict("index")

    for key in (*ROUTING_KEYS, "fips"):
        if key not in fields.columns:
            fields[key] = pd.Series([None] * len(fields), dtype="object")
        fields[key] = fields[key].astype("object")

    assigned = 0
    for idx, row in fields.iterrows():
        info = lookup.get(str(row.get("field_id")))
        if not info:
            continue
        for key in (*ROUTING_KEYS, "fips"):
            value = info.get(key)
            value = str(value).strip() if value is not None else ""
            fields.at[idx, key] = value or None
        if fields.at[idx, "state_fips"] is not None:
            assigned += 1

    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    fields.to_file(boundary_path, driver="GeoJSON")

    for _, row in fields.iterrows():
        field_id = str(row.get("field_id"))
        slug = field_slug_map.get(field_id, field_id)
        single = gpd.GeoDataFrame([row], geometry="geometry", crs=fields.crs)
        target = field_boundary_path(grower, farm, slug)
        target.parent.mkdir(parents=True, exist_ok=True)
        single.to_file(target, driver="GeoJSON")

    print(
        json.dumps(
            {
                "grower_slug": grower,
                "farm_slug": farm,
                "field_count": int(len(fields)),
                "assigned_state_fips": assigned,
                "ambiguity_count": int(len(ambiguity)),
                "boundary_path": str(boundary_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
