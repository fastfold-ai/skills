---
name: boltz
description: Unified Boltz API execution skill. Use this whenever users ask for Boltz structure-and-binding, protein design/screen, small-molecule design/screen, ADME prediction, or Boltz run status/recovery; run through the bundled script for estimate -> submit -> wait/download -> final summary.
---

# Boltz

## Overview

Use this single skill for all Boltz API workflows:

- structure-and-binding
- protein design
- protein screen
- small-molecule design
- small-molecule screen
- ADME
- status/retrieve/resume

## Authentication

- `boltz-api` is expected to be preinstalled in the runtime image.
- `BOLTZ_API_KEY` must be available in the runtime environment.
- If `BOLTZ_API_KEY` is missing, stop and ask the user to:
  - configure Boltz provider access in Fastfold: `https://cloud.fastfold.ai/integrations/providers?provider=boltz`
  - create/get API key in Boltz console: `https://api.boltz.bio/console`
  - restart the sandbox so the new env var is available to commands
- If CLI/auth is unavailable, report the infrastructure issue and stop.

## When to Use This Skill

- User explicitly wants Boltz API execution (`boltz-api` flows).
- User needs end-to-end run with cost estimate, submission, waiting/downloading, and summary.
- User needs status/recovery for an existing Boltz job.
- User asks for Boltz endpoints, payload mapping, or run artifacts.

## Workflow

0. Confirm mode:
   - `sab`, `protein-design`, `protein-screen`, `sm-design`, `sm-screen`, `adme`, `status`.
1. For non-`status` modes, prepare payload file in working directory (for example: `payload.yaml`).
2. Run estimate first:
   - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --estimate-only`
3. If execution is approved, run full end-to-end:
   - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --yes`
4. For status/recovery, use `status` mode actions (`status`, `retrieve`, `resume`, `list`).
5. Return deterministic summary keys:
   - `job_id` (if available)
   - `idempotency_key`
   - `run_name`
   - `run_dir` (resolved local run directory from CLI)
   - `output_root`
   - `persistent_run_dir` (when mirror succeeds)

## Scripts

- Unified runner:
  - estimate only:
    - `python scripts/run.py sab --payload payload.yaml --run-name sab-target-v1 --estimate-only`
  - full E2E:
    - `python scripts/run.py sab --payload payload.yaml --run-name sab-target-v1 --yes`
  - other modes:
    - `python scripts/run.py protein-design --payload payload.yaml --run-name pd-target-v1 --yes`
    - `python scripts/run.py protein-screen --payload payload.yaml --run-name ps-target-v1 --yes`
    - `python scripts/run.py sm-design --payload payload.yaml --run-name smd-target-v1 --yes`
    - `python scripts/run.py sm-screen --payload payload.yaml --run-name sms-target-v1 --yes`
    - `python scripts/run.py adme --payload payload.yaml --run-name adme-set-v1 --yes`
  - status/recovery:
    - `python scripts/run.py status --action status --run-name sab-target-v1`
    - `python scripts/run.py status --action retrieve --resource sab --job-id <job-id>`
    - `python scripts/run.py status --action resume --job-id <job-id> --run-name sab-target-v1`
    - `python scripts/run.py status --action list --limit 20`

## Guardrails

- Keep payload keys aligned with API body schema for selected mode.
- Use `/tmp/boltz-runs` for runtime download/checkpoint writes.
- Mirror finalized run directories to `/workspace/boltz-artifacts/boltz/<run_dir_name>/` for persistence.
- Reuse same slug for `--idempotency-key` and downloader `--name`.
- Never re-submit to resume a run; use status/retrieve/resume actions.
- For non-`status` modes, run `--estimate-only` before `--yes` when approval is required.
- Prefer the bundled runner over ad hoc raw CLI sequences unless debugging a specific CLI behavior.

## Resources

- Read [references/api.md](references/api.md) for raw HTTP endpoint mappings and mode-to-resource details.
- Read [references/results.md](references/results.md) for run directory layout and resume rules.
