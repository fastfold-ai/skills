# Auth & API Reference (md-openmm-calvados)

## Base URL

- Production: `https://api.fastfold.ai`
- Self-host / local: override with `--base-url http://localhost:8000` on any script.

## Authentication

All workflow and library endpoints require an API key.

- Header: `X-API-Key: <YOUR_API_KEY>` (also accepted: `Authorization: Bearer <YOUR_API_KEY>`)
- Key creation: https://cloud.fastfold.ai/api-keys
- Scripts resolve the key from (first match wins):
  1. `FASTFOLD_API_KEY` env var
  2. `.env` in the current or any parent directory
  3. `~/.fastfold-cli/config.json` (`api.fastfold_cloud_key`)

Never paste keys into chat or command arguments.

## Endpoints used by this skill

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/jobs/{job_id}/results` | Resolve `jobRunId` + protein `sequenceId` from a FastFold fold job |
| POST | `/v1/library/create` | Create a Library item for a file to upload (fold-job mode not needed) |
| POST | `/v1/library/{item_id}/upload-files` | Upload PDB or PAE JSON (multipart/form-data, field `files`) |
| GET | `/v1/library/{item_id}` | Read back `metadata.files[0].file_name` to reference in the workflow payload |
| POST | `/v1/workflows` | Submit `workflow_name: calvados_openmm_v1` with OpenMM `workflow_input` (include `isPublic: true` to make public at creation) |
| GET | `/v1/workflows/{workflow_id}` | Fetch an existing OpenMM workflow and read its stored `input_payload` before submitting a new workflow from it |
| GET | `/v1/workflows/status/{workflow_id}` | Poll workflow + task status |
| GET | `/v1/workflows/task-results/{workflow_id}` | Read task-level output summary (authed) |
| GET | `/v1/workflows/public/{workflow_id}` | Read full public payload including `result_raw_json` (no auth; requires `isPublic: true`) |
| PATCH | `/v1/workflows/{workflow_id}/public` | Toggle public/private after creation. Body: `{ "isPublic": true \| false }` |

## Terminal states

Workflow and task `status` values are the same set:

- `INITIALIZED`, `QUEUED`, `RUNNING`
- `COMPLETED`, `FAILED`, `STOPPED` (terminal)

Trust `artifacts`, `metrics`, `metricsJson` only when task status is `COMPLETED`.
These fields can populate a short time after the first terminal status;
`wait_for_workflow.py` handles that settle window.

## isPublic vs auth

- `workflow_input.isPublic: true` makes the full `result_raw_json` readable
  via `/v1/workflows/public/{id}` without auth — useful for sharing and for
  reading artifact URLs directly from results.
- If you omit `isPublic`, use `/v1/workflows/task-results/{id}` with API key
  to inspect task output.
- Toggle public/private at any time with
  `PATCH /v1/workflows/{id}/public` (body `{ "isPublic": true }`). The
  state is stored in `workflow.input_payload.isPublic`.

## Public share URL

When public, link users to:

```
https://cloud.fastfold.ai/openmm/results/<workflow_id>?shared=true
```

For private workflows this URL returns `403` and redirects the visitor to
login with a `return_to` back to the authed results page.
