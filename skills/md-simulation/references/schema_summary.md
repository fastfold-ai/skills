# `calvados_openmm_v1` workflow schema summary

## Submit body

```
POST /v1/workflows
```

```json
{
  "workflow_name": "calvados_openmm_v1",
  "name": "<display name>",
  "workflow_input": { ... }
}
```

## `workflow_input` core fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `preset` | string | ✅ | `"single_af_go"` for AF structure + PAE. Other presets exist server-side (`single_idr_fasta`, `single_idr_box_eq`) but require FASTA / sequences input — not covered by this skill yet. |
| `name` | string | ✅ | OpenMM simulation name. Used as filename stem for generated artifacts. |
| `force_field_family` | string | ✅ | Typically `"calvados"`. |
| `residue_profile` | string | ✅ | Residue profile (e.g. `"calvados2"`, `"calvados3"`, `"c2rna"`). The server auto-attaches a residues CSV for known profiles. |
| `temp` | number | ✅ | Temperature in Kelvin (e.g. `293.15`). |
| `ionic` | number | ✅ | Ionic strength in M (e.g. `0.15`). |
| `pH` | number | ✅ | pH (e.g. `7.5`). |
| `step_size_ns` | number | ✅ | Step size in ns (e.g. `0.01`). |
| `sim_length_ns` | number | ✅ | Simulation length in ns (e.g. `0.2`). |
| `box_length` | number | ✅ | Cubic box length in nm (e.g. `20`). |
| `files` | object | ✅ | `{}` for fold-job mode; `{ "pdb": {...}, "pae": {...} }` for manual upload mode. |
| `isPublic` | bool | optional | Set to `true` to allow public reads via `/v1/workflows/public/<id>`. |

### Fold-job mode (`preset: single_af_go` + `files: {}`)

Add:

| Field | Type | Description |
|-------|------|-------------|
| `sourceType` | `"fold_job"` | Declares that inputs come from an existing fold job |
| `sourceJobId` | UUID | FastFold fold job ID |
| `sourceJobRunId` | UUID | `jobRunId` from `/v1/jobs/{job_id}/results` |
| `sourceSequenceId` | UUID | Protein `sequenceId` from fold results (`sequences[].id` with `type == "protein"`) |

Backend auto-resolves and attaches:

- `files.pdb` → normalized PDB from the fold job
- `files.pae` → normalized PAE JSON (AlphaFold EBI format)

### Manual upload mode (`preset: single_af_go` + `files.pdb` + `files.pae`)

After uploading each file via the Library API, provide refs:

```json
"files": {
  "pdb": { "libraryItemId": "<uuid>", "fileName": "<server-stored-file-name>" },
  "pae": { "libraryItemId": "<uuid>", "fileName": "<server-stored-file-name>" }
}
```

`fileName` must be the UUID-prefixed filename that the server assigns
(read from `metadata.files[0].file_name` after upload). Do **not** pass
the local filename.

## Submit response

`200 OK` with:

- `workflow_id` (UUID)
- `status` (initial status)
- `workflow_type` (`"calvados_openmm_v1"`)
- `tasks[]` including the single MD task (`inference_calvados_openmm`)

## Result payload (after COMPLETED)

From `/v1/workflows/public/<id>` (requires `isPublic: true`) or
`/v1/workflows/task-results/<id>` (authed):

- `tasks[-1].result_raw_json.artifacts[]`
  - `path`: e.g. `analysis/metrics.json`, `analysis/<name>_fel.png`, `analysis/<name>_rg.svg`, `<name>.dcd`, `<name>.pdb`, `_inputs/<name>.pdb`, `_inputs/<name>.json`
  - `sizeBytes`: integer bytes
  - `url`: signed download URL (CloudFront / S3)
- `tasks[-1].result_raw_json.metrics` (top-level keys):
  - `rmsd`, `rmsf`, `radius_of_gyration`, `free_energy_landscape`
  - `binding_energy`, `protein_ligand_distance` (present when `ligand_detected: true`)
  - `ligand_detected`, `analysis_name`, `analysis_parameters`, `output_files`
- `tasks[-1].result_raw_json.metricsJson` — raw `analysis/metrics.json` content

## Status values

`INITIALIZED` | `QUEUED` | `RUNNING` | `COMPLETED` | `FAILED` | `STOPPED`

Only trust artifacts/metrics when task status is `COMPLETED`.
Metrics may appear a short time after the first terminal status; use
`wait_for_workflow.py` to handle the settle window.
