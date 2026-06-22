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

Coverage alignment with new Boltz releases:

- BoltzMol-1 workflows map to:
  - `sm-design` (de novo generation)
  - `sm-screen` (library screening)
  - `adme` (Tier-1 ADME prediction)
- BoltzProt-1 workflows map to:
  - `protein-design` (binder generation)
  - `protein-screen` (library screening)
- Boltz-2 structure/binding maps to:
  - `sab`

## Authentication

- `BOLTZ_API_KEY` must be available before running commands.
- Accept any of these auth setups:
  - runtime/env injection already provides `BOLTZ_API_KEY` (preferred in hosted agent runtimes)
  - local `.env`/shell env exports `BOLTZ_API_KEY` for the active agent process
- If `BOLTZ_API_KEY` is missing, stop and ask the user to set it using their runtime method.
- Fastfold Cloud-specific option (if relevant for the user):
  - configure Boltz provider access: `https://cloud.fastfold.ai/integrations/providers?provider=boltz`
  - create/get API key in Boltz console: `https://api.boltz.bio/console`
  - restart sandbox/session so the new env var is visible to commands

## Boltz API CLI bootstrap

- Official install (when needed):
  - `curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`
- The runtime may not have `boltz-api` installed yet.
- Prefer `python scripts/run.py ...` for run/submit/download flows (it enforces the spend gate,
  workspace persistence, and recovery manifest). Raw `boltz-api ...` is allowed for read-only
  inspection or capabilities the wrapper does not expose — see "Runner vs. raw CLI" below.
- The bundled runner auto-installs `boltz-api` with the official installer when missing, then resolves the binary from:
  - `PATH`
  - `~/.local/bin/boltz-api`
  - `~/.boltz/bin/boltz-api`
- Do not use ad hoc install methods (for example `pip install boltz-api`) unless the official installer fails and the user explicitly requests a fallback.
- If auto-install fails (missing `curl`/`sh` or installer error), report the failure and stop.

## When to Use This Skill

- User explicitly wants Boltz API execution (`boltz-api` flows).
- User needs end-to-end run with cost estimate, submission, waiting/downloading, and summary.
- User needs status/recovery for an existing Boltz job.
- User asks for Boltz endpoints, payload mapping, or run artifacts.

## Workflow

0. Confirm mode:
   - `sab`, `protein-design`, `protein-screen`, `sm-design`, `sm-screen`, `adme`, `status`.
1. Run through the bundled runner (`python scripts/run.py ...`); it auto-installs `boltz-api` when missing.
2. For non-`status` modes, prepare payload file in working directory (for example: `payload.yaml`).
3. Run estimate first (never billable):
   - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --estimate-only`
4. STOP and confirm before submitting (mandatory):
   - Show the user the estimated cost, the mode, and the run name.
   - Wait for the user to explicitly approve. Do NOT run `--yes` in the same turn as the estimate.
   - `--yes` submits a real, billable job to the Boltz API. Billing accrues as work runs, so submit deliberately.
   - For `protein-design`, `protein-screen`, `sm-design`, `sm-screen`: the run can be stopped early
     (see step 6), so mention this when confirming — the user can cancel an in-progress run to cap spend.
   - For `sab` and `adme`: these are short synchronous predictions with no stop endpoint, so there is
     nothing to cancel once submitted; be extra clear before approving these.
   - Only run the submit command after the user clearly says to proceed (e.g. "yes", "go ahead", "submit").
   - If the user only asked for an estimate/cost, stop after step 3 and do not submit at all.
5. After explicit approval, run full end-to-end:
   - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --yes`
6. For status/recovery, use `status` mode actions (`status`, `retrieve`, `resume`, `recover`, `stop`, `list`).
   - Stop an in-progress design/screen run early (caps further spend):
     - `python scripts/run.py status --action stop --resource <protein_design|protein_screen|sm_design|sm_screen> --job-id <job-id>`
   - If the user asks to cancel / stop / abort a running design or screen, do this immediately; do not wait for completion.
   - `sab` and `adme` cannot be stopped (no stop endpoint); they finish quickly on their own.
7. Return deterministic summary keys:
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
    - `python scripts/run.py status --action list-results --resource protein_design --job-id <job-id> --limit 5` (paginated per-item results; `--max-items -1` for all)
    - `python scripts/run.py status --action resume --job-id <job-id> --run-name sab-target-v1`
    - `python scripts/run.py status --action recover --run-name sab-target-v1` (re-download + persist after sandbox eviction; auto-resolves the job from the workspace manifest or the API)
    - `python scripts/run.py status --action stop --resource sm_design --job-id <job-id>` (design/screen only)
    - `python scripts/run.py status --action delete-data --resource protein_design --job-id <job-id> --confirm-delete` (irreversible)
    - `python scripts/run.py status --action list --limit 20`

