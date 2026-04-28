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
| `preset` | string | ✅ | `"single_af_go"` (AF structure + PAE) or `"single_idr_fasta"` (sequence-only/FASTA mode). |
| `name` | string | ✅ | OpenMM simulation name. Used as filename stem for generated artifacts. |
| `force_field_family` | string | ✅ | Typically `"calvados"`. |
| `residue_profile` | string | ✅ | Force field selector (CALVADOS parameter set), e.g. `"calvados2"`, `"calvados3"`, `"c2rna"`. The server auto-attaches a residues CSV for known values. |
| `temp` | number | ✅ | Temperature in Kelvin (e.g. `293.15`). |
| `ionic` | number | ✅ | Ionic strength in M (e.g. `0.15`). |
| `pH` | number | ✅ | pH (e.g. `7.5`). |
| `step_size_ns` | number | ✅ | Step size in ns (e.g. `0.01`). |
| `sim_length_ns` | number | ✅ | Simulation length in ns (e.g. `0.2`). |
| `box_length` | number | ✅ | Cubic box length in nm (e.g. `20`). |
| `files` | object | ✅ | `{}` for fold-job mode; `{ "pdb": {...}, "pae": {...} }` for manual upload mode. |
| `config.box_eq` | bool | optional | Enable/disable anisotropic box equilibration stage. |
| `config.pressure` | number[3] | optional | Pressure vector `[x,y,z]` for box equilibration, e.g. `[0.1,0,0]`. |
| `component_defaults.periodic` | bool | optional | Enable/disable periodic component handling. |
| `component_defaults.charged_N_terminal_amine` | bool | optional | N-terminal amine charge-state flag. |
| `component_defaults.charged_C_terminal_carboxyl` | bool | optional | C-terminal carboxyl charge-state flag. |
| `component_defaults.charged_histidine` | bool | optional | Histidine charging flag. |
| `component_defaults.charge_termini` | string | optional | CALVADOS termini mode derived from N/C flags (`both`, `N`, `C`, `none`). |
| `yml_reference` | object | optional | Advanced lane-2 metadata: uploaded `config.yaml` + `components.yaml` refs and file bindings for provenance/future YML-native input mode. |
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

### Advanced lane-2 reference metadata (`yml_reference`)

Advanced skills can attach uploaded YML references without changing runtime semantics:

```json
"yml_reference": {
  "mode": "lane2_custom_upload_v1",
  "config": { "libraryItemId": "<uuid>", "fileName": "config.yaml" },
  "components": { "libraryItemId": "<uuid>", "fileName": "components.yaml" },
  "file_bindings": {
    "residues": { "libraryItemId": "<uuid>", "fileName": "<server-file>" },
    "fasta": { "libraryItemId": "<uuid>", "fileName": "<server-file>" }
  }
}
```

This is for reproducibility/provenance and future migration; current execution still uses explicit OpenMM fields + `files`.

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
  - `path`: e.g. `analysis/metrics.json`, `analysis/<name>_fel.png`, `analysis/<name>_fel.csv`, `analysis/<name>_rg.svg`, `analysis/<name>_rg.csv`, `<name>.dcd`, `<name>.pdb`, `_inputs/<name>.pdb`, `_inputs/<name>.json`
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

## Extract frame endpoint

Use after a completed OpenMM workflow has trajectory artifacts.

```
POST /v1/workflows/openmm/<workflow_id>/extract-frame
```

Body:

```json
{
  "timeNs": 5.0,
  "selection": "protein or resname LIG",
  "outputFilename": "<workflow-name>_extracted_frame.pdb",
  "dtInPs": 0
}
```

Fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timeNs` | number | ✅ | Time to extract in ns. Must be non-negative and should be within `sim_length_ns`; the server extracts the closest available frame. |
| `selection` | string | optional | MDAnalysis atom selection. Defaults to `protein or resname LIG`. |
| `outputFilename` | string | optional | PDB filename. UI/scripts use `<workflow-name>_extracted_frame.pdb`. |
| `dtInPs` | number | optional | Timestep override in ps. `0` means auto/read from trajectory metadata. |

Response:

```json
{
  "workflowId": "<uuid>",
  "taskId": "<uuid>",
  "pdbUrl": "https://...",
  "path": "analysis/extracted_frames/<file>.pdb",
  "frameIndex": 500,
  "requestedTimeNs": 5.0,
  "actualTimeNs": 5.0,
  "atomCount": 1234
}
```

Bundled script:

```bash
python scripts/extract_frame.py <workflow_id> --time-ns 5.0 [--selection "protein or resname LIG"] [--dt-in-ps 0] [--download ./frame.pdb] [--json]
```
