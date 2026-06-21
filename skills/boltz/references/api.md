# Unified Boltz API Reference

Source of truth:

- Official API docs: `https://api.boltz.bio/docs/api/`
- CLI repo: `https://github.com/boltz-bio/boltz-api-cli`

Mode to CLI resource mapping:

- `sab` -> `predictions:structure-and-binding`
- `protein-design` -> `protein:design`
- `protein-screen` -> `protein:library-screen`
- `sm-design` -> `small-molecule:design`
- `sm-screen` -> `small-molecule:library-screen`
- `adme` -> `predictions:adme`

Raw HTTP endpoints (used as the reference contract):

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

Runner usage pattern:

- Estimate only:
  - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --estimate-only`
- Full run:
  - `python scripts/run.py <mode> --payload payload.yaml --run-name <slug> --yes`

Status/recovery pattern:

- `python scripts/run.py status --action status --run-name <slug>`
- `python scripts/run.py status --action retrieve --resource sab --job-id <id>`
- `python scripts/run.py status --action resume --job-id <id> --run-name <slug>`