## Job Lifecycle & Actions

Inspect the run state first (cheap, never billable), then proactively offer the right control.
Use `status --action retrieve` (or `status`) to read `status`/`progress` before suggesting an action.

| Action | What it does | Modes | Runner command | Billable / destructive |
| --- | --- | --- | --- | --- |
| inspect (remote) | Status, progress, and (for `sab`/`adme`) inline results | all | `status --action retrieve --resource <r> --job-id <id>` | no |
| inspect (local) | Local checkpoint state; auto-restores from workspace mirror | all | `status --action status --run-name <slug>` | no |
| list jobs | Find jobs / job ids by `idempotency_key` | all | `status --action list --limit <n>` | no |
| list results | Paginated per-item results without downloading archives | design/screen only | `status --action list-results --resource <r> --job-id <id>` | no |
| fetch + persist | Download full result set and mirror to `/workspace` | all | `status --action resume --job-id <id> --run-name <slug>` | no |
| recover | Re-resolve + re-download after sandbox eviction | all | `status --action recover --run-name <slug>` | no |
| stop early | Cancel an in-progress run to cap further spend | design/screen only | `status --action stop --resource <r> --job-id <id>` | no (caps spend) |
| delete data | Permanently delete input/output/result data | all | `status --action delete-data --resource <r> --job-id <id> --confirm-delete` | destructive, irreversible |

There is **no pause/resume of compute** — a job cannot be paused and un-paused. "resume" here means
resuming the *download* of already-computed results (`download-results`), not restarting compute.
The only lifecycle controls are start, stop (design/screen), and delete-data.

Proactively offer actions based on state:

- Run is `running` and the user wants to abort, or it's clearly overshooting cost → offer `stop`
  (design/screen only). Act immediately when the user says cancel/stop/abort; don't wait for completion.
- Run is `running` and the user asks for partial results → use `list-results` / `retrieve` to show
  what's done so far rather than implying you must wait.
- Run is `succeeded` and the user wants results → `resume` (persists to `/workspace`); for a quick
  peek use `list-results`.
- Local `/tmp` state is missing (sandbox evicted) → `recover` (never re-submit).
- User wants cleanup or to delete sensitive data → confirm explicitly, then `delete-data --confirm-delete`.
- `sab`/`adme` are short and have no `stop`; don't offer to cancel them — they finish on their own.

## Runner vs. raw CLI

The bundled runner is preferred, but not mandatory. It exists to enforce three invariants that raw
CLI calls do not: the estimate→confirm spend gate before `--yes`, the submit-time recovery
manifest written to `/workspace`, and mirroring downloaded results to `/workspace`. Treat those
invariants as the actual rule — the runner is just the easy way to satisfy them.

Use the raw `boltz-api` CLI directly when it helps, especially for:

- **Read-only / inspection**: `retrieve`, `list`, `list-results`, `estimate-cost`, `config`,
  `admin:usage`, etc. These are safe; reach for raw CLI whenever you need a flag the runner does not
  expose — e.g. `--before-id` paging, `--transform`/`--format` shaping, `--workspace-id`, or admin
  commands.
- **Capabilities the wrapper lacks**: richer payload flags (templates, MSA modes, `molecule_filters`,
  `chemical_space`), debugging a specific CLI behavior, or any subcommand not mapped in `run.py`.

When you drop to raw CLI for a **mutating / billable / durability-critical** action
(`start`/`run`, `download-results`, `stop`, `delete-data`), you must preserve the invariants yourself:

- Run `estimate-cost` first and get explicit user approval before any billable `start`/`run`.
- After downloading results to `/tmp/boltz-runs/<slug>`, mirror them to
  `/workspace/boltz-artifacts/boltz/<slug>/` so they survive sandbox eviction.
- Record the `job_id` + `run-name` somewhere durable (e.g. write/append the workspace `manifest.json`)
  so the run stays recoverable.
- Prefer reusing the run-name slug as the `idempotency_key`.

If the runner is missing something that mutating flows need often, prefer extending `run.py` over
making one-off raw calls a habit — but a single well-justified raw call is fine. Don't ask the user
to install `boltz-api` manually; let the runner (or `bootstrap`) handle it first.

## Sandbox Persistence & Recovery

The sandbox `/tmp` tree is ephemeral — it is wiped whenever the sandbox is evicted or recreated.
The durable sources of truth are the **Boltz API** (the job itself) and the persistent
**`/workspace/boltz-artifacts/boltz/<run-name>/`** mirror.

