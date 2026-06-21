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
  - Early stop for design/screen (`status --action stop`)

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

Status/recovery:

- `python scripts/run.py status --action status --run-name <slug>`
- `python scripts/run.py status --action retrieve --resource sab --job-id <id>`
- `python scripts/run.py status --action resume --job-id <id> --run-name <slug>`
- `python scripts/run.py status --action stop --resource sm_design --job-id <id>`
