# Auth & API Reference (md-openmmdl)

## Base URL

- Production: `https://api.fastfold.ai`
- Self-host / local: override with `--base-url http://localhost:8000` on scripts.

## Authentication

All workflow and library endpoints require an API key.

- Header: `X-API-Key: <YOUR_API_KEY>` (also accepts `Authorization: Bearer <YOUR_API_KEY>`)
- Key creation: https://cloud.fastfold.ai/api-keys
- Scripts resolve the key from (first match wins):
  1. `FASTFOLD_API_KEY` env var
  2. `.env` in current or parent directory
  3. `~/.fastfold-cli/config.json` (`api.fastfold_cloud_key`)

Never paste keys into chat or command arguments.

## Endpoints used by this skill

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/library/create` | Create a file item before upload |
| POST | `/v1/library/{item_id}/upload-files` | Upload topology/ligand/script files |
| GET | `/v1/library/{item_id}` | Read `metadata.files[0].file_name` for workflow refs |
| POST | `/v1/workflows/openmmdl/prepare-script` | Validate input and generate OpenMMDL script metadata |
| POST | `/v1/workflows` | Submit `workflow_name: openmmdl_v1` |
| POST | `/v1/workflows/execute` | Execute an existing draft workflow |
| GET | `/v1/workflows/{workflow_id}` | Full workflow details including `tasks[].result_raw_json` |
| GET | `/v1/workflows/status/{workflow_id}` | Poll workflow + task status |
| GET | `/v1/workflows/public/{workflow_id}` | Public read of workflow (requires `isPublic: true`) |
| PATCH | `/v1/workflows/{workflow_id}/public` | Toggle workflow public/private |
| POST | `/v1/workflows/openmmdl/{workflow_id}/extract-frame` | Extract PDB frame from trajectory |

## Workflow type + task type

- Workflow type: `openmmdl_v1`
- Inference task type: `inference_openmmdl`

## Terminal states

Workflow/task status values:

- `INITIALIZED`, `QUEUED`, `RUNNING`
- `COMPLETED`, `FAILED`, `STOPPED` (terminal)

Trust `result_raw_json` artifacts and metrics only after terminal completion.

## isPublic behavior

- If `workflow_input.isPublic: true`, the workflow is readable via `/v1/workflows/public/{id}`.
- If private, use authenticated endpoints (`/v1/workflows/{id}` and `/v1/workflows/status/{id}`).
- Toggle later with `PATCH /v1/workflows/{id}/public` and `{ "isPublic": true | false }`.

## Dashboard URLs

- Private/authed dashboard:  
  `https://cloud.fastfold.ai/openmmdl/results/<workflow_id>`
- Share URL (public only):  
  `https://cloud.fastfold.ai/openmmdl/results/<workflow_id>?shared=true`
- Deep analysis view:  
  `https://cloud.fastfold.ai/openmmdl/results/md-analysis/<workflow_id>`
