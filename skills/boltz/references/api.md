# Unified Boltz API Reference

Primary sources:

- API docs root: `https://api.boltz.bio/docs/`
- API reference: `https://api.boltz.bio/docs/api/`
- CLI repo: `https://github.com/boltz-bio/boltz-api-cli`

## Mode to CLI Resource Mapping

- `sab` -> `predictions:structure-and-binding`
- `protein-design` -> `protein:design`
- `protein-screen` -> `protein:library-screen`
- `sm-design` -> `small-molecule:design`
- `sm-screen` -> `small-molecule:library-screen`
- `adme` -> `predictions:adme`

## BoltzMol / BoltzProt Feature Coverage

This skill covers the API-visible features exposed for BoltzMol/BoltzProt/Boltz-2 workflows:

- **BoltzMol-1 small-molecule hit discovery**
  - **Generate** candidates -> `sm-design` (`small-molecule:design`)
  - **Screen** provided molecule libraries -> `sm-screen` (`small-molecule:library-screen`)
  - **Tier-1 ADME** support -> `adme` (`predictions:adme`) and ADME fields in design/screen results when present
  - **Property steering/filtering** -> pass `molecule_filters` and `chemical_space` in mode payload
- **BoltzProt-1 protein binder design**
  - **De novo binder generation** -> `protein-design` (`protein:design`)
  - **Protein library scoring/screening** -> `protein-screen` (`protein:library-screen`)
  - **Ranking metrics exposure** -> `binding_confidence`, `structure_confidence`, `iptm`, `min_interaction_pae`, etc. returned by API/CLI output
- **Boltz-2 structure + binding**
  - `sab` mode (`predictions:structure-and-binding`, model `boltz-2.1`)
- **Operational API features**
  - Cost estimate before submission (`estimate-cost`)
  - Idempotent run naming (`--idempotency-key`/`--name` reused per experiment)
  - Download recovery (`download-results --id <id>`)
  - Post-eviction recovery from the API without re-submitting (`list` + `download-results`)
  - Paginated per-item results for design/screen (`list-results`)
  - Early stop for design/screen (`stop`)
  - Permanent data deletion (`delete-data`, irreversible)

## Per-Resource Action Matrix

CLI subcommands available per resource (verified against `boltz-api <resource> --help`):

| Subcommand | sab | adme | protein-design | protein-screen | sm-design | sm-screen |
| --- | --- | --- | --- | --- | --- | --- |
| `estimate-cost` | yes | yes | yes | yes | yes | yes |
| `start` / `run` | yes | yes | yes | yes | yes | yes |
| `retrieve` | yes | yes | yes | yes | yes | yes |
| `list` | yes | yes | yes | yes | yes | yes |
| `list-results` | no | no | yes | yes | yes | yes |
| `stop` | no | no | yes | yes | yes | yes |
| `delete-data` | yes | yes | yes | yes | yes | yes |

Notes:

- There is no `pause`/`unpause` on any resource. Lifecycle controls are `start`, `stop`
  (design/screen only), and `delete-data`. `download-results` resumes the result *download*, not compute.
- `sab` and `adme` are short synchronous predictions: results come back via `retrieve` (no
  `list-results`), and they cannot be stopped.
- `delete-data` permanently deletes input/output/result data (the run record is kept with a
  `data_deleted_at` timestamp). It is irreversible; the runner gates it behind `--confirm-delete`.

## Raw HTTP Endpoints (Reference Contract)

- `sab` (`predictions:structure-and-binding`)
  - `POST /compute/v1/predictions/structure-and-binding`
  - `GET /compute/v1/predictions/structure-and-binding`
  - `GET /compute/v1/predictions/structure-and-binding/{id}`
  - `POST /compute/v1/predictions/structure-and-binding/{id}/delete-data`
  - `POST /compute/v1/predictions/structure-and-binding/estimate-cost`
- `adme` (`predictions:adme`)
  - `POST /compute/v1/predictions/adme`
  - `GET /compute/v1/predictions/adme`
  - `GET /compute/v1/predictions/adme/{id}`
  - `POST /compute/v1/predictions/adme/{id}/delete-data`
  - `POST /compute/v1/predictions/adme/estimate-cost`
- `sm-design` (`small-molecule:design`)
  - `POST /compute/v1/small-molecule/design`
  - `GET /compute/v1/small-molecule/design`
  - `GET /compute/v1/small-molecule/design/{id}`
  - `GET /compute/v1/small-molecule/design/{id}/results`
  - `POST /compute/v1/small-molecule/design/{id}/stop`
  - `POST /compute/v1/small-molecule/design/{id}/delete-data`
  - `POST /compute/v1/small-molecule/design/estimate-cost`
- `sm-screen` (`small-molecule:library-screen`)
  - `POST /compute/v1/small-molecule/library-screen`
  - `GET /compute/v1/small-molecule/library-screen`
  - `GET /compute/v1/small-molecule/library-screen/{id}`
  - `GET /compute/v1/small-molecule/library-screen/{id}/results`
  - `POST /compute/v1/small-molecule/library-screen/{id}/stop`
  - `POST /compute/v1/small-molecule/library-screen/{id}/delete-data`
  - `POST /compute/v1/small-molecule/library-screen/estimate-cost`
- `protein-design` (`protein:design`)
  - `POST /compute/v1/protein/design`
  - `GET /compute/v1/protein/design`
  - `GET /compute/v1/protein/design/{id}`
  - `GET /compute/v1/protein/design/{id}/results`
  - `POST /compute/v1/protein/design/{id}/stop`
  - `POST /compute/v1/protein/design/{id}/delete-data`
  - `POST /compute/v1/protein/design/estimate-cost`
- `protein-screen` (`protein:library-screen`)
  - `POST /compute/v1/protein/library-screen`
  - `GET /compute/v1/protein/library-screen`
  - `GET /compute/v1/protein/library-screen/{id}`
  - `GET /compute/v1/protein/library-screen/{id}/results`
  - `POST /compute/v1/protein/library-screen/{id}/stop`
  - `POST /compute/v1/protein/library-screen/{id}/delete-data`
  - `POST /compute/v1/protein/library-screen/estimate-cost`

## CLI Usage Pattern

Pick `<resource>` from the mapping above; reuse one `<slug>` as `--idempotency-key` and `--name`.

```bash
# Estimate (never bills), then submit after approval
boltz-api <resource> estimate-cost --input @yaml://payload.yaml      # + --model for sab/adme
boltz-api <resource> run --input @yaml://payload.yaml --idempotency-key <slug> --name <slug> --root-dir /tmp/boltz-runs
scripts/persist.sh /tmp/boltz-runs/<slug>                            # copy to S3-backed /workspace

# Inspect / lifecycle
boltz-api <resource> retrieve --id <id> --format json
boltz-api <resource> list --limit 20 --format jsonl
boltz-api <resource> list-results --id <id> --format jsonl          # design/screen only
boltz-api <resource> stop --id <id>                                 # design/screen only
boltz-api <resource> delete-data --id <id>                         # irreversible — confirm first
```

Recovery (`/tmp` is ephemeral; recover from the API, never by re-submitting): find the id with
`list` (match `idempotency_key`), then `download-results --id <id> --name <slug> --root-dir /tmp/boltz-runs`
and `persist.sh`.
