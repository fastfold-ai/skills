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

**Preferred (Sandwalk agent):** Set `BOLTZ_API_KEY` via Sandwalk **Integrations**
(Boltz / Fastfold Cloud provider wiring). Sandwalk mirrors configured provider keys into
the chat shell env for `shell.run`. Do **not** ask the user to paste the secret in chat.

**Alternatives:** local `.env` / `export BOLTZ_API_KEY=...`, or create a key in the
Boltz console at https://api.boltz.bio/console (Fastfold Cloud provider page:
https://cloud.fastfold.ai/integrations/providers?provider=boltz).

**Interactive machines:** the CLI also supports device-code login —
`boltz-api auth status` to check, `boltz-api auth login --device-code` to sign in.
Relay the URL and code the CLI prints. Only use this where a person is present to
complete the browser step; in a hosted sandbox prefer the key.

**If `BOLTZ_API_KEY` is missing:** stop after a failed `boltz-api` / `printenv BOLTZ_API_KEY`
check; tell the user to configure Integrations (or export / `.env`) and retry. Do not
hunt the filesystem for secrets.

## Install

- Check first: `boltz-api --version`.
- If `boltz-api` is missing: `curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`
  (Windows PowerShell: `irm https://install.boltz.bio/boltz-api/install.ps1 | iex`).
- It installs to `PATH`, `~/.local/bin`, or `~/.boltz/bin`. Don't use `pip install boltz-api`.
- When the CLI reports that an update is available or required, relay its message and the
  install command it prints rather than hardcoding a minimum version. Respect opt-outs
  such as `BOLTZ_API_NO_UPDATE_CHECK=1`.

## Golden rules

1. **Estimate, then confirm — every single `start`/`run`.** Run `estimate-cost` first, show the
   user the figure it returned, and only submit after they explicitly approve. Estimates never
   bill. A plan the user already agreed to, an earlier phase's approval, or a cost that looks
   trivial are **not** authorization — each billable submit needs a fresh yes. This holds even
   when tool calls are pre-approved (accept-edits / auto-accept / bypass modes); there you are
   the only cost gate. Never quote a dollar figure that didn't come from `estimate-cost`, and
   never extrapolate one estimate to a different size or payload. A design/screen run can be
   stopped early (`stop`) to cap spend; `sab`/`adme` are short and cannot be stopped. There is
   no pause/resume of compute.
2. **Save results to a durable location — where depends on your runtime (pick one).**
   - **Local agent (sandwalk, Claude Code, Codex, Cursor, or any local machine):** the
     filesystem is plain POSIX and persists across the session. Download straight into a project-relative
     output dir — use `--root-dir "${OUTPUT_DIR:-./outputs}/boltz"` (sandwalk sets `OUTPUT_DIR`;
     other agents fall back to `./outputs/boltz`). No copy step; **don't** use `persist.sh`.
   - **Hosted sandbox with an S3-backed `/workspace`:** the CLI can't download into `/workspace`
     directly (not a full POSIX filesystem), and `/tmp` is ephemeral (wiped on eviction). Download to
     `/tmp/boltz-runs/<slug>`, then copy to `/workspace` with `scripts/persist.sh`.
   - If unsure: `$OUTPUT_DIR` set or a writable `./outputs` ⇒ local agent; a `/workspace` mount ⇒
     hosted sandbox.
3. **Recover from the API, never re-submit.** The job lives server-side. If the local run dir is gone,
   find the job with `list` (match `idempotency_key`) and re-`download-results` by id. Never re-run a
   billable submit just to fetch results.

## Payload rules that bite

Get these wrong and the server returns a `400 VALIDATION_ERROR` with no field path.
Full shapes per mode are in [references/api.md](references/api.md).

- Entities are `{type, chain_ids, value}` — the field is **`value`** (not `sequence`) and
  **`chain_ids`** is an array (not `chain_id`), even for a single chain.
- **Every residue index is 0-based** (`epitope_residues`, `pocket_residues`, `crop_residues`,
  `design_motifs`, constraints, modifications, bonds). Mapping from a structure:
  `API index = label_seq_id − 1`, using `label_seq` and never author numbering.
- `binding` is a flat block with an explicit `type` — don't nest the variant name under it.
- Pass payloads as `--input @yaml:///absolute/path/payload.yaml` (or `@json://`). Not `@./file`,
  not `@file://`. Embed CIF/PDB bytes with `@data:///absolute/path/file.cif`.
- Use absolute paths and keep passing the same `--root-dir`; don't `cd` into the run directory.
- In permission-gated runtimes keep each call a top-level `boltz-api …` command — no `sh -c`,
  wrappers, or pipelines. Capture ids with `--raw-output --transform id`.

## Run sizing (design modes)

