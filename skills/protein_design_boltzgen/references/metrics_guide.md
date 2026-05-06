# BoltzGen Metrics Guide

Use this guide when explaining `parsed_results` from:

- `GET /v1/workflows/task-results/{workflow_id}`
- task type: `pipeline_run_boltzgen_v1`

## Expected output spec

`GET /v1/workflows/task-results/{workflow_id}` returns:

- `tasksResults[]` entries per node/task
- for `task_type == pipeline_run_boltzgen_v1`:
  - `parsed_results[]` (ranked candidates with metrics)
  - `output_library_items[]` (artifacts such as CSV/PDF/CIF)

Candidate row expected shape:

```json
{
  "id": "<design_label>",
  "num_design": 0,
  "designed_sequence": "<AA_SEQUENCE>",
  "final_rank": 1,
  "secondary_rank": 1,
  "max_rank": 1.0,
  "quality_score": null,
  "iptm": 0.0,
  "design_iiptm": 0.0,
  "ligand_iptm": 0.0,
  "ptm": 0.0,
  "design_ptm": 0.0,
  "target_ptm": 0.0,
  "interaction_pae": 0.0,
  "min_interaction_pae": 0.0,
  "bindsite_under_3rmsd": 0.0,
  "bindsite_under_4rmsd": 0.0,
  "bindsite_under_5rmsd": 0.0,
  "bindsite_under_6rmsd": 0.0,
  "bindsite_under_7rmsd": 0.0,
  "bindsite_under_8rmsd": 0.0,
  "bindsite_under_9rmsd": 0.0,
  "design_hydrophobicity": 0.0,
  "helix": 0.0,
  "sheet": 0.0,
  "loop": 0.0,
  "file": {
    "libraryItemId": "<uuid>",
    "fileName": "rank1_<design_label>.cif"
  }
}
```

## Field-by-field meaning

- `id`: design/job label (usually derived from input spec id).
- `num_design`: intermediate generated design index used by the pipeline.
- `designed_sequence`: amino-acid sequence for designed chain/residues.
- `final_rank`: final filtered rank (primary order shown to users).
- `secondary_rank`: additional ranking order from filtering stage.
- `max_rank`: normalized rank helper from filtering output.
- `quality_score`: optional aggregate quality score; may be `null`.
- `iptm`: interface predicted TM-style confidence (higher is usually better).
- `design_iiptm`: design/interface-focused confidence metric.
- `ligand_iptm`: ligand interface confidence (relevant for ligand tasks; often `0` otherwise).
- `ptm`: overall predicted TM-style confidence.
- `design_ptm`: predicted TM confidence for designed portion/complex context.
- `target_ptm`: predicted TM confidence for target context.
- `interaction_pae`: interface uncertainty/error estimate (lower is generally better).
- `min_interaction_pae`: best-case/minimum interface PAE observed.
- `bindsite_under_3rmsd ... bindsite_under_9rmsd`: fraction/proportion satisfying each binding-site RMSD cutoff.
- `design_hydrophobicity`: hydrophobicity-related composition metric for designed sequence.
- `helix`, `sheet`, `loop`: secondary-structure composition fractions.
- `file.libraryItemId`, `file.fileName`: result structure artifact reference (open this CIF for geometry inspection).

## Output artifacts (pipeline node)

From `output_library_items[]` for a completed pipeline task:

- `all_designs_metrics.csv`: metrics for all considered designs.
- `final_designs_metrics_<budget>.csv`: metrics for final selected set.
- `results_overview.pdf`: plots/summary visualization.
- `rank<k>_<id>.cif`: ranked candidate structure files.

## Practical interpretation (heuristic)

- `final_rank`: pipeline-selected order after quality/diversity filtering.
- `iptm` / `design_iiptm`: interface confidence indicators; higher is generally better.
- `interaction_pae` / `min_interaction_pae`: interface uncertainty/error estimates; lower is generally better.
- `bindsite_under_Xrmsd`: fraction near target-site RMSD cutoff; higher suggests better local site match.
- `helix/sheet/loop`: secondary structure composition summary for designed region.
- `design_hydrophobicity`: quick composition signal; use comparatively across candidates, not as an absolute pass/fail.

## Reporting rules

- Compare candidates within the same run/protocol first.
- Present uncertainty and avoid universal thresholds.
- Do not claim biological efficacy from computational metrics alone.
- Always include the structure file links so users can inspect geometry.

## Paper context

BoltzGen reports broad modality support and wet-lab validation across diverse target/binder settings:

- Paper: <https://www.biorxiv.org/content/10.1101/2025.11.20.689494v1.full>
- DOI: `10.1101/2025.11.20.689494`

Use the paper for capability framing, but keep run-level interpretation grounded in the returned metrics and structures.
