# Boltz Results, Persistence & Recovery

## Where results go

- Download to a POSIX path: `/tmp/boltz-runs/<slug>` (`--root-dir /tmp/boltz-runs --name <slug>`).
- `/tmp` is ephemeral — wiped on sandbox eviction.
- Persist to the durable, S3-backed workspace with `scripts/persist.sh /tmp/boltz-runs/<slug>`,
  which copies into `/workspace/boltz-artifacts/boltz/<slug>/`. The CLI can't write to `/workspace`
  directly (it's not a full POSIX filesystem), which is why the copy step exists.

## Run directory layout

`download-results` / `run` fetch the **complete** result set (it follows the remote cursor):

```
/tmp/boltz-runs/<slug>/
  .boltz-run.json            # CLI local run metadata
  results/
    <result_id>/metadata.json
    <result_id>/archive.tar.gz
    ...                      # one folder per item
```

To return first/top/ranked N, enumerate `results/` and read each `metadata.json` — the local set is
complete, so no manual API paging is needed. For a quick peek without downloading archives
(design/screen only), use `boltz-api <resource> list-results --id <id> --format jsonl`
(`--after-id` / `--max-items -1` to page). For `sab`/`adme`, results come back inline via
`boltz-api <resource> retrieve --id <id> --format json`.

## Naming / idempotency

- Use one stable slug per experiment, reused as both `--idempotency-key` and `--name`.
- Use a **new** slug for a new experiment; reuse the same slug only for idempotent retries/downloads
  (reusing a slug with a changed payload can collide with the prior job).

## Recovery after eviction (never re-submit)

The job lives server-side; recover from the API:

1. Find the job id (match `idempotency_key` to your slug):
   - `boltz-api <resource> list --limit 50 --format jsonl`
2. Re-download and persist:
   - `boltz-api download-results --id <id> --name <slug> --root-dir /tmp/boltz-runs`
   - `scripts/persist.sh /tmp/boltz-runs/<slug>`

A result set is only incomplete if `download-results` errored or the run is still `running`; re-run
the download (idempotent) rather than paging by hand.