- The run-name slug is reused as the `idempotency_key`, so it is the stable handle for a job.
- At submit time the runner writes `manifest.json` (`run_name` + `job_id` + `resource`) to the
  workspace immediately, so a job stays recoverable even if the submit/download wait is interrupted.
- Never re-submit (`--yes`) to get results — that bills again and may not even be possible if the
  payload is gone. To retrieve results, recover from the API instead.

Recovery flow when `/tmp` state is lost (e.g. `status` reports "Run metadata does not exist"):

1. One-shot: `python scripts/run.py status --action recover --run-name <slug>`
   - Resolves `job_id` from the workspace manifest, or by matching `idempotency_key` in the API,
     then re-downloads artifacts and mirrors them to the workspace.
   - If the run-name is unknown, find the job first with `status --action list --limit 20`, then
     pass `--job-id <id>` to `recover` (or `resume`).
2. The `status` action also auto-restores the workspace mirror back into `/tmp` before reading
   local checkpoint state.

Whenever the user asks to fetch / retrieve / download results, persist them: use `recover` or
`resume` (both mirror to `/workspace`), never a raw download that only writes to `/tmp`.

### Pagination & completeness (large result sets)

You do not need to hand-roll API pagination — the bundled runner already fetches the complete set:

- **Per-result artifacts** (e.g. 1000 protein designs): `resume`/`recover` call `download-results`
  with `--download-mode everything`, which walks the remote result cursor and downloads **every**
  item (concurrently). After it finishes, the full set lives under
  `<run_dir>/results/<result_id>/` — one folder per item.
- To return "first N", "top N", or rank/sort by a metric, **enumerate the downloaded
  `results/` directory** (read each item's `metadata.json`), not a partial API page. Reading the
  local mirror is complete and avoids per-call API limits.
- **Job discovery** (the `recover` lookup and `list`): the CLI list is cursor-paginated. The
  recovery scan uses `--max-items -1` so it auto-paginates across **all** jobs and won't miss the
  target in a busy workspace. For a human-facing `list`, raise `--limit` (default 20) as needed.
- Only treat a result set as incomplete if `download-results` reported an error or the run is still
  `running`; in that case re-run `resume`/`recover` (idempotent) rather than paging manually.

## Quick Examples

For 1-2 small examples per use case (SAB, protein design/screen, small-molecule design/screen, ADME, status), use:

- [references/examples.md](references/examples.md)

## Guardrails

- Keep payload keys aligned with API body schema for selected mode.
- Use `/tmp/boltz-runs` for runtime download/checkpoint writes, but treat it as ephemeral — it is wiped on sandbox eviction. Durable state lives in the Boltz API and `/workspace/boltz-artifacts/boltz/<run-name>/`.
- Mirror finalized run directories to `/workspace/boltz-artifacts/boltz/<run_dir_name>/` for persistence.
- When the user asks to fetch/retrieve/download results, ALWAYS persist them with `recover`/`resume` (which mirror to `/workspace`); never leave results only in `/tmp`.
- Reuse same slug for `--idempotency-key` and downloader `--name`.
- Never re-submit (`--yes`) to recover a run or get results; use status/retrieve/resume/recover actions. Re-submitting bills again and is not a recovery path.
- If `/tmp` run metadata is missing (sandbox was evicted), recover from the API: `status --action recover --run-name <slug>` (or `status --action list` then `recover`/`resume` with `--job-id`).
- For non-`status` modes, ALWAYS run `--estimate-only` first, then STOP, surface the cost, and get explicit user approval before running `--yes`. Never chain estimate and submit in one turn.
- `--yes` is a billable submission to the Boltz API. Default to confirming with the user, even if the original request looks like it wants the full run — when in doubt, estimate and ask.
- Design/screen runs (`protein-design`, `protein-screen`, `sm-design`, `sm-screen`) can be stopped early with `status --action stop` to cap spend; offer this when confirming and act on it immediately if the user asks to cancel. `sab`/`adme` have no stop endpoint.
- Prefer the bundled runner for run/submit/download (it enforces the spend gate, workspace persistence, and recovery manifest). Raw `boltz-api` is fine for read-only inspection or capabilities the runner lacks — but when using raw CLI for a billable/mutating action, preserve those invariants yourself (see "Runner vs. raw CLI").
- Never ask the user to manually install `boltz-api` before running the bundled runner; let the runner bootstrap the CLI first.

## Resources

- Read [references/api.md](references/api.md) for raw HTTP endpoint mappings and mode-to-resource details.
- Read [references/results.md](references/results.md) for run directory layout and resume rules.
- Read [references/examples.md](references/examples.md) for copy-paste small payloads and user-facing prompt examples.
