# Boltz Results, Persistence & Recovery

## Where results go — depends on the runtime

Pick the `--root-dir` that matches where the agent is running:

### Local agent (sandwalk, Claude Code, Codex, Cursor, or any local machine)

- Plain POSIX filesystem that persists across the session — no S3/`/workspace` quirks.
- Download straight into a project-relative output dir: `--root-dir "${OUTPUT_DIR:-./outputs}/boltz" --name <slug>`.
  The sandwalk sets `OUTPUT_DIR` to its artifact dir (config `sandbox.output_dir`, default
  `./outputs`, alongside `./outputs/reports` and `./exports`); other agents simply fall back to `./outputs/boltz`.
- **Do not** run `scripts/persist.sh` here — there's nothing to mirror to.

### Hosted sandbox with an S3-backed `/workspace`

- Download to a POSIX path: `/tmp/boltz-runs/<slug>` (`--root-dir /tmp/boltz-runs --name <slug>`).
- `/tmp` is ephemeral — wiped on sandbox eviction.
- Persist to the durable, S3-backed workspace with `scripts/persist.sh /tmp/boltz-runs/<slug>`,
  which copies into `/workspace/boltz-artifacts/boltz/<slug>/`. The CLI can't write to `/workspace`
  directly (it's not a full POSIX filesystem), which is why the copy step exists.

Below, `<root>` is whichever root-dir you picked above.

Always pass the same absolute `<root>` to every follow-up command. Do **not** `cd`
into the run directory — later relative paths then resolve against the run dir
instead of the user's workspace.

## Run directory layout — differs by mode

`download-results` / `run` fetch the **complete** result set (it follows the remote cursor).
The layout is not the same for every mode.

### `sab` and `adme` (single synchronous prediction)

```
<root>/<slug>/
  .boltz-run.json            # CLI local run metadata, cursor, idempotency key
  outputs/archive.tar.gz     # contains prediction/{metrics.json,
                             #   sample_*_predicted_structure.cif, sample_*_pae.npz}
```

There is no `results/` directory and no `list-results` for these two modes.
Results are also available inline via `boltz-api <resource> retrieve --id <id> --format json`.

### Design and screen modes (`protein:design`, `protein:library-screen`, `small-molecule:design`, `small-molecule:library-screen`)

```
<root>/<slug>/
  .boltz-run.json            # CLI local run metadata
  run.json                   # sanitized remote run record
  results/
    index.jsonl              # one line per design/hit: sequence or SMILES, metrics, local paths
    <result_id>/metadata.json
    <result_id>/archive.tar.gz
    ...                      # one folder per item
```

`results/index.jsonl` is the fastest way to rank — read it instead of walking every
per-result folder. For a quick peek without downloading archives, use
`boltz-api <resource> list-results --id <id> --format jsonl`
(`--after-id` / `--max-items -1` to page).

## Ranking results

### Design and screen

Rank by **`binding_confidence` descending**. Tiebreakers: `iptm` (higher is better),
`min_interaction_pae` (lower is better).

`optimization_score` is **not** emitted for `protein:design` — do not sort by it there.

### Structure-and-binding metrics are nested

`metrics.json` is not flat:

- `best_sample.metrics` and each `all_sample_results[].metrics` hold lowercase keys:
  `structure_confidence`, `ptm`, `iptm`, `ligand_iptm`, `protein_iptm`, `complex_plddt`,
  `complex_iplddt`, `complex_pde`, `complex_ipde`.
- `binding_metrics` is a separate **top-level** object, present only when `binding` was requested.
  - `ligand_protein_binding` → `binding_confidence` and `optimization_score`.
  - `protein_protein_binding` → `binding_confidence` only.

`binding_confidence` (0–1) is the confidence that binding occurs — the primary signal
for whether the complex binds at all. `optimization_score` ranks binding **strength**
for lead optimization (higher = stronger predicted binding), and is emitted only for
`ligand_protein_binding`.

### Designed binder entity gotcha

In `protein:design` output the generated binder comes back as `type: "protein"`,
**not** `type: "designed_protein"`, with the sequence DSL resolved to a real amino-acid
sequence in `value`. Select the binder by the `chain_ids` you assigned at submit time —
never by `type == "designed_protein"`, which matches nothing in the results.

### Screen inputs that vanish

In library screens, a molecule or protein that was filtered out or failed validation
does not appear in the results. Reconcile result count against input count and tell the
user which inputs dropped out rather than silently reporting a shorter list.
The optional per-item `id` you submit is echoed back as `external_id`, which is what
makes that reconciliation possible — always set it.

## Naming / idempotency

- Use one stable slug per experiment, reused as both `--idempotency-key` and `--name`.
- Use a **new** slug for a new experiment; reuse the same slug only for idempotent retries/downloads
  (reusing a slug with a changed payload can collide with the prior job).

## Checking progress

- Local downloader state (no API call): `boltz-api --format json download-status --name <slug> --root-dir <root>`.
- Remote job state: `boltz-api <resource> retrieve --id <id> --format json`.

Prefer `download-status` when the user has the run name and only wants progress.
Do not sit in a manual polling loop — report status when asked, or schedule a
follow-up check if the runtime supports one.

## Recovery after losing the local run dir (never re-submit)

The job lives server-side; recover from the API (needed on a hosted sandbox after eviction, or any time
the local `<root>/<slug>` is gone):

1. Find the job id (match `idempotency_key` to your slug):
   - `boltz-api <resource> list --limit 50 --format jsonl`
2. Re-download into your runtime's `<root>`:
   - `boltz-api download-results --id <id> --name <slug> --root-dir <root>`
   - On a hosted sandbox only, then mirror: `scripts/persist.sh /tmp/boltz-runs/<slug>`

Never run `start`/`run` again to resume a job — that bills a second time for work the
server already did. If a job genuinely failed, fix the payload and submit under a **new**
idempotency key.

A result set is only incomplete if `download-results` errored or the run is still `running`; re-run
the download (idempotent) rather than paging by hand.
