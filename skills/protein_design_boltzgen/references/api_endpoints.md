# BoltzGen API Endpoints (Composer-Equivalent)

## Base URLs

- API default: `https://api.fastfold.ai`
- UI default for shared composer/results links: `https://cloud.fastfold.ai`

## Authentication

Use API key header:

- `X-API-Key: <FASTFOLD_API_KEY>`

## Core Flow

1. Create workflow draft:
   - `POST /v1/workflows/graph/add`
2. Upload input files:
   - `POST /v1/library/create`
   - `POST /v1/library/{item_id}/upload-files`
   - `GET /v1/library/{item_id}`
3. Save full graph as workflow YAML:
   - `POST /v1/workflows/{workflow_id}/workflow.yml`
4. Execute:
   - `POST /v1/workflows/execute`
5. Poll status:
   - `GET /v1/workflows/status/{workflow_id}`
6. Read live logs (same endpoint used by Composer log panel):
   - `GET /v1/workflows/logs/{workflow_id}`
7. Fetch results:
   - `GET /v1/workflows/task-results/{workflow_id}`

## Useful Read Endpoints

- Workflow summary:
  - `GET /v1/workflows/{workflow_id}`
- Graph JSON:
  - `GET /v1/workflows/{workflow_id}/graph`
- Current YAML preview:
  - `GET /v1/workflows/{workflow_id}/workflow.yml`
- Workflow logs:
  - `GET /v1/workflows/logs/{workflow_id}` (plain text; for active runs and post-run log retrieval)
- Sync current graph to canonical `.fastfold/workflow.yml`:
  - `POST /v1/workflows/{workflow_id}/sync/workflow.yml`

## Composer Link

After non-empty graph upsert, share:

- `https://cloud.fastfold.ai/workflow/composer/{workflow_id}`
