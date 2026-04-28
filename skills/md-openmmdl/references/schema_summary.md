# OpenMMDL Input Schema Summary

This summary reflects backend validation in `api/workflows/routes.py` for `openmmdl_v1`.

## Minimal valid payload

```json
{
  "workflow_name": "openmmdl_v1",
  "name": "OpenMMDL Simulation",
  "workflow_input": {
    "name": "openmmdl_run_1",
    "files": {
      "topology": {
        "libraryItemId": "<uuid>",
        "fileName": "<stored_topology_file>"
      },
      "ligands": [
        {
          "libraryItemId": "<uuid>",
          "fileName": "<stored_ligand_file>"
        }
      ]
    }
  }
}
```

## Required fields

- `workflow_name` must be `openmmdl_v1`
- `workflow_input.name` (non-empty string)
- `workflow_input.files` (object)
- `workflow_input.files.topology.libraryItemId` + `fileName`

## Ligands field variants

`workflow_input.files.ligands` can be:

1. Omitted (no ligands), or
2. One object:
   ```json
   { "libraryItemId": "<uuid>", "fileName": "<name>" }
   ```
3. Array of objects (recommended for multiple ligands):
   ```json
   [
     { "libraryItemId": "<uuid>", "fileName": "<name1>" },
     { "libraryItemId": "<uuid>", "fileName": "<name2>" }
   ]
   ```

## Validated optional fields

The backend explicitly validates/coerces:

- `workflow_input.ligand_selection` (string, max 120 chars)
- `workflow_input.run_analysis` (boolean-like)
- `workflow_input.analysis_cpus` (integer >= 1)
- `workflow_input.failure_retries` (integer >= 1)
- `workflow_input.sim_length_ns` (number > 0)
- `workflow_input.step_time_ps` (number > 0)

Many other OpenMMDL fields are accepted and passed through without strict backend validation.

## Draft script mode

To create a DRAFT workflow instead of queuing immediately, set:

- top-level `create_mode: "draft_script"` and/or
- `workflow_input.create_mode: "draft_script"`

Example:

```json
{
  "workflow_name": "openmmdl_v1",
  "create_mode": "draft_script",
  "name": "OpenMMDL Draft",
  "workflow_input": {
    "create_mode": "draft_script",
    "name": "openmmdl_draft_1",
    "files": {
      "topology": { "libraryItemId": "<uuid>", "fileName": "<file>" }
    }
  }
}
```

## Prepare-script endpoint contract

`POST /v1/workflows/openmmdl/prepare-script` request:

```json
{ "workflow_input": { "...": "..." } }
```

Response includes:

- `system_name`
- `folder_name`
- `topology_file`
- `ligand_files` (array)
- `generated_script`
- `processed_topology_file`
- `processed_topology_b64`
- `missing_residue_spans` (array)
- `missing_heavy_atoms` (array)
- `workflow_input` (effective normalized payload to use for submit/explanations)

## Effective inputs and defaults

`prepare-script` and workflow submit responses may return normalized/defaulted values.

For reliable user-facing reporting:

1. Prefer `prepared.workflow_input` after `POST /v1/workflows/openmmdl/prepare-script`.
2. Prefer `submit_response.input_payload` after `POST /v1/workflows`.
3. Treat those payloads as the canonical "what ran" source when answering user questions.
