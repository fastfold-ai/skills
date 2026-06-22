# Unified Boltz Results Reference

Default runtime output root (bundled runner default):

- `/tmp/boltz-runs`

Persistent mirror root:

- `/workspace/boltz-artifacts/boltz`
- Runner mirrors `<run_name>` into `/workspace/boltz-artifacts/boltz/<run_name>/` after successful download/run.

Ephemerality and durability:

- `/tmp/boltz-runs` is wiped whenever the sandbox is evicted or recreated.
- Durable state lives in the Boltz API (the job) and the `/workspace` mirror.
- At submit time the runner writes `manifest.json` (`run_name`, `job_id`, `resource`) to the
  workspace immediately, before the long download poll, so a run stays recoverable even if the
  submit/wait is interrupted.
- `resume` and `recover` always mirror downloaded results to `/workspace`; `status` auto-restores
  the workspace mirror back into `/tmp` before reading local checkpoint state.

Runner summary output includes:

- `job_id` (for non-ADME modes)
- `idempotency_key`
- `run_name`
- `run_dir`
- `output_root`
- `persistent_run_dir`
- `estimate`

Recommended naming/idempotency strategy:

- Use one stable slug per experiment for `--run-name`.
- Reuse that same slug for idempotent retries and downloads.
- Keep `run_name` stable across `status` and `resume`.
- Treat `run_dir` as the source of truth for the resolved local folder name.

Status and resume strategy:

1. Check local state (`status` action) — auto-restores from the workspace mirror if `/tmp` is empty.
2. Retrieve remote job metadata (`retrieve` action).
3. Resume artifacts (`resume` action) — downloads and mirrors to `/workspace`.
4. Recover after sandbox eviction (`recover` action) — resolves `job_id` from the workspace
   manifest or the API by `idempotency_key`, then re-downloads and mirrors. Never re-submit.

Useful status commands:

- Local checkpoint status:
  - `python scripts/run.py status --action status --run-name <slug>`
- Remote retrieve by job id:
  - `python scripts/run.py status --action retrieve --resource sab --job-id <id>`
- Resume downloads (mirrors to `/workspace`):
  - `python scripts/run.py status --action resume --job-id <id> --run-name <slug>`
- Recover after eviction (auto-resolves the job, mirrors to `/workspace`):
  - `python scripts/run.py status --action recover --run-name <slug>`
  - `python scripts/run.py status --action recover --run-name <slug> --job-id <id>` (skip API lookup)

Recovering a lost run-name:

- If the run-name/slug is unknown, list jobs first and match on `idempotency_key`:
  - `python scripts/run.py status --action list --limit 20`
- Then `recover`/`resume` with the discovered `--job-id`.

Pagination & completeness:

- `resume`/`recover` run `download-results --download-mode everything`, which follows the remote
  result cursor and downloads the **entire** result set (concurrent workers). The complete set
  lands under `<run_dir>/results/<result_id>/` (one folder per item, each with `metadata.json`
  and `archive.tar.gz`).
- To return first/top/ranked N from downloaded artifacts, enumerate the local `results/` directory
  after download — do not page the API by hand. Reading the local mirror is complete and avoids
  per-request limits.
- For a quick peek without downloading archives (design/screen only), use the API-native paginated
  endpoint: `status --action list-results --resource <r> --job-id <id> --limit <n>`
  (or `--max-items -1` for the full set, `--after-id <id>` to page). For `sab`/`adme`, results come
  back inline via `status --action retrieve`.
- The job-discovery scan in `recover` uses `--max-items -1`, so the cursor-based job list is fully
  paginated and won't miss the target job in a workspace with many runs.
- A result set is only incomplete if `download-results` errored or the run is still `running`;
  re-run `resume`/`recover` (idempotent) instead of paginating manually.
