#!/usr/bin/env python3
"""
Fetch AlphaFold DB PDB structure + PAE JSON for a given UniProt ID.

Mirrors the UI's "Fetch UniProt" action on /openmm/new:

    1. GET https://alphafold.ebi.ac.uk/api/prediction/<UNIPROT_ID>
    2. Parse entry[0].pdbUrl and entry[0].paeDocUrl
    3. Download both and validate the PAE JSON parses

On success, writes:
    AF-<UNIPROT_ID>.pdb   (structure)
    AF-<UNIPROT_ID>.json  (normalized PAE)

into --out-dir (default: current directory) and prints their paths.

Example (chain with submit_manual_af_pae):
    python scripts/fetch_uniprot.py P00698 --out-dir /tmp --json

Stdlib only. No authentication required (public AlphaFold DB).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ALPHAFOLD_PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
_UNIPROT_ID_RE = re.compile(r"^[A-Z0-9]{6,10}$")
_ALLOWED_DOWNLOAD_HOSTS = (
    "alphafold.ebi.ac.uk",
    "alphafold.com",
)


def _validate_uniprot_id(value: str) -> str:
    clean = str(value or "").strip().upper()
    if not _UNIPROT_ID_RE.match(clean):
        sys.exit(
            "Error: invalid UniProt ID. Expected 6-10 uppercase letters/digits (e.g. P00698)."
        )
    return clean


def _validate_download_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        sys.exit("Error: missing download URL from AlphaFold DB response.")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        sys.exit(f"Error: AlphaFold DB URL must use https (got {url}).")
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in _ALLOWED_DOWNLOAD_HOSTS):
        sys.exit(f"Error: unexpected AlphaFold DB host {host!r} for {url}.")
    return url


def _http_get(url: str, *, timeout: float = 30.0) -> bytes:
    request = Request(url=url, method="GET", headers={"Accept": "*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        sys.exit(f"Error: HTTP {error.code} from {url}")
    except URLError as error:
        sys.exit(f"Error: network error while requesting {url}: {error.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch AlphaFold DB PDB + PAE JSON for a UniProt ID.",
    )
    parser.add_argument("uniprot_id", help="UniProt accession (e.g. P00698).")
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write AF-<id>.pdb and AF-<id>.json (default: current directory).",
    )
    parser.add_argument("--json", action="store_true", help="Print result as JSON to stdout.")
    args = parser.parse_args()

    uniprot_id = _validate_uniprot_id(args.uniprot_id)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prediction_url = ALPHAFOLD_PREDICTION_URL.format(uniprot_id=uniprot_id)
    prediction_raw = _http_get(prediction_url)
    try:
        prediction_payload = json.loads(prediction_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.exit(f"Error: AlphaFold DB prediction endpoint returned invalid JSON for {uniprot_id}.")

    if not isinstance(prediction_payload, list) or not prediction_payload:
        sys.exit(f"Error: no AlphaFold prediction found for UniProt {uniprot_id}.")
    entry = prediction_payload[0]
    if not isinstance(entry, dict):
        sys.exit("Error: unexpected prediction payload shape from AlphaFold DB.")

    structure_url = _validate_download_url(str(entry.get("pdbUrl") or "").strip())
    pae_url = _validate_download_url(str(entry.get("paeDocUrl") or "").strip())

    structure_bytes = _http_get(structure_url)
    pae_bytes = _http_get(pae_url)

    # Validate PAE is JSON (the UI does JSON.parse(paeText) as its only check).
    try:
        pae_json = json.loads(pae_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.exit(f"Error: PAE file at {pae_url} is not valid JSON.")
    if not isinstance(pae_json, (list, dict)):
        sys.exit(f"Error: PAE file at {pae_url} is not a JSON array or object.")

    pdb_path = out_dir / f"AF-{uniprot_id}.pdb"
    pae_path = out_dir / f"AF-{uniprot_id}.json"
    pdb_path.write_bytes(structure_bytes)
    pae_path.write_bytes(pae_bytes)

    result = {
        "uniprot_id": uniprot_id,
        "pdb_path": str(pdb_path),
        "pae_path": str(pae_path),
        "source": {
            "prediction_url": prediction_url,
            "structure_url": structure_url,
            "pae_url": pae_url,
        },
        "pdb_size_bytes": len(structure_bytes),
        "pae_size_bytes": len(pae_bytes),
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(str(pdb_path))
    print(str(pae_path))


if __name__ == "__main__":
    main()
