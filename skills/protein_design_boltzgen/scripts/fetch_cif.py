#!/usr/bin/env python3
"""
Fetch and normalize mmCIF files for BoltzGen design specs.

Supports:
- Download from RCSB by PDB id.
- Normalize existing local CIF files (line endings, control chars, trailing newline).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RCSB_CIF_URL = "https://files.rcsb.org/download/{pdb_id}.cif"


def fetch_cif_from_rcsb(pdb_id: str, timeout: float = 60.0) -> bytes:
    pdb = pdb_id.strip().upper()
    if not re.fullmatch(r"[A-Za-z0-9]{4}", pdb):
        sys.exit(f"Error: Invalid PDB id '{pdb_id}'. Expected 4 alphanumeric characters.")
    url = RCSB_CIF_URL.format(pdb_id=pdb)
    request = Request(url=url, method="GET", headers={"Accept": "text/plain"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.getcode() != 200:
                sys.exit(f"Error: Unexpected status {response.getcode()} while downloading {url}")
            return response.read()
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        sys.exit(f"Error: Failed to download CIF for {pdb} ({error.code}): {body}")
    except URLError as error:
        sys.exit(f"Error: Network error while downloading CIF for {pdb}: {error.reason}")


def normalize_cif_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    # keep printable characters + tabs/newlines
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (" " <= ch <= "~"))
    # trim trailing spaces
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    if not text.endswith("\n"):
        text += "\n"
    return text


def validate_cif(text: str, source_label: str) -> None:
    if "data_" not in text[:200]:
        sys.exit(f"Error: {source_label} does not look like a valid mmCIF (missing data_ header).")
    if "_atom_site." not in text:
        print(
            f"Warning: {source_label} has no _atom_site table; structure may be incomplete.",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch or normalize a CIF file for BoltzGen.")
    parser.add_argument("--pdb-id", help="4-char PDB id to fetch from RCSB (e.g. 5cqg).")
    parser.add_argument("--source-file", help="Existing local CIF file to normalize.")
    parser.add_argument("--out-dir", default=".", help="Output directory (default: current directory).")
    parser.add_argument("--output-name", default=None, help="Output file name (default: <pdb>.cif or source name).")
    args = parser.parse_args()

    if not args.pdb_id and not args.source_file:
        parser.error("Provide --pdb-id or --source-file.")
    if args.pdb_id and args.source_file:
        parser.error("Use either --pdb-id or --source-file, not both.")

    if args.pdb_id:
        raw = fetch_cif_from_rcsb(args.pdb_id)
        default_name = f"{args.pdb_id.strip().lower()}.cif"
        source_label = f"PDB:{args.pdb_id.strip().upper()}"
    else:
        source = Path(args.source_file).expanduser().resolve()
        if not source.exists() or not source.is_file():
            sys.exit(f"Error: source file not found: {source}")
        raw = source.read_bytes()
        default_name = source.name
        source_label = str(source)

    normalized = normalize_cif_text(raw)
    validate_cif(normalized, source_label)

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = args.output_name or default_name
    if not out_name.lower().endswith(".cif"):
        out_name = f"{out_name}.cif"
    out_path = out_dir / out_name
    out_path.write_text(normalized, encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
