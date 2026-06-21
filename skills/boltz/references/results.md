# Unified Boltz Results Reference

Default runtime output root (bundled runner default):

- `/tmp/boltz-runs`

Persistent mirror root:

- `/workspace/boltz-artifacts/boltz`
- Runner mirrors `<run_name>` into `/workspace/boltz-artifacts/boltz/<run_name>/` after successful download/run.

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

1. Check local state (`status` action).
2. Retrieve remote job (`retrieve` action).
3. Resume artifacts (`resume` action).

Useful status commands:

- Local checkpoint status:
  - `python scripts/run.py status --action status --run-name <slug>`
- Remote retrieve by job id:
  - `python scripts/run.py status --action retrieve --resource sab --job-id <id>`
- Resume downloads:
  - `python scripts/run.py status --action resume --job-id <id> --run-name <slug>`
