# Field EDA Local Instructions

## Purpose

This folder owns the field-level EDA subskill: one generator that compares field
boundaries, CDL history, and weather across growers and writes static figures,
CSV tables, and a manifest.

## Safe edit scope

Keep edits inside `eda/field-eda/`, except for the generator at
`data-pipeline/src/scripts/reporting/generate_field_eda.py`. Do not change sibling
EDA guides, the data-pipeline runtime contract, or root policy from this folder
unless the user explicitly asks.

## Read first

- `README.md` for outputs and measured findings.
- `GUIDE.md` for metric definitions and the figure catalogue.
- `PROVENANCE.md` before changing inputs, sources, or the crop palette.
- `../../data-pipeline/AGENTS.md` for runtime rules.

## Runtime contract

- `DATA_PIPELINE_DATA_ROOT` must be absolute and outside the repository.
- Write outputs only under
  `${DATA_PIPELINE_DATA_ROOT}/data-pipeline/eda/field-eda/output/<run-name>/`.
- Run the generator from the runtime source copy, never from this checkout.
- Refresh the runtime source after editing the generator with
  `install.sh --non-interactive --force-refresh --no-install-deps --persist none`.

## Story rule

Every figure and table must have a story that the measured statistics support.
Before changing a title, caption, or manifest story:

1. read the corresponding statistic in `manifest.json`;
2. state the direction, effect size, and p-value where relevant;
3. mark exploratory or underpowered comparisons as such;
4. never describe a group difference that the test does not show.

Current examples: field area differs by grower, but compactness does not. The
corn-vs-soy weather comparison is exploratory because fields share ten POWER
cells.

## Output policy

- No HTML, dashboard, or report here. The report is a separate one-time artifact.
- No soil, terrain, imagery, or NDVI inputs.
- Keep the CDL residual as explicit `Other/unclassified`.
- Do not commit generated artifacts.

## Validation

- `python3 -m py_compile data-pipeline/src/scripts/reporting/generate_field_eda.py`
- A runtime run that produces all 15 artifacts.
- A repeat run compared by SHA-256 for determinism.
- `./scripts/validate.sh` from the repository root after documentation changes.

## Keep it small

This is a first build meant to be reviewed and improved. Add figures in the same
three-category structure, with one explicit story per artifact, rather than
expanding into a dashboard or a full report.