---
name: field-eda
description: >
  Field-level EDA subskill for My Farm Advisor. Use when a request needs a
  reproducible comparison of field boundaries, CDL/cropland history, and
  weather across fields and growers, delivered as static PNG figures, CSV
  tables, and one manifest — no dashboard and no assembled report.
license: Apache-2.0
metadata:
  author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  version: "0.1.0"
  skill-author: Clayton Young / Superior Byte Works, LLC (@borealBytes)
  skill-version: "0.1.0"
---

# Field EDA

Use this nested EDA subskill to compare field boundaries, CDL/cropland history,
and weather across several growers with one deterministic Python run. It reads
the canonical runtime tree, writes ten static figures, four CSV tables, and one
manifest, and stops there.

## Start Here

- Read [README.md](README.md) for the overview, inputs, outputs, and measured findings.
- Read [GUIDE.md](GUIDE.md) for metric definitions, the figure/table catalogue, flags, and troubleshooting.
- Read [INDEX.md](INDEX.md) for file-level navigation.
- Read [PROVENANCE.md](PROVENANCE.md) before changing inputs, sources, or the crop palette.
- Open [`../../data-pipeline/src/scripts/reporting/generate_field_eda.py`](../../data-pipeline/src/scripts/reporting/generate_field_eda.py) for the generator.

## When To Use

Use this subskill when a request asks for:

- a field-level comparison of size, shape, crop history, or weather across growers;
- within-field change over time, across fields within a grower, and across growers;
- a small, reviewable set of static EDA artifacts before a report is written;
- reproducible evidence for assignment-style or grower-review analysis.

Do not use it for: soil, terrain, imagery, or NDVI analysis; live dashboards;
report or HTML assembly; or anything that needs a new data download. The report
is a separate, one-time artifact assembled from these outputs.

## Comparison Axes

Every category covers three axes where the data support it:

| Axis | Boundaries | CDL | Weather |
| --- | --- | --- | --- |
| Within a field over time | — | field x year heatmap, transition table | annual precipitation, GDD curves |
| Across fields within a grower | size, compactness | composition, rotation diversity | field points |
| Across growers | Kruskal–Wallis, Spearman | composition, rotation | precipitation, GDD, crop link |

## Runtime Contract

- `DATA_PIPELINE_DATA_ROOT` is required, absolute, and outside this repository.
- Inputs are read from `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/<grower>/farms/<farm>/`:
  - `boundary/field_boundaries.geojson`
  - `derived/tables/<farm>_<start>_<end>_full_composition.csv`
  - `derived/tables/<farm>_weather_<start>_<end>.csv`
- Run the generator from the installed runtime copy, not from this checkout:
  `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python ${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src/scripts/reporting/generate_field_eda.py ...`
- Refresh the runtime source after editing the generator:
  `./data-pipeline/scripts/install.sh --non-interactive --force-refresh --no-install-deps --persist none`.

## Output

Everything lands under:

```
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/
```

The default run name is `default`; the Assignment 2 run uses `--run-name assignment-2`.
Outputs are runtime artifacts and must not be committed. There is no HTML,
dashboard, or report here by design.

## Command

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  src/scripts/reporting/generate_field_eda.py \
  --growers il-grower ia-grower ne-grower \
  --run-name assignment-2
```

`--growers` also sets display order. Without it, every grower that has all three
layers is used in directory order.

## Story Contract

Each figure and table must carry an explicit, measured story in `manifest.json`.
Do not describe a difference that the statistics do not support. The current
build deliberately records two corrections:

- field area differs by grower (Kruskal–Wallis p=0.002), but compactness does not
  (p=0.72);
- the corn-vs-soy weather comparison is exploratory and underpowered, not proof
  of no effect.

## Related

- [../INDEX.md](../INDEX.md) — EDA subtree index.
- [../eda-explore/GUIDE.md](../eda-explore/GUIDE.md) — first-pass inspection.
- [../eda-visualize/GUIDE.md](../eda-visualize/GUIDE.md) — chart conventions.
- [../../data-pipeline/README.md](../../data-pipeline/README.md) — runtime setup and pipeline commands.
- [../../data-pipeline/grower-web-map/SKILL.md](../../data-pipeline/grower-web-map/SKILL.md) — the nested-subskill layout this folder follows.