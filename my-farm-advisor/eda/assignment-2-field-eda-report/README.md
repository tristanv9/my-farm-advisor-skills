# Assignment 2 Field EDA Report

One-time, two-page PDF report assembled from the static outputs of the
`eda/field-eda` subskill for the Assignment 2 run. It is **not** part of the
reusable subskill; the subskill stops at figures, tables, and a manifest.

## Custom EDA skill

The custom skill behind these outputs is **Field EDA** (`field-eda`), at
[`eda/field-eda/`](../field-eda/). It compares field boundaries, CDL/cropland
history, and weather across growers and writes ten static figures, four CSV
tables, and one manifest. Outputs are saved under
`${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/`;
this report is saved in this folder as `assignment-2-field-eda-report.pdf`.

## Files

| File | Purpose |
| --- | --- |
| `assignment-2-field-eda-report.pdf` | The two-page report. Open this from the pull request. |
| `generate_assignment_2_report.py` | One-time reproducibility script that rebuilds the PDF from the run outputs. |
| `figures/` | The ten standalone EDA figures (PNG) from the same run. |
| `README.md` | This note. |

## What the report covers

Page 1: dataset scope and grower locations, field counts and data layers, the
comparison levels used, key findings, a grower snapshot table, and the two
boundary visualizations with their Kruskal–Wallis and Spearman results.

Page 2: the CDL rotation heatmap and diversity/residual text, the corn-vs-soybean
weather comparison with its exploratory caveat, the county-scale geospatial map,
and a limitations box. A footer note lists the five figures not embedded.

## Source run

Artifacts come from:

```text
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/assignment-2/
```

Growers: `il-grower` (Iroquois, IL), `ia-grower` (Kossuth, IA), `ne-grower`
(York, NE), 10 fields each. Layers: field boundaries, CDL 2019–2023, NASA POWER
weather 2021–2025. No soil, terrain, imagery, or NDVI layer was used.

## Rebuild

The script needs `reportlab` and `pillow`, which are not in the data-pipeline
virtual environment. Install them in a throwaway environment, then run from
this folder:

```bash
python generate_assignment_2_report.py
```

By default it reads the `assignment-2` runtime output directory and writes
`assignment-2-field-eda-report.pdf` beside the script. Pass `--output-dir` and
`--pdf` to override either path.

## Notes

- The report is exactly two pages; the generator embeds five of the ten figures
  at readable size and describes the other five in the footer note.
- Every statistic in the PDF is read from the run's `manifest.json` and
  `field_metrics.csv`, so re-running the report against a new run name picks up
  the new numbers.
- The build is deterministic: `rl_config.invariant = 1` plus `ImageReader`
  image inputs make repeated runs byte-identical (same SHA-256).
- The report deliberately omits soil analysis, which was not required and not a
  focus of Assignment 2.