De novo design is generate-and-filter: you make many candidates and keep the rare good ones, so a
real campaign is **large**. `num_proteins` accepts 10–1,000,000, but 10 is a smoke test, not a
campaign — don't anchor on it. When the user names a count, honor it; when they don't, explain the
tiers and propose one:

| Tier | `num_proteins` | When |
| --- | --- | --- |
| Small screen | 20,000 | Quick look / tight budget |
| **Medium (recommended)** | **50,000** | Default for a real campaign |
| Large | 100,000 | Hard target / maximal coverage |

Present tiers as **counts**, never with a price attached unless `estimate-cost` returned that exact
figure for that exact tier. Estimate the tier the user leans toward, show that number, then apply
the spending gate.

**New target?** Before sizing anything, offer a target-exploration pass — a few 50-design scouting
runs that compare crop/epitope framings and pick the one that actually yields binders. Recommend it
for an unknown site or a large/multi-domain target; designing directly is fine for a
well-characterized site. Don't raise campaign size while exploration is still on the table — the
scouting yield is what informs the tier. See
[references/target_exploration.md](references/target_exploration.md).

For antibody or nanobody requests, recommend Boltz's curated scaffolds
(`binder_specification.type: boltz_curated`, `binder: boltz_antibody` / `boltz_nanobody`) and ask
whether the user wants custom scaffold/CDR control before authoring the payload.

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
boltz-api <resource> start --input @yaml://payload.yaml --idempotency-key <slug> \
  --raw-output --transform id                                          # prints job id
boltz-api <resource> retrieve --id <id> --format json                 # status / progress
boltz-api download-results --id <id> --name <slug> --root-dir <root> \
  --poll-interval-seconds 30                                           # 10 sab/adme, 30 screens, 60 design
boltz-api --format json download-status --name <slug> --root-dir <root>   # local progress, no API call

# Inspect / enumerate
boltz-api <resource> list --limit 20 --format jsonl                    # find jobs by idempotency_key
boltz-api <resource> list-results --id <id> --format jsonl            # per-item results (design/screen)
                                                                       #   page with --after-id / --max-items -1

# Lifecycle
boltz-api <resource> stop --id <id>                                    # design/screen only, caps spend
boltz-api <resource> delete-data --id <id>                            # permanent + irreversible — confirm first
```

Notes:
- `run` blocks until the job finishes. For a large design campaign prefer `start` +
  `download-results`, and launch the downloader through whatever long-running / non-blocking
  facility the runtime documents. Don't detach it with `&` or `nohup` unless the runtime
  documents shell backgrounding — some tool runners reap backgrounded children before
  `.boltz-run.json` is written. After launching it, report the job id, run name, and output
  directory; don't sit in a manual polling loop.
- Wall-clock time scales with the job: small `sab`/`adme` finish in minutes, large screens and
  design campaigns can run for hours. Don't quote a fixed duration.
- `run`/`download-results` fetch the **complete** result set into `<root>/<slug>/`.
  `sab`/`adme` land in `outputs/archive.tar.gz`; design/screen land in `results/` with an
  `index.jsonl`. See [references/results.md](references/results.md).
- Recover after losing the local run dir: `boltz-api <resource> list --limit 50 --format jsonl` to find
  the id, then `download-results --id <id> --name <slug> --root-dir <root>` (and `persist.sh` only on a
  hosted sandbox).

## Reading results

- **Design and screen:** rank by `binding_confidence` descending, from
  `<root>/<slug>/results/index.jsonl`. Tiebreak with `iptm` (higher better) and
  `min_interaction_pae` (lower better). `optimization_score` is not emitted for
  `protein:design` — don't sort by it there.
- **Structure-and-binding:** `metrics.json` is nested — per-sample metrics live under
  `best_sample.metrics`, and `binding_metrics` is a separate top-level object present only when
  `binding` was requested. Summarize the useful metrics and point the user at the CIF path.
- A designed binder comes back as `type: "protein"`, not `designed_protein` — select it by the
  `chain_ids` you assigned at submit time.
- Screened inputs that were filtered or failed validation are simply absent from results.
  Reconcile result count against input count (via the `external_id` you set) and say which dropped.

Details: [references/results.md](references/results.md).

## Payloads

Per-mode payload shapes and small copy-paste examples are in
[references/examples.md](references/examples.md). Pass them with `@yaml://<file>`. If unsure of a
mode's schema, check the example first — the estimate step also catches a bad payload cheaply before
any billing.

## Resources

- [references/api.md](references/api.md) — mode↔resource mapping, per-mode payload schemas, raw HTTP endpoints.
- [references/examples.md](references/examples.md) — payloads and prompt examples.
- [references/results.md](references/results.md) — run directory layout, ranking, persistence/recovery.
- [references/target_exploration.md](references/target_exploration.md) — pre-design scouting pass for new targets.
