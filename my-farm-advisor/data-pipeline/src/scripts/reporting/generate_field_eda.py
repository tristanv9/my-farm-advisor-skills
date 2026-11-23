#!/usr/bin/env python3
# ruff: noqa: E402
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false
"""Field-level EDA across boundaries, CDL/cropland, and weather.

Produces static, reviewable artifacts only: PNG figures, CSV tables, and one
manifest JSON. There is no HTML, dashboard, or report assembly here; the report
is a separate, one-time artifact assembled from these outputs.

Inputs (read from the canonical runtime tree, never downloaded here):
  growers/<grower>/farms/<farm>/boundary/field_boundaries.geojson
  growers/<grower>/farms/<farm>/derived/tables/<farm>_<start>_<end>_full_composition.csv
  growers/<grower>/farms/<farm>/derived/tables/<farm>_weather_<start>_<end>.csv

Scope: boundaries, CDL, weather. No soil, terrain, imagery, or NDVI. All figures
use the matplotlib Agg backend; no network access happens at plot time.

Artifacts (under --out-dir, default
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>):

  field_metrics.csv                          master per-field table
  analysis_boundary_correlation.csv          area-vs-compactness Spearman by scope
  analysis_cdl_transitions.csv               year-over-year crop transitions
  analysis_weather_crop_link.csv             field-year weather joined to crop
  fig_boundary_size_distribution.png         A1  field area by grower
  fig_boundary_compactness.png               A2  shape regularity by grower
  fig_boundary_area_vs_compactness.png       A3  correlation analysis
  fig_boundary_field_locations.png           A4  county-scale field locations colored by CDL 2023
  fig_cdl_composition_2023.png               B1  crop mix per field
  fig_cdl_diversity.png                      B2  rotation diversity per field
  fig_cdl_rotation_heatmap.png               B3  field x year crop sequence
  fig_weather_annual_precip.png              C1  annual water supply
  fig_weather_gdd_curves.png                 C2  cumulative GDD by year
  fig_weather_crop_link.png                  C3  crop-year weather comparison
  manifest.json                              params, inputs, artifacts, stats

Usage:
  export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
  python generate_field_eda.py
  python generate_field_eda.py --growers il-grower ia-grower ne-grower \
      --run-name assignment-2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# --data-root must be applied before runtime-path helpers read the environment
# at import time (paths.py resolves DATA_ROOT once, at module import).
_PRE = argparse.ArgumentParser(add_help=False)
_PRE.add_argument("--data-root", default=None)
_PRE_ARGS, _ = _PRE.parse_known_args()
if _PRE_ARGS.data_root:
    os.environ["DATA_PIPELINE_DATA_ROOT"] = str(
        Path(_PRE_ARGS.data_root).expanduser().resolve(strict=False)
    )

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from scipy import stats

_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS / "lib"))

from paths import (  # noqa: E402
    DATA_ROOT,
    GROWERS_ROOT,
    farm_boundary_path,
    farm_cdl_preferred_full_composition_path,
    farm_weather_path,
)

WEATHER_COLS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
    "RH2M",
    "WS10M",
]

# Fixed semantic palette. Crop colors are never re-assigned by rank so the same
# crop keeps the same color across figures and across a later report.
CROP_COLORS = {
    "Corn": "#E8B33A",
    "Soybeans": "#4E9F3D",
    "Winter Wheat": "#D8B26A",
    "Alfalfa": "#8E6BBE",
    "Grass/Pasture": "#A3C585",
    "Forest": "#2F6B3A",
    "Open Water": "#4A90D9",
    "Fallow/Idle": "#BDBDBD",
    "Other": "#9E9E9E",
    "Other/unclassified": "#E6E6E6",
}
CROP_ORDER = [
    "Corn",
    "Soybeans",
    "Winter Wheat",
    "Alfalfa",
    "Grass/Pasture",
    "Forest",
    "Open Water",
    "Fallow/Idle",
    "Other",
    "Other/unclassified",
]
CROP_ABBR = {
    "Corn": "Corn",
    "Soybeans": "Soy",
    "Winter Wheat": "Wht",
    "Alfalfa": "Alf",
    "Grass/Pasture": "Grass",
    "Forest": "Forest",
    "Open Water": "Water",
    "Fallow/Idle": "Fallow",
    "Other": "Other",
}
GROWER_COLORS = ["#1F4E79", "#2E8B57", "#B07A1E", "#7A4E9E", "#B5484A"]
DARK_TEXT_CROPS = {"Forest", "Open Water", "Alfalfa"}

GDD_BASE_C = 10.0
SEASON_MONTHS = (4, 9)  # inclusive, April..September

ARTIFACTS: list[dict[str, str]] = [
    {
        "file": "fig_boundary_size_distribution.png",
        "kind": "figure",
        "category": "boundaries",
        "axis": "across fields within a grower; across growers",
        "story": "NE fields cluster tightly near 200 ha; IL/IA span wider area ranges and IA carries the 57.6 ha outlier (Kruskal–Wallis H=12.1, p=0.002).",
    },
    {
        "file": "fig_boundary_compactness.png",
        "kind": "figure",
        "category": "boundaries",
        "axis": "across fields within a grower; across growers",
        "story": "Compactness ranges overlap heavily; it does not separate growers (H=0.65, p=0.72), so shape is not a usable grower signature here.",
    },
    {
        "file": "fig_boundary_area_vs_compactness.png",
        "kind": "figure",
        "category": "boundaries",
        "axis": "across growers",
        "story": "Pooled Spearman rho=-0.47 (p=0.009) is a weak size-shape trend driven by IA's small irregular field; per-grower NE shows essentially none.",
    },
    {
        "file": "fig_boundary_field_locations.png",
        "kind": "map",
        "category": "boundaries",
        "axis": "across fields within a grower; across growers",
        "story": "County-scale locations of the individually selected fields, colored by CDL 2023 dominant crop; the fields are scattered, not contiguous.",
    },
    {
        "file": "fig_cdl_composition_2023.png",
        "kind": "figure",
        "category": "cdl",
        "axis": "across fields within a grower; across growers",
        "story": "2023 crop mix per field with an explicit unclassified residual; NE continuous corn vs IL/IA rotation.",
    },
    {
        "file": "fig_cdl_diversity.png",
        "kind": "figure",
        "category": "cdl",
        "axis": "across fields within a grower",
        "story": "Shannon H' of the 5-year dominant-crop sequence: monocultures score 0, strict corn-soy rotations ~0.69, the ia-4 fallow/alfalfa field ~1.33.",
    },
    {
        "file": "fig_cdl_rotation_heatmap.png",
        "kind": "figure",
        "category": "cdl",
        "axis": "within a field over time",
        "story": "Field x year sequences reveal rotation discipline and the ia-4 alfalfa/fallow anomaly.",
    },
    {
        "file": "fig_weather_annual_precip.png",
        "kind": "figure",
        "category": "weather",
        "axis": "within a field over time; across growers",
        "story": "Annual water supply by field/year; NE is drier than IL/IA and dry years differ by grower.",
    },
    {
        "file": "fig_weather_gdd_curves.png",
        "kind": "figure",
        "category": "weather",
        "axis": "within a field over time; across growers",
        "story": "Heat accumulation and season length per year, averaged across distinct POWER cells with a min-max band.",
    },
    {
        "file": "fig_weather_crop_link.png",
        "kind": "figure",
        "category": "weather",
        "axis": "within a field over time; across growers",
        "story": "Compares seasonal water and GDD between corn and soybean years, labelled with cell-level replication.",
    },
    {
        "file": "field_metrics.csv",
        "kind": "table",
        "category": "all",
        "axis": "field",
        "story": "Master per-field table: geometry, CDL summary (composition, mix entropy, rotation entropy), weather summary, and weather cell id.",
    },
    {
        "file": "analysis_boundary_correlation.csv",
        "kind": "table",
        "category": "boundaries",
        "axis": "across growers",
        "story": "Spearman area-vs-compactness by scope, supporting the geometry comparison.",
    },
    {
        "file": "analysis_cdl_transitions.csv",
        "kind": "table",
        "category": "cdl",
        "axis": "within a field over time",
        "story": "Year-over-year crop transition counts and shares, by grower and pooled.",
    },
    {
        "file": "analysis_weather_crop_link.csv",
        "kind": "table",
        "category": "weather",
        "axis": "within a field over time",
        "story": "Field-year weather joined to the CDL dominant crop for 2021-2023.",
    },
]

CAVEATS = [
    "CDL tables retain only the hardcoded classes in the cropland module; residual = 100 - sum(pct) is plotted as Other/unclassified and is never renormalized.",
    "field_metrics.csv carries two Shannon columns: cdl_mix_shannon_mean is mean within-year crop-mix entropy, while cdl_rotation_shannon is the entropy of the five-year dominant-crop sequence; the diversity figure uses the latter.",
    "Weather fields map to only a few NASA POWER grid cells; fields sharing a cell have identical series, so field-level n overstates independent weather samples.",
    "The weather/crop join is limited to 2021-2023, the overlap of CDL 2019-2023 and weather 2021-2025.",
    "Weather lat/lon columns are field centroids, not POWER grid-cell coordinates.",
    "The 10 fields per grower are individually selected CSB polygons scattered across the county, not one contiguous farm; the location panel is county-scale and does not depict farm layout.",
    "Compactness does not separate growers in this sample (Kruskal-Wallis p=0.72); do not read figure A2 as a grower-level shape signal.",
    "No soil, terrain, imagery, or NDVI layers are read; no report or HTML/dashboard is produced here.",
]


@dataclass(frozen=True)
class FarmSpec:
    grower_slug: str
    farm_slug: str
    grower_name: str
    farm_name: str
    boundary: Path
    weather: Path
    cdl: Path


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
        }
    )


def _field_sort_key(field_id: str) -> tuple[str, int, str]:
    prefix, _, suffix = str(field_id).rpartition("-")
    try:
        return (prefix, int(suffix), str(field_id))
    except ValueError:
        return (str(field_id), 10**9, str(field_id))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(DATA_ROOT.resolve()))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _shannon(pcts: pd.Series) -> float:
    values = pcts[pcts > 0].astype(float) / 100.0
    values = values[values > 0]
    if values.empty:
        return 0.0
    return float(max(0.0, -(values * np.log(values)).sum()))


def _sequence_shannon(values: pd.Series) -> float:
    """Shannon entropy of a categorical sequence, e.g. 5 years of dominant crop.

    A monoculture sequence (Corn, Corn, Corn, Corn, Corn) scores 0; a strict
    corn-soy alternation scores ~0.69.
    """
    weights = values.value_counts(normalize=True).to_numpy(dtype=float)
    weights = weights[weights > 0]
    if weights.size == 0:
        return 0.0
    return float(max(0.0, -(weights * np.log(weights)).sum()))


def _save(fig: plt.Figure, path: Path, dpi: int) -> Path:
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _facet(n: int, *, width: float, height: float, sharey: bool = True):
    fig, axes = plt.subplots(
        1, n, figsize=(width * n, height), sharey=sharey, squeeze=False
    )
    return fig, axes[0]


def _panel_title(ax, grower: dict, extra: str = "") -> None:
    ax.set_title(f"{grower['label']}{extra}")


def _add_crop_legend(
    fig, cols: list[str], *, ncol: int = 6, y: float = -0.02
) -> None:
    handles = [
        Patch(facecolor=CROP_COLORS.get(c, "#9E9E9E"), edgecolor="white", label=c)
        for c in cols
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=ncol,
        fontsize=7.5,
        bbox_to_anchor=(0.5, y),
    )


# --------------------------------------------------------------------------- #
# discovery and loading
# --------------------------------------------------------------------------- #


def _discover_farms(
    grower_slugs: list[str] | None,
    weather_years: tuple[int, int],
) -> tuple[list[FarmSpec], list[str]]:
    warnings: list[str] = []
    if grower_slugs:
        grower_dirs = [GROWERS_ROOT / slug for slug in grower_slugs]
    else:
        grower_dirs = sorted(p for p in GROWERS_ROOT.iterdir() if p.is_dir())

    specs: list[FarmSpec] = []
    for grower_dir in grower_dirs:
        if not grower_dir.is_dir():
            warnings.append(f"grower not found: {grower_dir}")
            continue
        grower = grower_dir.name
        grower_name = str(_read_json(grower_dir / "grower.json").get("display_name") or grower)
        farms_dir = grower_dir / "farms"
        if not farms_dir.is_dir():
            warnings.append(f"no farms dir: {farms_dir}")
            continue
        for farm_dir in sorted(p for p in farms_dir.iterdir() if p.is_dir()):
            farm = farm_dir.name
            farm_name = str(_read_json(farm_dir / "farm.json").get("display_name") or farm)
            boundary = farm_boundary_path(grower, farm)
            weather = farm_weather_path(grower, farm, *weather_years)
            cdl = farm_cdl_preferred_full_composition_path(grower, farm)
            missing = [
                label
                for label, path in (("boundary", boundary), ("weather", weather), ("cdl", cdl))
                if not path.exists()
            ]
            if missing:
                warnings.append(
                    f"skip {grower}/{farm}: missing {', '.join(missing)}"
                )
                continue
            specs.append(
                FarmSpec(
                    grower_slug=grower,
                    farm_slug=farm,
                    grower_name=grower_name,
                    farm_name=farm_name,
                    boundary=boundary,
                    weather=weather,
                    cdl=cdl,
                )
            )
    return specs, warnings


def _load_fields(spec: FarmSpec) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(spec.boundary, engine="pyogrio")
    gdf["field_id"] = gdf["field_id"].astype(str)
    # The boundary layer's own `crop` is the CSB selection-year attribute, not
    # CDL. Rename it so it can never be confused with cdl_2023_dominant.
    if "crop" in gdf.columns:
        gdf = gdf.rename(columns={"crop": "csb_crop"})
    projected = gdf.to_crs("EPSG:5070")
    gdf["area_ha"] = projected.geometry.area / 10000.0
    gdf["perimeter_m"] = projected.geometry.length
    gdf["compactness"] = (
        4.0 * np.pi * gdf["area_ha"] * 10000.0 / gdf["perimeter_m"].pow(2)
    )
    centroids = projected.geometry.centroid.to_crs("EPSG:4326")
    gdf["centroid_lon"] = centroids.x.to_numpy()
    gdf["centroid_lat"] = centroids.y.to_numpy()
    farm_centre = projected.geometry.union_all().centroid
    centre_wgs84 = (
        gpd.GeoSeries([farm_centre], crs=projected.crs).to_crs("EPSG:4326").iloc[0]
    )
    planar_centre = projected.geometry.union_all().centroid
    gdf["distance_to_farm_centroid_km"] = (
        projected.geometry.centroid.distance(planar_centre) / 1000.0
    )
    gdf["grower_slug"] = spec.grower_slug
    gdf["farm_slug"] = spec.farm_slug
    gdf["grower_name"] = spec.grower_name
    gdf["farm_name"] = spec.farm_name
    gdf["farm_centroid_lon"] = centre_wgs84.x
    gdf["farm_centroid_lat"] = centre_wgs84.y
    return gdf


def _load_weather(spec: FarmSpec, years: tuple[int, int]) -> pd.DataFrame:
    frame = pd.read_csv(spec.weather, parse_dates=["date"])
    frame = frame[frame["date"].dt.year.between(years[0], years[1])].copy()
    frame["field_id"] = frame["field_id"].astype(str)
    frame["grower_slug"] = spec.grower_slug
    frame["farm_slug"] = spec.farm_slug
    return frame


def _load_cdl(spec: FarmSpec, years: tuple[int, int]) -> pd.DataFrame:
    frame = pd.read_csv(spec.cdl)
    frame = frame[frame["year"].between(years[0], years[1])].copy()
    frame["field_id"] = frame["field_id"].astype(str)
    frame["grower_slug"] = spec.grower_slug
    frame["farm_slug"] = spec.farm_slug
    return frame


# --------------------------------------------------------------------------- #
# derived metrics
# --------------------------------------------------------------------------- #


def _weather_cells(
    weather: pd.DataFrame,
) -> tuple[pd.Series, dict[tuple[str, str], int]]:
    def signature(frame: pd.DataFrame) -> str:
        ordered = frame.sort_values("date")
        array = np.ascontiguousarray(ordered[WEATHER_COLS].to_numpy(dtype="float64"))
        return hashlib.sha1(array.tobytes()).hexdigest()[:12]

    raw = {
        field_id: signature(group)
        for field_id, group in weather.groupby("field_id", sort=True)
    }
    unique_order: list[str] = []
    for field_id in sorted(raw, key=_field_sort_key):
        if raw[field_id] not in unique_order:
            unique_order.append(raw[field_id])
    labels = {value: f"C{index + 1}" for index, value in enumerate(unique_order)}
    per_field = pd.Series(
        {field_id: labels[value] for field_id, value in raw.items()}, name="weather_cell"
    )
    owner = weather.drop_duplicates("field_id").set_index("field_id")["grower_slug"]
    joined = per_field.to_frame("weather_cell").join(owner, how="left")
    counts = joined.groupby(["grower_slug", "weather_cell"], sort=True).size()
    sizes = {
        (str(grower), str(cell)): int(count) for (grower, cell), count in counts.items()
    }
    return per_field, sizes


def _field_year_weather(weather: pd.DataFrame, cells: pd.Series) -> pd.DataFrame:
    frame = weather.copy()
    frame["year"] = frame["date"].dt.year
    frame["gdd"] = np.maximum(
        (frame["T2M_MAX"] + frame["T2M_MIN"]) / 2.0 - GDD_BASE_C, 0.0
    )
    season = frame[
        frame["date"].dt.month.between(SEASON_MONTHS[0], SEASON_MONTHS[1])
    ]
    grouped = frame.groupby(["grower_slug", "field_id", "year"], sort=True)
    seasonal = season.groupby(["grower_slug", "field_id", "year"], sort=True)
    out = pd.DataFrame(
        {
            "annual_precip_mm": grouped["PRECTOTCORR"].sum(),
            "gdd_total": grouped["gdd"].sum(),
            "mean_t2m_c": grouped["T2M"].mean(),
        }
    )
    out["seasonal_precip_mm"] = seasonal["PRECTOTCORR"].sum()
    out["seasonal_gdd"] = seasonal["gdd"].sum()
    out = out.reset_index()
    out["weather_cell"] = out["field_id"].map(cells)
    return out


def _gdd_curves(weather: pd.DataFrame, cells: pd.Series, years: tuple[int, int]) -> pd.DataFrame:
    frame = weather[
        weather["date"].dt.month.between(SEASON_MONTHS[0], SEASON_MONTHS[1])
    ].copy()
    frame["year"] = frame["date"].dt.year
    frame["doy"] = frame["date"].dt.day_of_year
    frame["gdd"] = np.maximum(
        (frame["T2M_MAX"] + frame["T2M_MIN"]) / 2.0 - GDD_BASE_C, 0.0
    )
    frame = frame.sort_values(["field_id", "date"])
    frame["cum_gdd"] = frame.groupby("field_id", sort=False)["gdd"].cumsum()
    frame["weather_cell"] = frame["field_id"].map(cells)
    per_cell = frame.drop_duplicates(
        subset=["grower_slug", "weather_cell", "year", "doy"]
    )
    curves = (
        per_cell.groupby(["grower_slug", "weather_cell", "year", "doy"], sort=True)[
            "cum_gdd"
        ]
        .agg(["min", "max"])
        .reset_index()
        .rename(columns={"min": "cum_gdd_min", "max": "cum_gdd_max"})
    )
    mean = (
        per_cell.groupby(["grower_slug", "year", "doy"], sort=True)["cum_gdd"]
        .mean()
        .reset_index()
        .rename(columns={"cum_gdd": "cum_gdd_mean"})
    )
    return curves.merge(mean, on=["grower_slug", "year", "doy"], how="left")


def _dominant(cdl: pd.DataFrame) -> pd.DataFrame:
    index = cdl.groupby(["grower_slug", "field_id", "year"], sort=True)["pct"].idxmax()
    dominant = cdl.loc[
        index, ["grower_slug", "field_id", "year", "crop_name", "pct"]
    ].rename(columns={"crop_name": "dominant_crop", "pct": "dominant_pct"})
    return dominant.reset_index(drop=True)


def _residual(cdl: pd.DataFrame) -> pd.Series:
    return 100.0 - cdl.groupby(["grower_slug", "field_id", "year"], sort=True)[
        "pct"
    ].sum()


def _transitions(dominant: pd.DataFrame, years: tuple[int, int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    year_list = list(range(years[0], years[1] + 1))
    for grower_slug, group in dominant.groupby("grower_slug", sort=True):
        pivot = group.pivot(index="field_id", columns="year", values="dominant_crop")
        pivot = pivot.reindex(columns=year_list)
        for first, second in zip(year_list[:-1], year_list[1:]):
            pairs = pivot[[first, second]].dropna()
            for (source, target), count in pairs.value_counts().items():
                rows.append(
                    {
                        "grower_slug": grower_slug,
                        "from_year": first,
                        "to_year": second,
                        "from_crop": source,
                        "to_crop": target,
                        "count": int(count),
                    }
                )
    pooled = dominant.pivot(index="field_id", columns="year", values="dominant_crop")
    pooled = pooled.reindex(columns=year_list)
    for first, second in zip(year_list[:-1], year_list[1:]):
        pairs = pooled[[first, second]].dropna()
        for (source, target), count in pairs.value_counts().items():
            rows.append(
                {
                    "grower_slug": "all",
                    "from_year": first,
                    "to_year": second,
                    "from_crop": source,
                    "to_crop": target,
                    "count": int(count),
                }
            )
    frame = pd.DataFrame(rows)
    frame["share_pct"] = (
        frame.groupby(["grower_slug", "from_year", "to_year"])["count"]
        .transform(lambda values: 100.0 * values / values.sum())
        .round(1)
    )
    return frame.sort_values(
        ["grower_slug", "from_year", "from_crop", "to_crop"]
    ).reset_index(drop=True)


def _field_metrics(
    fields: gpd.GeoDataFrame,
    dominant: pd.DataFrame,
    residual: pd.Series,
    cdl: pd.DataFrame,
    field_weather: pd.DataFrame,
    cells: pd.Series,
    cell_sizes: dict[str, int],
    cdl_year: int,
) -> pd.DataFrame:
    metrics = fields.drop(columns="geometry").copy()
    metrics["field_id"] = metrics["field_id"].astype(str)
    metrics["cdl_2023_dominant"] = None
    metrics["cdl_2023_dominant_pct"] = np.nan
    latest = dominant[dominant["year"] == cdl_year]
    for _, row in latest.iterrows():
        mask = metrics["field_id"] == row["field_id"]
        metrics.loc[mask, "cdl_2023_dominant"] = row["dominant_crop"]
        metrics.loc[mask, "cdl_2023_dominant_pct"] = float(row["dominant_pct"])
    residual_mean = residual.groupby(level=["grower_slug", "field_id"]).mean()
    metrics["cdl_residual_mean_pct"] = [
        float(residual_mean.get((row["grower_slug"], row["field_id"]), np.nan))
        for _, row in metrics.iterrows()
    ]
    distinct_classes = cdl.groupby(["grower_slug", "field_id"])["crop_name"].nunique()
    mix_shannon = (
        cdl.groupby(["grower_slug", "field_id", "year"])["pct"]
        .apply(_shannon)
        .groupby(level=["grower_slug", "field_id"])
        .mean()
    )
    rotation_distinct = dominant.groupby(["grower_slug", "field_id"])[
        "dominant_crop"
    ].nunique()
    rotation_shannon = dominant.groupby(["grower_slug", "field_id"])[
        "dominant_crop"
    ].apply(_sequence_shannon)
    metrics["cdl_distinct_classes"] = [
        int(distinct_classes.get((row["grower_slug"], row["field_id"]), 0))
        for _, row in metrics.iterrows()
    ]
    metrics["cdl_mix_shannon_mean"] = [
        float(mix_shannon.get((row["grower_slug"], row["field_id"]), np.nan))
        for _, row in metrics.iterrows()
    ]
    metrics["cdl_rotation_distinct"] = [
        int(rotation_distinct.get((row["grower_slug"], row["field_id"]), 0))
        for _, row in metrics.iterrows()
    ]
    metrics["cdl_rotation_shannon"] = [
        float(rotation_shannon.get((row["grower_slug"], row["field_id"]), np.nan))
        for _, row in metrics.iterrows()
    ]
    corn_years = (
        dominant[dominant["dominant_crop"] == "Corn"]
        .groupby(["grower_slug", "field_id"])
        .size()
    )
    soy_years = (
        dominant[dominant["dominant_crop"] == "Soybeans"]
        .groupby(["grower_slug", "field_id"])
        .size()
    )
    metrics["corn_years"] = [
        int(corn_years.get((row["grower_slug"], row["field_id"]), 0))
        for _, row in metrics.iterrows()
    ]
    metrics["soy_years"] = [
        int(soy_years.get((row["grower_slug"], row["field_id"]), 0))
        for _, row in metrics.iterrows()
    ]
    weather_summary = (
        field_weather.groupby(["grower_slug", "field_id"], sort=True)
        .agg(
            annual_precip_mean_mm=("annual_precip_mm", "mean"),
            seasonal_precip_mean_mm=("seasonal_precip_mm", "mean"),
            gdd_seasonal_mean=("seasonal_gdd", "mean"),
        )
        .reset_index()
    )
    metrics = metrics.merge(
        weather_summary, on=["grower_slug", "field_id"], how="left"
    )
    metrics["weather_cell"] = metrics["field_id"].map(cells)
    cell_key = (
        metrics["grower_slug"].astype(str) + "|" + metrics["weather_cell"].astype(str)
    )
    metrics["weather_cell_fields"] = cell_key.map(
        {f"{grower}|{cell}": count for (grower, cell), count in cell_sizes.items()}
    )
    metrics["_field_order"] = metrics["field_id"].map(
        lambda field_id: _field_sort_key(field_id)[1]
    )
    return (
        metrics.sort_values(["grower_slug", "_field_order"])
        .drop(columns="_field_order")
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #


def fig_boundary_size(
    metrics: pd.DataFrame, growers: list[dict], kruskal: dict, out: Path, dpi: int
) -> Path:
    fig, axes = _facet(len(growers), width=3.4, height=3.9)
    for ax, grower in zip(axes, growers):
        sub = metrics[metrics["grower_slug"] == grower["slug"]]
        sns.boxplot(
            data=sub, y="area_ha", color="#C6D4E6", width=0.45,
            showfliers=False, ax=ax,
        )
        sns.stripplot(data=sub, y="area_ha", color="#1F3B73", size=4, jitter=0.10, ax=ax)
        ax.set_title(
            f"{grower['label']}\nn={len(sub)} · median {sub['area_ha'].median():.0f} ha",
            fontsize=9,
        )
        ax.set_ylabel("Field area (ha)" if ax is axes[0] else "")
        ax.set_xlabel("")
        ax.margins(y=0.06)
    fig.suptitle(
        "Field size differs by grower (Kruskal–Wallis "
        f"H={kruskal['H']:.1f}, p={kruskal['p']:.3f}) — NE clusters near 200 ha; "
        "IL/IA spread wider",
        y=1.03,
    )
    fig.tight_layout()
    return _save(fig, out / "fig_boundary_size_distribution.png", dpi)


def fig_boundary_compactness(
    metrics: pd.DataFrame, growers: list[dict], kruskal: dict, out: Path, dpi: int
) -> Path:
    fig, axes = _facet(len(growers), width=3.4, height=3.9)
    for ax, grower in zip(axes, growers):
        sub = metrics[metrics["grower_slug"] == grower["slug"]]
        sns.boxplot(
            data=sub, y="compactness", color="#D8C6E6", width=0.45,
            showfliers=False, ax=ax,
        )
        sns.stripplot(data=sub, y="compactness", color="#5B2C6F", size=4, jitter=0.10, ax=ax)
        ax.set_title(
            f"{grower['label']}\nn={len(sub)} · median {sub['compactness'].median():.2f}",
            fontsize=9,
        )
        ax.set_ylabel("Compactness (4πA/P²)" if ax is axes[0] else "")
        ax.set_xlabel("")
        ax.margins(y=0.06)
    fig.suptitle(
        "Field shape regularity — distributions overlap; compactness does not "
        f"separate growers (H={kruskal['H']:.2f}, p={kruskal['p']:.2f})",
        y=1.03,
    )
    fig.tight_layout()
    return _save(fig, out / "fig_boundary_compactness.png", dpi)


def fig_boundary_area_vs_compactness(
    metrics: pd.DataFrame, growers: list[dict], correlation: pd.DataFrame, kruskal: dict,
    out: Path, dpi: int,
) -> Path:
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    for grower in growers:
        sub = metrics[metrics["grower_slug"] == grower["slug"]]
        row = correlation[correlation["scope"] == grower["slug"]].iloc[0]
        label = f"{grower['label']}  ρ={row['spearman_rho']:.2f}"
        ax.scatter(
            sub["area_ha"], sub["compactness"], s=44, alpha=0.85,
            color=grower["color"], edgecolor="white", linewidth=0.6, label=label,
        )
    pooled = correlation[correlation["scope"] == "pooled"].iloc[0]
    ax.set_xlabel("Field area (ha)")
    ax.set_ylabel("Compactness (4πA/P²)")
    ax.set_title("Does size predict shape, or do growers share one geometry range?")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.text(
        0.5, -0.03,
        f"pooled Spearman ρ={pooled['spearman_rho']:.2f} "
        f"(p={pooled['spearman_p']:.3f}) · compactness Kruskal–Wallis "
        f"H={kruskal['H']:.2f}, p={kruskal['p']:.2f}, ε²={kruskal['epsilon_squared']:.2f}\n"
        "→ weak size–shape link; compactness does not separate growers",
        ha="center", va="top", fontsize=8, color="#333333",
    )
    return _save(fig, out / "fig_boundary_area_vs_compactness.png", dpi)


def fig_boundary_field_locations(
    fields: gpd.GeoDataFrame, metrics: pd.DataFrame, growers: list[dict], out: Path, dpi: int
) -> Path:
    """County-scale location map.

    The 10 fields per grower are individually selected CSB polygons scattered
    across the county, not one contiguous farm. Labeling every polygon at this
    scale hides the fill colors and collides on adjacent fields, so ids are left
    to the companion charts; each panel states its true extent.
    """
    n = len(growers)
    fig, axes = plt.subplots(1, n, figsize=(4.9 * n, 5.6))
    if n == 1:
        axes = [axes]
    for ax, grower in zip(axes, growers):
        subset = fields[fields["grower_slug"] == grower["slug"]].to_crs("EPSG:5070")
        meta = metrics[metrics["grower_slug"] == grower["slug"]].set_index("field_id")
        colors = [
            CROP_COLORS.get(meta.loc[fid, "cdl_2023_dominant"], "#9E9E9E")
            for fid in subset["field_id"]
        ]
        subset.plot(ax=ax, color=colors, edgecolor="#1A1A1A", linewidth=1.0)
        minx, miny, maxx, maxy = subset.total_bounds
        width_km = (maxx - minx) / 1000.0
        height_km = (maxy - miny) / 1000.0
        pad_x = (maxx - minx) * 0.10
        pad_top = (maxy - miny) * 0.10
        pad_bottom = (maxy - miny) * 0.24
        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_bottom, maxy + pad_top)
        ax.set_aspect("equal", adjustable="datalim")
        # 10 km scale bar in the reserved strip below every field.
        bar_m = 10000.0
        x0 = minx - pad_x + (maxx - minx) * 0.04
        y0 = miny - pad_bottom * 0.55
        ax.plot([x0, x0 + bar_m], [y0, y0], color="#111111", lw=2.6,
                solid_capstyle="butt", zorder=5)
        ax.text(
            x0 + bar_m / 2.0, y0 + (maxy - miny) * 0.035, "10 km",
            ha="center", va="bottom", fontsize=7, color="#111111",
        )
        county = str(subset["county"].iloc[0])
        state = str(subset["state"].iloc[0])
        ax.set_title(
            f"{state} · {county} County\n{len(subset)} fields · "
            f"~{width_km:.0f} × {height_km:.0f} km extent",
            fontsize=9,
        )
        ax.axis("off")
        ax.grid(False)
    present = [
        crop for crop in CROP_ORDER
        if crop in set(metrics["cdl_2023_dominant"].dropna())
        and crop != "Other/unclassified"
    ]
    _add_crop_legend(fig, present, ncol=min(8, max(1, len(present))), y=-0.06)
    fig.text(
        0.5, -0.015,
        "Fields are individually selected across each county, not contiguous farm "
        "blocks; per-field ids and crops are in the companion charts and field_metrics.csv.",
        ha="center", fontsize=7.5, color="#555555",
    )
    fig.suptitle(
        "Field locations, county scale — fill = CDL 2023 dominant crop", y=1.02
    )
    fig.tight_layout()
    return _save(fig, out / "fig_boundary_field_locations.png", dpi)


def fig_cdl_composition(
    cdl: pd.DataFrame, growers: list[dict], cdl_year: int, out: Path, dpi: int
) -> Path:
    frame = cdl[cdl["year"] == cdl_year]
    pivot = frame.pivot_table(
        index=["grower_slug", "field_id"], columns="crop_name",
        values="pct", aggfunc="sum", fill_value=0.0,
    )
    pivot["Other/unclassified"] = (100.0 - pivot.sum(axis=1)).clip(lower=0.0)
    columns = [crop for crop in CROP_ORDER if crop in pivot.columns]
    columns += [crop for crop in pivot.columns if crop not in columns and pivot[crop].sum() > 0]
    fig, axes = _facet(len(growers), width=4.1, height=4.6, sharey=False)
    for ax, grower in zip(axes, growers):
        sub = pivot.loc[grower["slug"]].copy()
        sub["order"] = [_field_sort_key(fid)[1] for fid in sub.index]
        sub = sub.sort_values("order")
        left = np.zeros(len(sub))
        for crop in columns:
            values = sub[crop].to_numpy(dtype=float)
            if values.sum() <= 0:
                continue
            ax.barh(
                np.arange(len(sub)), values, left=left, height=0.74,
                color=CROP_COLORS.get(crop, "#9E9E9E"), label=crop,
                edgecolor="white", linewidth=0.4,
            )
            left += values
        ax.set_yticks(np.arange(len(sub)))
        ax.set_yticklabels(sub.index, fontsize=7.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_title(grower["label"])
        ax.set_xlabel("Share of field pixels (%)" if ax is axes[0] else "")
        ax.grid(axis="y", visible=False)
    present = [crop for crop in columns if pivot[crop].sum() > 0]
    _add_crop_legend(fig, present, ncol=min(8, max(1, len(present))), y=-0.10)
    fig.suptitle(
        f"CDL {cdl_year} crop mix per field — residual shown as Other/unclassified", y=1.02
    )
    fig.tight_layout()
    return _save(fig, out / "fig_cdl_composition_2023.png", dpi)


def fig_cdl_diversity(metrics: pd.DataFrame, growers: list[dict], out: Path, dpi: int) -> Path:
    fig, axes = _facet(len(growers), width=3.5, height=4.3, sharey=False)
    for ax, grower in zip(axes, growers):
        sub = metrics[metrics["grower_slug"] == grower["slug"]].copy()
        sub["order"] = sub["field_id"].map(lambda fid: _field_sort_key(fid)[1])
        sub = sub.sort_values("order")
        ax.barh(
            np.arange(len(sub)), sub["cdl_rotation_shannon"], height=0.68,
            color="#6A8CAF", edgecolor="white", linewidth=0.4,
        )
        for index, (_, row) in enumerate(sub.iterrows()):
            count = int(row["cdl_rotation_distinct"])
            ax.annotate(
                f"{count} crop{'s' if count != 1 else ''}",
                xy=(row["cdl_rotation_shannon"] + 0.03, index), va="center", fontsize=6.8,
                color="#333333",
            )
        ax.set_yticks(np.arange(len(sub)))
        ax.set_yticklabels(sub["field_id"], fontsize=7.5)
        ax.invert_yaxis()
        ax.set_xlim(
            0, max(1.0, float(metrics["cdl_rotation_shannon"].max()) + 0.45)
        )
        ax.set_title(grower["label"])
        ax.set_xlabel(
            "Shannon H′ of the 5-year dominant-crop sequence" if ax is axes[0] else ""
        )
        ax.grid(axis="y", visible=False)
    fig.suptitle(
        "Rotation diversity per field — low H′ means the same dominant crop most "
        "years", y=1.02,
    )
    fig.tight_layout()
    return _save(fig, out / "fig_cdl_diversity.png", dpi)


def fig_cdl_rotation(
    dominant: pd.DataFrame, growers: list[dict], years: tuple[int, int], out: Path, dpi: int
) -> Path:
    year_list = list(range(years[0], years[1] + 1))
    palette = [CROP_COLORS.get(crop, "#9E9E9E") for crop in CROP_ORDER] + ["#F2F2F2"]
    codes = {crop: index for index, crop in enumerate(CROP_ORDER)}
    cmap = ListedColormap(palette)
    fig, axes = _facet(len(growers), width=4.1, height=4.5, sharey=False)
    for ax, grower in zip(axes, growers):
        sub = dominant[dominant["grower_slug"] == grower["slug"]]
        pivot = sub.pivot(index="field_id", columns="year", values="dominant_crop")
        pivot = pivot.reindex(columns=year_list)
        pivot = pivot.loc[sorted(pivot.index, key=_field_sort_key)]
        matrix = np.array(
            [
                [codes.get(crop, len(CROP_ORDER)) for crop in row]
                for row in pivot.to_numpy()
            ],
            dtype=float,
        )
        ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=-0.5, vmax=len(CROP_ORDER) - 0.5)
        ax.set_xticks(range(len(year_list)))
        ax.set_xticklabels(year_list, fontsize=8)
        ax.set_yticks(range(len(pivot)))
        ax.set_yticklabels(pivot.index, fontsize=7.5)
        for row_index in range(matrix.shape[0]):
            for col_index in range(matrix.shape[1]):
                crop = pivot.iloc[row_index, col_index]
                if not isinstance(crop, str):
                    continue
                color = "white" if crop in DARK_TEXT_CROPS else "#111111"
                ax.text(
                    col_index, row_index, CROP_ABBR.get(crop, crop[:4]),
                    ha="center", va="center", fontsize=6.4, color=color,
                )
        ax.set_title(grower["label"])
        ax.grid(False)
    present = [
        crop for crop in CROP_ORDER
        if crop in set(dominant["dominant_crop"].dropna())
    ]
    _add_crop_legend(fig, present, ncol=min(8, max(1, len(present))), y=-0.04)
    fig.suptitle(
        f"Dominant CDL crop per field, {years[0]}–{years[1]} — within-field sequences", y=1.02
    )
    fig.tight_layout()
    return _save(fig, out / "fig_cdl_rotation_heatmap.png", dpi)


def fig_weather_annual_precip(
    field_weather: pd.DataFrame, growers: list[dict], out: Path, dpi: int
) -> Path:
    fig, axes = _facet(len(growers), width=3.9, height=4.0, sharey=True)
    for ax, grower in zip(axes, growers):
        sub = field_weather[field_weather["grower_slug"] == grower["slug"]]
        cells = sub["weather_cell"].nunique()
        sns.boxplot(
            data=sub, x="year", y="annual_precip_mm", color="#BFD3E6",
            width=0.55, showfliers=False, ax=ax,
        )
        sns.stripplot(
            data=sub, x="year", y="annual_precip_mm", color="#1F4E79",
            size=3.4, jitter=0.14, ax=ax,
        )
        ax.set_title(
            f"{grower['label']}\n{len(sub['field_id'].unique())} fields · "
            f"{cells} POWER cells",
            fontsize=9,
        )
        ax.set_xlabel("")
        ax.set_ylabel("Annual precipitation (mm)" if ax is axes[0] else "")
        ax.margins(y=0.08)
    fig.suptitle(
        "Annual water supply by field — points within a year share POWER cells", y=1.02
    )
    fig.tight_layout()
    return _save(fig, out / "fig_weather_annual_precip.png", dpi)


def fig_weather_gdd(
    curves: pd.DataFrame, growers: list[dict], years: tuple[int, int], out: Path, dpi: int
) -> Path:
    year_list = list(range(years[0], years[1] + 1))
    colors = matplotlib.colormaps["viridis"](np.linspace(0.08, 0.88, len(year_list)))
    fig, axes = _facet(len(growers), width=3.9, height=4.0, sharey=True)
    for ax, grower in zip(axes, growers):
        sub = curves[curves["grower_slug"] == grower["slug"]]
        for year, color in zip(year_list, colors):
            series = sub[sub["year"] == year].sort_values("doy")
            if series.empty:
                continue
            ax.plot(series["doy"], series["cum_gdd_mean"], lw=1.7, color=color, label=str(year))
            ax.fill_between(
                series["doy"], series["cum_gdd_min"], series["cum_gdd_max"],
                color=color, alpha=0.14, linewidth=0,
            )
        cell_count = sub["weather_cell"].nunique()
        ax.set_title(grower["label"])
        ax.set_xlabel("Day of year (Apr–Sep)" if ax is axes[0] else "")
        ax.set_ylabel("Cumulative GDD (°C-day)" if ax is axes[0] else "")
        ax.annotate(
            f"mean across {cell_count} POWER cells; band = min–max",
            xy=(0.02, 0.93), xycoords="axes fraction", fontsize=7,
            color="#444444",
        )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(year_list),
               fontsize=7.5, title="Year", bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(
        f"Cumulative GDD (base {GDD_BASE_C:.0f} °C, mean method), {years[0]}–{years[1]}", y=1.02
    )
    fig.tight_layout()
    return _save(fig, out / "fig_weather_gdd_curves.png", dpi)


def fig_weather_crop_link(
    link: pd.DataFrame, growers: list[dict], stats_summary: dict, out: Path, dpi: int
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.8))
    specs = [
        (axes[0], "seasonal_precip_mm", "precip_p",
         "Seasonal (Apr–Sep) precipitation (mm)", "Water supply by crop year"),
        (axes[1], "seasonal_gdd", "gdd_p",
         "Seasonal GDD (°C-day)", "Heat accumulation by crop year"),
    ]
    for ax, column, p_key, ylabel, title in specs:
        hue_order = [grower["label"] for grower in growers]
        sns.boxplot(
            data=link, x="crop", y=column, hue="grower_label", hue_order=hue_order,
            width=0.62, showfliers=False, ax=ax, palette="Set2",
        )
        sns.stripplot(
            data=link, x="crop", y=column, hue="grower_label", hue_order=hue_order,
            dodge=True, size=3.2, alpha=0.7, jitter=0.12, ax=ax, legend=False,
        )
        pooled_p = stats_summary["pooled"][p_key]
        ax.set_title(
            f"{title}\nMann–Whitney corn vs soy: p={pooled_p:.2f} "
            f"(n={stats_summary['pooled']['n_corn']}/{stats_summary['pooled']['n_soy']})",
            fontsize=9,
        )
        ax.set_xlabel("CDL dominant crop")
        ax.set_ylabel(ylabel)
        if ax.get_legend() is not None:
            ax.get_legend().remove()
        ax.margins(y=0.06)
    palette = sns.color_palette("Set2", len(growers))
    handles = [
        Patch(facecolor=palette[index], edgecolor="white", label=grower["label"])
        for index, grower in enumerate(growers)
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(growers),
               fontsize=8, bbox_to_anchor=(0.5, -0.05))
    pooled = stats_summary["pooled"]
    fig.suptitle(
        "Crop-year weather, 2021–2023 — no significant corn-vs-soy difference; "
        f"field points pseudo-replicated across {pooled['n_cells']} POWER cells",
        y=1.02,
    )
    fig.tight_layout()
    return _save(fig, out / "fig_weather_crop_link.png", dpi)


# --------------------------------------------------------------------------- #
# analysis tables
# --------------------------------------------------------------------------- #


def _boundary_correlation(metrics: pd.DataFrame, growers: list[dict]) -> pd.DataFrame:
    rows = []
    scopes = [(grower["slug"], grower["label"]) for grower in growers] + [("pooled", "All growers")]
    for scope, label in scopes:
        sub = metrics if scope == "pooled" else metrics[metrics["grower_slug"] == scope]
        if len(sub) < 3 or sub["compactness"].nunique() < 2:
            rho, p_value = float("nan"), float("nan")
        else:
            rho, p_value = stats.spearmanr(sub["area_ha"], sub["compactness"])
        rows.append(
            {
                "scope": scope,
                "label": label,
                "n_fields": int(len(sub)),
                "spearman_rho": round(float(rho), 4) if np.isfinite(rho) else None,
                "spearman_p": round(float(p_value), 4) if np.isfinite(p_value) else None,
            }
        )
    return pd.DataFrame(rows)


def _kruskal(metrics: pd.DataFrame, column: str, growers: list[dict]) -> dict:
    groups = [
        metrics.loc[metrics["grower_slug"] == grower["slug"], column].to_numpy(dtype=float)
        for grower in growers
    ]
    groups = [group for group in groups if len(group) > 0]
    if len(groups) < 2:
        return {"H": float("nan"), "p": float("nan"), "epsilon_squared": float("nan")}
    result = stats.kruskal(*groups)
    k = len(groups)
    n = sum(len(group) for group in groups)
    epsilon = (result.statistic - k + 1) / max(n - k, 1)
    return {
        "H": float(result.statistic),
        "p": float(result.pvalue),
        "epsilon_squared": float(epsilon),
    }


def _weather_crop_link(
    field_weather: pd.DataFrame, dominant: pd.DataFrame, cdl_years: tuple[int, int],
    growers: list[dict],
) -> tuple[pd.DataFrame, dict]:
    years = sorted(
        set(field_weather["year"].unique())
        & set(dominant["year"].unique())
    )
    years = [int(year) for year in years if cdl_years[0] <= year <= cdl_years[1]]
    crop_lookup = dominant.set_index(["field_id", "year"])["dominant_crop"]
    link = field_weather[field_weather["year"].isin(years)].copy()
    link["crop"] = [
        crop_lookup.get((row["field_id"], row["year"]), None)
        for _, row in link.iterrows()
    ]
    link = link[link["crop"].isin(["Corn", "Soybeans"])].copy()

    def compare(subset: pd.DataFrame) -> dict:
        corn = subset[subset["crop"] == "Corn"]
        soy = subset[subset["crop"] == "Soybeans"]
        if len(corn) < 2 or len(soy) < 2:
            return {
                "n_corn": int(len(corn)),
                "n_soy": int(len(soy)),
                "precip_u": None,
                "precip_p": None,
                "gdd_u": None,
                "gdd_p": None,
            }
        precip = stats.mannwhitneyu(corn["seasonal_precip_mm"], soy["seasonal_precip_mm"])
        gdd = stats.mannwhitneyu(corn["seasonal_gdd"], soy["seasonal_gdd"])
        return {
            "n_corn": int(len(corn)),
            "n_soy": int(len(soy)),
            "precip_u": float(precip.statistic),
            "precip_p": float(precip.pvalue),
            "gdd_u": float(gdd.statistic),
            "gdd_p": float(gdd.pvalue),
        }

    summary = {
        grower["slug"]: {
            **compare(link[link["grower_slug"] == grower["slug"]]),
            "n_cells": int(
                link.loc[link["grower_slug"] == grower["slug"], "weather_cell"].nunique()
            ),
        }
        for grower in growers
    }
    summary["pooled"] = {
        **compare(link),
        "n_cells": int(
            link[["grower_slug", "weather_cell"]].drop_duplicates().shape[0]
        ),
    }
    link = link.sort_values(["grower_slug", "field_id", "year"]).reset_index(drop=True)
    return link, summary


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root; defaults to $DATA_PIPELINE_DATA_ROOT",
    )
    parser.add_argument(
        "--growers", nargs="*", default=None,
        help="Grower slugs to include, in display order; default is every grower with all three layers",
    )
    parser.add_argument(
        "--cdl-years", nargs=2, type=int, metavar=("START", "END"), default=[2019, 2023]
    )
    parser.add_argument(
        "--weather-years", nargs=2, type=int, metavar=("START", "END"), default=[2021, 2025]
    )
    parser.add_argument(
        "--cdl-year", type=int, default=None,
        help="Year used for the composition/map snapshot; default is the last CDL year",
    )
    parser.add_argument("--run-name", default="default", help="Output subdirectory name")
    parser.add_argument(
        "--out-dir", default=None,
        help="Absolute output directory; overrides the runtime default",
    )
    parser.add_argument("--dpi", type=int, default=200, help="PNG resolution (default 200)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cdl_years = (min(args.cdl_years), max(args.cdl_years))
    weather_years = (min(args.weather_years), max(args.weather_years))
    cdl_year = args.cdl_year or cdl_years[1]
    if not (cdl_years[0] <= cdl_year <= cdl_years[1]):
        raise SystemExit(f"--cdl-year {cdl_year} is outside the CDL window {cdl_years}")

    _style()
    np.random.seed(0)

    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else (DATA_ROOT / "eda" / "field-eda" / "output" / args.run_name)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    specs, warnings = _discover_farms(args.growers, weather_years)
    if not specs:
        for warning in warnings:
            print(f"WARN {warning}", file=sys.stderr)
        raise SystemExit("no farm has boundary + weather + CDL outputs")

    field_frames: list[gpd.GeoDataFrame] = []
    weather_frames: list[pd.DataFrame] = []
    cdl_frames: list[pd.DataFrame] = []
    inputs = []
    for spec in specs:
        fields = _load_fields(spec)
        weather = _load_weather(spec, weather_years)
        cdl = _load_cdl(spec, cdl_years)
        field_frames.append(fields)
        weather_frames.append(weather)
        cdl_frames.append(cdl)
        inputs.extend(
            [
                {
                    "kind": "boundary",
                    "grower_slug": spec.grower_slug,
                    "farm_slug": spec.farm_slug,
                    "path": _rel(spec.boundary),
                    "sha256": _sha256(spec.boundary),
                    "rows": int(len(fields)),
                },
                {
                    "kind": "weather",
                    "grower_slug": spec.grower_slug,
                    "farm_slug": spec.farm_slug,
                    "path": _rel(spec.weather),
                    "sha256": _sha256(spec.weather),
                    "rows": int(len(weather)),
                },
                {
                    "kind": "cdl",
                    "grower_slug": spec.grower_slug,
                    "farm_slug": spec.farm_slug,
                    "path": _rel(spec.cdl),
                    "sha256": _sha256(spec.cdl),
                    "rows": int(len(cdl)),
                },
            ]
        )

    fields = gpd.GeoDataFrame(
        pd.concat(field_frames, ignore_index=True),
        geometry="geometry",
        crs=field_frames[0].crs,
    )
    weather = pd.concat(weather_frames, ignore_index=True)
    cdl = pd.concat(cdl_frames, ignore_index=True)
    if fields["field_id"].duplicated().any():
        duplicated = sorted(fields.loc[fields["field_id"].duplicated(), "field_id"].unique())
        raise SystemExit(
            "field_id is not unique across the selected farms: " + ", ".join(duplicated)
        )

    states = (
        fields.groupby("grower_slug", sort=True)["state"]
        .agg(lambda values: str(values.dropna().iloc[0]) if not values.dropna().empty else "")
        .to_dict()
    )
    grower_slugs = list(dict.fromkeys(fields["grower_slug"]))
    growers = [
        {
            "slug": slug,
            "state": states.get(slug, ""),
            "label": f"{states.get(slug, '') or '??'} · {slug}",
            "color": GROWER_COLORS[index % len(GROWER_COLORS)],
        }
        for index, slug in enumerate(grower_slugs)
    ]

    cells, cell_sizes = _weather_cells(weather)
    field_weather = _field_year_weather(weather, cells)
    curves = _gdd_curves(weather, cells, weather_years)
    dominant = _dominant(cdl)
    residual = _residual(cdl)
    transitions = _transitions(dominant, cdl_years)
    metrics = _field_metrics(
        fields, dominant, residual, cdl, field_weather, cells, cell_sizes, cdl_year
    )
    metrics["grower_label"] = metrics["grower_slug"].map(
        {grower["slug"]: grower["label"] for grower in growers}
    )
    grower_rank = {grower["slug"]: index for index, grower in enumerate(growers)}
    metrics = (
        metrics.assign(
            _grower_rank=metrics["grower_slug"].map(grower_rank),
            _field_rank=metrics["field_id"].map(lambda fid: _field_sort_key(fid)[1]),
        )
        .sort_values(["_grower_rank", "_field_rank"])
        .drop(columns=["_grower_rank", "_field_rank"])
        .reset_index(drop=True)
    )

    correlation = _boundary_correlation(metrics, growers)
    kruskal_area = _kruskal(metrics, "area_ha", growers)
    kruskal_compactness = _kruskal(metrics, "compactness", growers)
    link, link_stats = _weather_crop_link(field_weather, dominant, cdl_years, growers)
    link["grower_label"] = link["grower_slug"].map(
        {grower["slug"]: grower["label"] for grower in growers}
    )

    metrics.to_csv(out_dir / "field_metrics.csv", index=False)
    correlation.to_csv(out_dir / "analysis_boundary_correlation.csv", index=False)
    transitions.to_csv(out_dir / "analysis_cdl_transitions.csv", index=False)
    link.to_csv(out_dir / "analysis_weather_crop_link.csv", index=False)

    fig_boundary_size(metrics, growers, kruskal_area, out_dir, args.dpi)
    fig_boundary_compactness(metrics, growers, kruskal_compactness, out_dir, args.dpi)
    fig_boundary_area_vs_compactness(
        metrics, growers, correlation, kruskal_compactness, out_dir, args.dpi
    )
    fig_boundary_field_locations(fields, metrics, growers, out_dir, args.dpi)
    fig_cdl_composition(cdl, growers, cdl_year, out_dir, args.dpi)
    fig_cdl_diversity(metrics, growers, out_dir, args.dpi)
    fig_cdl_rotation(dominant, growers, cdl_years, out_dir, args.dpi)
    fig_weather_annual_precip(field_weather, growers, out_dir, args.dpi)
    fig_weather_gdd(curves, growers, weather_years, out_dir, args.dpi)
    fig_weather_crop_link(link, growers, link_stats, out_dir, args.dpi)

    max_residual = float((100.0 - cdl.groupby(["grower_slug", "field_id", "year"])["pct"].sum()).max())
    manifest = {
        "action": "field_eda",
        "generator": "src/scripts/reporting/generate_field_eda.py",
        "output_dir": str(out_dir),
        "parameters": {
            "growers": grower_slugs,
            "cdl_years": list(cdl_years),
            "cdl_snapshot_year": cdl_year,
            "weather_years": list(weather_years),
            "dpi": args.dpi,
            "gdd_base_c": GDD_BASE_C,
            "season_months": list(SEASON_MONTHS),
        },
        "inputs": inputs,
        "farms": [
            {
                "grower_slug": grower["slug"],
                "grower_label": grower["label"],
                "state": grower["state"],
                "fields": int((metrics["grower_slug"] == grower["slug"]).sum()),
                "weather_cells": int(field_weather.loc[field_weather["grower_slug"] == grower["slug"], "weather_cell"].nunique()),
                "cell_field_counts": {
                    cell: int(count)
                    for (grower_slug, cell), count in cell_sizes.items()
                    if grower_slug == grower["slug"]
                },
            }
            for grower in growers
        ],
        "artifacts": [
            {**artifact, "path": str(out_dir / artifact["file"])} for artifact in ARTIFACTS
        ],
        "statistics": {
            "boundary_area_kruskal": kruskal_area,
            "boundary_compactness_kruskal": kruskal_compactness,
            "boundary_spearman": correlation.to_dict(orient="records"),
            "weather_crop_link": link_stats,
            "cdl_max_residual_pct": round(max_residual, 2),
        },
        "caveats": CAVEATS,
        "warnings": warnings,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    missing = [
        artifact["file"]
        for artifact in ARTIFACTS
        if not (out_dir / artifact["file"]).exists()
    ]
    if missing:
        raise SystemExit("artifact check failed; missing: " + ", ".join(missing))

    print(
        json.dumps(
            {
                "action": "field_eda",
                "output_dir": str(out_dir),
                "farms": manifest["farms"],
                "artifacts": len(ARTIFACTS),
                "warnings": warnings,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())