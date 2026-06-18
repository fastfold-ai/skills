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
8. Download output artifacts (CIF/CSV/PDF) to disk:
   - `GET /v1/library/{item_id}` → read `metadata.files[0].file_name` (stored name)
   - `GET /v1/library/file/{item_id}/{file_name}` → returns a JSON string with a short-lived CloudFront-signed `https://artifacts.fastfold.ai/...` URL
   - `GET <signed_url>` → file bytes (the signed URL is self-authenticating; do NOT send the API key to it)

## Downloading Output Files (Important)

Workflow results return output files as **library item references**
(`{ "libraryItemId": "...", "fileName": "rank1_4.cif" }`), not direct URLs.
To download them programmatically:

1. Resolve the stored file name from `GET /v1/library/{item_id}` (`metadata.files[].file_name`).
   For pipeline outputs this usually equals `fileName`; for uploaded inputs it may be `<uuid>_<name>`.
2. Call `GET /v1/library/file/{item_id}/{stored_file_name}` with `X-API-Key`. This returns a
   signed `artifacts.fastfold.ai` URL (it does **not** stream the bytes directly).
3. `GET` the signed URL with no auth header to fetch the bytes.

Notes:
- `GET /v1/library/file/...` accepts the same `X-API-Key` auth as the rest of this flow.
  The browser-only `cloud.fastfold.ai/api/structure` route is **not** required and will reject API keys.
- The bundled `workflow_api.py download` command performs all three steps for every artifact.

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
