#!/usr/bin/env python3
"""Build the one-time Assignment 2 field EDA report PDF.

This script is intentionally outside the reusable field-eda subskill. It reads
the static artifacts produced by ``generate_field_eda.py`` and writes a compact
two-page PDF brief. The generated PDF is committed for the assignment review;
the underlying figures and tables remain runtime artifacts.

Usage:
    uv run --with reportlab --with pillow python generate_assignment_2_report.py \
        --output-dir /path/to/assignment-2 \
        --pdf /path/to/assignment-2-field-eda-report.pdf

The output directory must contain ``manifest.json`` and ``field_metrics.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

PAGE_W, PAGE_H = letter
MARGIN = 36
CONTENT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Palette and typography
# ---------------------------------------------------------------------------

NAVY = HexColor("#1F4E79")
GOLD = HexColor("#B07A1E")
GREEN = HexColor("#2E8B57")
INK = HexColor("#1A1A1A")
MUTED = HexColor("#555555")
RULE = HexColor("#D0D7DE")
LIGHT = HexColor("#F3F5F8")
WHITE = HexColor("#FFFFFF")
PALE_BLUE = HexColor("#EAF1F7")


def _register_fonts() -> tuple[str, str]:
    """Register a Unicode-capable font, with a safe Helvetica fallback."""
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(
            "/home/coder/my-farm-advisor-runtime/data-pipeline/.venv/lib/"
            "python3.12/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
        ),
    ]
    for base in candidates:
        if base.exists():
            bold = base.with_name("DejaVuSans-Bold.ttf")
            if bold.exists():
                pdfmetrics.registerFont(TTFont("ReportSans", str(base)))
                pdfmetrics.registerFont(TTFont("ReportSans-Bold", str(bold)))
                return "ReportSans", "ReportSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


def _styles():
    from reportlab.lib.styles import ParagraphStyle

    return {
        "title": ParagraphStyle(
            "title",
            fontName=FONT_BOLD,
            fontSize=19,
            leading=22,
            textColor=WHITE,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=FONT,
            fontSize=9.2,
            leading=11.5,
            textColor=HexColor("#DCE7F2"),
        ),
        "meta": ParagraphStyle(
            "meta",
            fontName=FONT,
            fontSize=7.4,
            leading=9.2,
            textColor=HexColor("#C9D9E8"),
        ),
        "h": ParagraphStyle(
            "h",
            fontName=FONT_BOLD,
            fontSize=9.4,
            leading=11.2,
            textColor=NAVY,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=FONT,
            fontSize=7.8,
            leading=9.5,
            textColor=INK,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName=FONT,
            fontSize=7.7,
            leading=9.4,
            textColor=INK,
            leftIndent=9,
            bulletIndent=0,
            spaceAfter=2.0,
        ),
        "bullet_small": ParagraphStyle(
            "bullet_small",
            fontName=FONT,
            fontSize=7.0,
            leading=8.6,
            textColor=INK,
            leftIndent=9,
            bulletIndent=0,
            spaceAfter=2.0,
        ),
        "small": ParagraphStyle(
            "small",
            fontName=FONT,
            fontSize=7.0,
            leading=8.7,
            textColor=MUTED,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName=FONT,
            fontSize=6.9,
            leading=8.5,
            textColor=MUTED,
        ),
        "table": ParagraphStyle(
            "table",
            fontName=FONT,
            fontSize=6.9,
            leading=8.1,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "table_head",
            fontName=FONT_BOLD,
            fontSize=6.8,
            leading=8.0,
            textColor=WHITE,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName=FONT,
            fontSize=6.4,
            leading=7.8,
            textColor=MUTED,
        ),
    }


STYLES = _styles()


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def draw_paragraph(
    c: canvas.Canvas,
    text: str,
    style,
    x: float,
    y_top: float,
    width: float,
) -> float:
    p = Paragraph(text, style)
    _, h = p.wrapOn(c, width, 1000)
    p.drawOn(c, x, y_top - h)
    return y_top - h


def draw_bullets(
    c: canvas.Canvas,
    items: list[str],
    x: float,
    y_top: float,
    width: float,
    style,
) -> float:
    y = y_top
    for item in items:
        p = Paragraph(item, style, bulletText="•")
        _, h = p.wrapOn(c, width, 1000)
        p.drawOn(c, x, y - h)
        y -= h + 2.0
    return y


def draw_heading(c: canvas.Canvas, text: str, x: float, y_top: float, width: float) -> float:
    p = Paragraph(text, STYLES["h"])
    _, h = p.wrapOn(c, width, 1000)
    p.drawOn(c, x, y_top - h)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(x, y_top - h - 2.5, x + width, y_top - h - 2.5)
    return y_top - h - 7


def draw_box(
    c: canvas.Canvas,
    title: str,
    items: list[str],
    x: float,
    y_top: float,
    width: float,
    height: float,
    accent: HexColor = NAVY,
) -> float:
    c.setFillColor(LIGHT)
    c.rect(x, y_top - height, width, height, stroke=0, fill=1)
    c.setFillColor(accent)
    c.rect(x, y_top - height, 3.2, height, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont(FONT_BOLD, 8.6)
    c.drawString(x + 9, y_top - 12, title)
    draw_bullets(c, items, x + 9, y_top - 22, width - 18, STYLES["bullet"])
    return y_top - height


def draw_table(
    c: canvas.Canvas,
    rows: list[list[str]],
    col_widths: list[float],
    x: float,
    y_top: float,
) -> float:
    data = []
    for row_index, row in enumerate(rows):
        style = STYLES["table_head"] if row_index == 0 else STYLES["table"]
        data.append([Paragraph(str(cell), style) for cell in row])
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 6.9),
                ("LEADING", (0, 0), (-1, -1), 8.1),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4.0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4.0),
            ]
        )
    )
    _, h = table.wrapOn(c, sum(col_widths), 1000)
    table.drawOn(c, x, y_top - h)
    return y_top - h


def draw_figure(
    c: canvas.Canvas,
    image_path: Path,
    x: float,
    y_top: float,
    width: float,
    caption: str,
) -> float:
    with Image.open(image_path) as im:
        aspect = im.width / im.height
    height = width / aspect
    c.drawImage(
        ImageReader(str(image_path)),
        x,
        y_top - height,
        width=width,
        height=height,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.rect(x, y_top - height, width, height, stroke=1, fill=0)
    cap = Paragraph(caption, STYLES["caption"])
    _, cap_h = cap.wrapOn(c, width, 1000)
    cap.drawOn(c, x, y_top - height - cap_h - 3)
    return y_top - height - cap_h - 7


def crop_figure(src: Path, dst: Path, max_width: int = 1400) -> Path:
    """Trim white margins and convert to a compact JPEG for the PDF."""
    im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        pad = 12
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(im.width, bbox[2] + pad)
        bottom = min(im.height, bbox[3] + pad)
        im = im.crop((left, top, right, bottom))
    if im.width > max_width:
        ratio = max_width / im.width
        im = im.resize((max_width, int(im.height * ratio)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=84, optimize=True)
    return dst


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def load_data(output_dir: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    with (output_dir / "field_metrics.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return manifest, rows


def grower_stats(manifest: dict, rows: list[dict]) -> list[dict]:
    by_slug: dict[str, list[dict]] = {}
    for row in rows:
        by_slug.setdefault(row["grower_slug"], []).append(row)

    ordered = []
    for farm in manifest["farms"]:
        slug = farm["grower_slug"]
        group = by_slug.get(slug, [])
        if not group:
            continue
        ordered.append(
            {
                "label": farm["grower_label"],
                "state": farm["state"],
                "fields": len(group),
                "median_area": statistics.median(float(r["area_ha"]) for r in group),
                "median_compactness": statistics.median(
                    float(r["compactness"]) for r in group
                ),
                "mean_rotation_h": statistics.mean(
                    float(r["cdl_rotation_shannon"]) for r in group
                ),
                "monocultures": sum(
                    1 for r in group if float(r["cdl_rotation_shannon"]) == 0.0
                ),
                "median_precip": statistics.median(
                    float(r["seasonal_precip_mean_mm"]) for r in group
                ),
                "median_gdd": statistics.median(
                    float(r["gdd_seasonal_mean"]) for r in group
                ),
                "cells": len({r["weather_cell"] for r in group}),
            }
        )
    return ordered


def fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


# ---------------------------------------------------------------------------
# Report pages
# ---------------------------------------------------------------------------


def page_one(
    c: canvas.Canvas,
    stats: list[dict],
    manifest: dict,
    figures: dict[str, Path],
) -> None:
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 100, PAGE_W, 100, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 19)
    c.drawString(MARGIN, PAGE_H - 42, "Field-Level EDA — Assignment 2")
    c.setFont(FONT, 9.2)
    c.setFillColor(HexColor("#DCE7F2"))
    c.drawString(
        MARGIN,
        PAGE_H - 60,
        "Boundaries, CDL/cropland, and weather across Illinois, Iowa, and Nebraska growers",
    )
    c.setFont(FONT, 7.4)
    c.setFillColor(HexColor("#C9D9E8"))
    c.drawString(
        MARGIN,
        PAGE_H - 77,
        "30 fields  ·  3 growers  ·  run assignment-2  ·  report 24 November 2026",
    )
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - 104, PAGE_W, 4, stroke=0, fill=1)

    y = PAGE_H - 118

    # Scope and key findings, two columns.
    scope_items = [
        "Growers: IL — Iroquois County; IA — Kossuth County; NE — York County. 10 individually selected CSB polygons each, scattered across the county, not one contiguous farm.",
        "Layers: field boundaries; CDL 2019–2023; NASA POWER weather 2021–2025. No soil, terrain, imagery, or NDVI was read.",
        "Comparison levels: field; field-year; grower; across-grower.",
        "Soil analysis is not required and was not the focus.",
    ]
    finding_items = [
        "Field area differs by grower; compactness does not.",
        "The area–shape link is weak and pooled; IA drives it, NE shows none.",
        "Rotation is mostly strict corn–soy; four fields are monocultures.",
        "NE is driest; the corn-vs-soy weather comparison is exploratory.",
    ]
    draw_box(c, "Scope & data", scope_items, MARGIN, y, 300, 110, NAVY)
    draw_box(c, "Key findings", finding_items, MARGIN + 312, y, 228, 110, GREEN)
    y -= 110

    # Grower snapshot table.
    y -= 10
    c.setFont(FONT_BOLD, 8.6)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Grower snapshot")
    y -= 12

    table_rows = [
        [
            "Grower",
            "Median area (ha)",
            "Median compactness",
            "Mean H′",
            "Mono-crops",
            "Seasonal precip (mm)",
            "Seasonal GDD (°C-day)",
            "POWER cells",
        ]
    ]
    for row in stats:
        table_rows.append(
            [
                row["label"],
                fmt(row["median_area"], 1),
                fmt(row["median_compactness"], 3),
                fmt(row["mean_rotation_h"], 3),
                str(row["monocultures"]),
                fmt(row["median_precip"], 0),
                fmt(row["median_gdd"], 0),
                str(row["cells"]),
            ]
        )
    col_widths = [100, 60, 74, 52, 60, 74, 80, 40]
    y = draw_table(c, table_rows, col_widths, MARGIN, y)
    y -= 2
    note = Paragraph(
        "H′ = Shannon entropy of the five-year dominant-crop sequence; 0 = monoculture. "
        "Values are field-level medians except mean H′.",
        STYLES["footer"],
    )
    _, note_h = note.wrapOn(c, CONTENT_W, 1000)
    note.drawOn(c, MARGIN, y - note_h)
    y -= note_h + 10

    # Boundaries.
    y = draw_heading(c, "Boundaries", MARGIN, y, CONTENT_W)
    comparison = (
        "Kruskal–Wallis: area H=12.11, p=0.0023, ε²=0.374; compactness H=0.65, "
        "p=0.722, ε²=−0.050. Spearman area–shape: pooled ρ=−0.471 (p=0.0086); "
        "IA −0.709 (p=0.022), IL −0.576 (p=0.082), NE −0.079 (p=0.829)."
    )
    y = draw_paragraph(c, comparison, STYLES["small"], MARGIN, y, CONTENT_W)
    y -= 6

    y = draw_figure(
        c,
        figures["size"],
        MARGIN,
        y,
        425,
        "Field area by grower. Boxes show median and IQR; points are individual fields. "
        "NE clusters near 200 ha; IL/IA span wider ranges and IA carries the 57.6 ha outlier.",
    )
    y -= 8
    y = draw_figure(
        c,
        figures["compactness"],
        MARGIN,
        y,
        425,
        "Compactness (4πA/P²; 1 = circle) by grower. Boxes show median and IQR; points are fields. "
        "Distributions overlap and the Kruskal–Wallis test is not significant.",
    )

    # Footer.
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN, 30, PAGE_W - MARGIN, 30)
    c.setFont(FONT, 6.4)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 20, "Field EDA  ·  run assignment-2  ·  page 1 of 2")
    c.drawRightString(PAGE_W - MARGIN, 20, "Generated from the static field EDA outputs")

    c.showPage()


def page_two(
    c: canvas.Canvas,
    manifest: dict,
    figures: dict[str, Path],
) -> None:
    # Thin continuation header.
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 28, PAGE_W, 28, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8.4)
    c.drawString(MARGIN, PAGE_H - 19, "Field-Level EDA — Assignment 2  ·  continued")
    c.setFont(FONT, 7.2)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 19, "page 2 of 2")

    y = PAGE_H - 50

    # CDL section.
    y = draw_heading(c, "CDL / cropland", MARGIN, y, CONTENT_W)
    cdl_text = (
        "The 2023 crop mix is mostly corn and soybeans. Rotation diversity uses Shannon H′ "
        "of each field's five-year dominant-crop sequence: strict corn–soy fields score 0.673; "
        "monocultures il-3, ne-2, ne-3, and ne-6 score 0; ia-4 is the outlier at 1.332 "
        "(fallow → soy → corn → soy → alfalfa). CDL residual is explicit as Other/unclassified; "
        "max 6.65% (ia-4, 2023, mostly rye), typical 0.4–0.8%."
    )
    y = draw_paragraph(c, cdl_text, STYLES["body"], MARGIN, y, CONTENT_W)
    y -= 7
    y = draw_figure(
        c,
        figures["heatmap"],
        MARGIN,
        y,
        405,
        "Dominant CDL crop by field and year, 2019–2023. Rows are fields grouped by grower; "
        "columns are years. The matrix shows rotation discipline, monocultures, and the ia-4 "
        "fallow/alfalfa anomaly.",
    )
    y -= 10

    # Weather section.
    y = draw_heading(c, "Weather", MARGIN, y, CONTENT_W)
    weather_text = (
        "Seasonal water supply is lower in NE: field-level medians are IL 537 mm, IA 583 mm, "
        "NE 448 mm. Seasonal GDD medians are IL 1856, IA 1690, NE 2069 °C-day. The corn-vs-soybean "
        "comparison is exploratory: pooled Mann–Whitney p=0.817 for precip and p=0.811 for GDD; "
        "every per-grower p≥0.31. Fields share only 10 POWER cells, so field-level n overstates "
        "independent weather samples."
    )
    y = draw_paragraph(c, weather_text, STYLES["body"], MARGIN, y, CONTENT_W)
    y -= 7
    y = draw_figure(
        c,
        figures["weather"],
        MARGIN,
        y,
        392,
        "Seasonal water and GDD for corn vs soybean years, by grower. Boxes show field-year "
        "distributions; pooled and per-grower Mann–Whitney tests are labelled. Treat as exploratory "
        "because weather is gridded.",
    )
    y -= 10

    # Map and limitations, side by side.
    row_top = y
    map_width = 250
    map_caption = (
        "County-scale field locations; colors are CDL 2023 dominant crops. Scale bars are shown; "
        "fields are unlabelled and scattered."
    )
    with Image.open(figures["map"]) as im:
        map_aspect = im.width / im.height
    map_height = map_width / map_aspect
    c.drawImage(
        ImageReader(str(figures["map"])),
        MARGIN,
        row_top - map_height,
        width=map_width,
        height=map_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.rect(MARGIN, row_top - map_height, map_width, map_height, stroke=1, fill=0)
    cap = Paragraph(map_caption, STYLES["caption"])
    _, cap_h = cap.wrapOn(c, map_width, 1000)
    cap.drawOn(c, MARGIN, row_top - map_height - cap_h - 3)

    # Limitations box. The footer note is drawn first so the box can stop above it.
    note = Paragraph(
        "<b>Also in the full output:</b> area–shape correlation (weak pooled trend); "
        "CDL 2023 composition (crop mix per field); CDL diversity (H′ per field); "
        "annual precipitation (field-year water supply); cumulative GDD curves "
        "(heat accumulation by year).",
        STYLES["footer"],
    )
    _, note_h = note.wrapOn(c, CONTENT_W, 1000)
    note.drawOn(c, MARGIN, 36)
    lim_bottom = 36 + note_h + 9

    lim_x = MARGIN + map_width + 18
    lim_w = CONTENT_W - map_width - 18
    lim_h = row_top - lim_bottom
    c.setFillColor(LIGHT)
    c.rect(lim_x, row_top - lim_h, lim_w, lim_h, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(lim_x, row_top - lim_h, 3.2, lim_h, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont(FONT_BOLD, 8.6)
    c.drawString(lim_x + 9, row_top - 12, "Limitations & assumptions")
    lim_items = [
        "Fields are individually selected CSB polygons scattered across each county, not one contiguous farm; the map is county-scale.",
        "Weather is gridded: 10 POWER cells; fields sharing a cell have identical series, so field-level n overstates independent samples.",
        "The weather/crop join is limited to 2021–2023.",
        "CDL residual is explicit as Other/unclassified and is never renormalized.",
        "No soil, terrain, imagery, or NDVI was read; soil analysis is not required and was not the focus.",
    ]
    draw_bullets(c, lim_items, lim_x + 9, row_top - 22, lim_w - 18, STYLES["bullet_small"])

    c.showPage()


def build_report(output_dir: Path, pdf_path: Path) -> None:
    manifest, rows = load_data(output_dir)
    stats = grower_stats(manifest, rows)

    figure_names = {
        "size": "fig_boundary_size_distribution.png",
        "compactness": "fig_boundary_compactness.png",
        "map": "fig_boundary_field_locations.png",
        "heatmap": "fig_cdl_rotation_heatmap.png",
        "weather": "fig_weather_crop_link.png",
    }
    for name in figure_names.values():
        if not (output_dir / name).exists():
            raise FileNotFoundError(f"Missing expected figure: {output_dir / name}")

    with tempfile.TemporaryDirectory(prefix="assignment-2-report-") as tmp:
        tmp_path = Path(tmp)
        figures = {
            key: crop_figure(output_dir / name, tmp_path / f"{key}.jpg")
            for key, name in figure_names.items()
        }

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        rl_config.invariant = 1
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.setTitle("Field-Level EDA — Assignment 2")
        c.setAuthor("My Farm Advisor")
        c.setSubject("Two-page field EDA report for boundaries, CDL, and weather")
        c.setCreator("generate_assignment_2_report.py")

        page_one(c, stats, manifest, figures)
        page_two(c, manifest, figures)
        c.save()


def default_output_dir() -> Path:
    root = os.environ.get("DATA_PIPELINE_DATA_ROOT")
    if root:
        return (
            Path(root)
            / "data-pipeline"
            / "eda"
            / "field-eda"
            / "output"
            / "assignment-2"
        )
    return Path(
        "/home/coder/my-farm-advisor-runtime/data-pipeline/eda/field-eda/output/assignment-2"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory containing manifest.json and the field EDA artifacts.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(__file__).with_name("assignment-2-field-eda-report.pdf"),
        help="Destination PDF path.",
    )
    args = parser.parse_args()
    build_report(args.output_dir, args.pdf)
    print(f"Wrote {args.pdf}")


if __name__ == "__main__":
    main()
