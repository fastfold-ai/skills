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
  - Cost estimate before submission (`--estimate-only`)
  - Idempotent run naming (`--run-name` reused for idempotency/download naming)
  - Resume/download recovery (`status --action resume`)
  - Post-eviction recovery from the API without re-submitting (`status --action recover`)
  - Paginated per-item results for design/screen (`status --action list-results`)
  - Early stop for design/screen (`status --action stop`)
  - Permanent data deletion (`status --action delete-data`, irreversible)

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
  (design/screen only), and `delete-data`. The runner's `resume`/`recover` actions resume the
  result *download*, not compute.
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

## Runner Usage Pattern

- Estimate only:
  - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --estimate-only`
- Full run:
  - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --yes`

Status/recovery (`/tmp` is ephemeral; recover from the API + `/workspace`, never by re-submitting):

- `python scripts/run.py status --action status --run-name <slug>`
- `python scripts/run.py status --action retrieve --resource sab --job-id <id>`
- `python scripts/run.py status --action list-results --resource protein_design --job-id <id> --limit 5`
- `python scripts/run.py status --action resume --job-id <id> --run-name <slug>`
- `python scripts/run.py status --action recover --run-name <slug>` (auto-resolves job_id, mirrors to `/workspace`)
- `python scripts/run.py status --action stop --resource sm_design --job-id <id>` (design/screen only)
- `python scripts/run.py status --action delete-data --resource protein_design --job-id <id> --confirm-delete` (irreversible)
