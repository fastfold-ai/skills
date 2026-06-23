---
name: boltz
description: Run Boltz API workflows via the official `boltz-api` CLI — structure-and-binding, protein design/screen, small-molecule design/screen, ADME prediction, and job status/recovery. Use when the user wants to estimate, submit, monitor, fetch results for, stop, or recover a Boltz API job.
---

# Boltz

## Overview

Drive the official `boltz-api` CLI directly for all Boltz workflows, following the three guardrails
below and using the bundled persistence helper to keep results.

Mode → CLI resource:

| Mode | `<resource>` | Extra flag |
| --- | --- | --- |
| structure-and-binding (`sab`) | `predictions:structure-and-binding` | `--model boltz-2.1` |
| protein design | `protein:design` | — |
| protein screen | `protein:library-screen` | — |
| small-molecule design | `small-molecule:design` | — |
| small-molecule screen | `small-molecule:library-screen` | — |
| ADME | `predictions:adme` | `--model adme-v1` |

## Authentication

- `BOLTZ_API_KEY` must be set before any command (env injection in hosted runtimes, or a local `.env`/shell export).
- If it is missing, stop and ask the user to set it; don't proceed.
- Fastfold Cloud: provider setup at `https://cloud.fastfold.ai/integrations/providers?provider=boltz`;
  create a key in the Boltz console at `https://api.boltz.bio/console`. Restart the session so the env var is visible.

## Install

- If `boltz-api` is missing: `curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`
- It installs to `PATH`, `~/.local/bin`, or `~/.boltz/bin`. Don't use `pip install boltz-api`.

## Golden rules

1. **Estimate, then confirm.** Run `estimate-cost` first, show the user the cost, and only run a
   billable `start`/`run` after they explicitly approve. Estimates never bill. A design/screen run
   can be stopped early (`stop`) to cap spend; `sab`/`adme` are short and cannot be stopped. There is
   no pause/resume of compute.
2. **Save results to a durable location — where depends on your runtime (pick one).**
   - **Local agent (Fastfold Agent CLI, Claude Code, Codex, Cursor, or any local machine):** the
     filesystem is plain POSIX and persists across the session. Download straight into a project-relative
     output dir — use `--root-dir "${OUTPUT_DIR:-./outputs}/boltz"` (Fastfold Agent CLI sets `OUTPUT_DIR`;
     other agents fall back to `./outputs/boltz`). No copy step; **don't** use `persist.sh`.
   - **Hosted sandbox with an S3-backed `/workspace`:** the CLI can't download into `/workspace`
     directly (not a full POSIX filesystem), and `/tmp` is ephemeral (wiped on eviction). Download to
     `/tmp/boltz-runs/<slug>`, then copy to `/workspace` with `scripts/persist.sh`.
   - If unsure: `$OUTPUT_DIR` set or a writable `./outputs` ⇒ local agent; a `/workspace` mount ⇒
     hosted sandbox.
3. **Recover from the API, never re-submit.** The job lives server-side. If the local run dir is gone,
   find the job with `list` (match `idempotency_key`) and re-`download-results` by id. Never re-run a
   billable submit just to fetch results.

## CLI cheat-sheet

Pick `<resource>` from the table above; reuse one `<slug>` per experiment as both `--idempotency-key`
and `--name`. Payloads are passed as files via `@yaml://payload.yaml`.

Set `<root>` per rule 2 — local agent: `"${OUTPUT_DIR:-./outputs}/boltz"`; hosted sandbox:
`/tmp/boltz-runs` (then `persist.sh`).

```bash
# Estimate (never bills)
boltz-api <resource> estimate-cost --input @yaml://payload.yaml        # + --model for sab/adme

# Submit + wait + download (after the user approves)
boltz-api <resource> run --input @yaml://payload.yaml \
  --idempotency-key <slug> --name <slug> --root-dir <root>
# hosted sandbox only: scripts/persist.sh /tmp/boltz-runs/<slug>       # copy to /workspace

# Or submit async, then poll + download later
boltz-api <resource> start --input @yaml://payload.yaml --idempotency-key <slug>   # prints job id
boltz-api <resource> retrieve --id <id> --format json                 # status / progress
boltz-api download-results --id <id> --name <slug> --root-dir <root>
# hosted sandbox only: scripts/persist.sh /tmp/boltz-runs/<slug>

# Inspect / enumerate
boltz-api <resource> list --limit 20 --format jsonl                    # find jobs by idempotency_key
boltz-api <resource> list-results --id <id> --format jsonl            # per-item results (design/screen)
                                                                       #   page with --after-id / --max-items -1

# Lifecycle
boltz-api <resource> stop --id <id>                                    # design/screen only, caps spend
boltz-api <resource> delete-data --id <id>                            # permanent + irreversible — confirm first
```

Notes:
- `run`/`download-results` fetch the **complete** result set into `<root>/<slug>/results/<result_id>/`.
  To return top/first N, read that directory (each item has `metadata.json`), or use `list-results`.
- Recover after losing the local run dir: `boltz-api <resource> list --limit 50 --format jsonl` to find
  the id, then `download-results --id <id> --name <slug> --root-dir <root>` (and `persist.sh` only on a
  hosted sandbox).

## Payloads

Per-mode payload shapes and small copy-paste examples are in
[references/examples.md](references/examples.md). Pass them with `@yaml://<file>`. If unsure of a
mode's schema, check the example first — the estimate step also catches a bad payload cheaply before
any billing.

## Resources

- [references/api.md](references/api.md) — mode↔resource mapping and raw HTTP endpoints.
- [references/examples.md](references/examples.md) — payloads and prompt examples.
- [references/results.md](references/results.md) — run directory layout and persistence/recovery notes.
