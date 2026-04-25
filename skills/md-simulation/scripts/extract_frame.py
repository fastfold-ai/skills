#!/usr/bin/env python3
"""
Extract a PDB frame from a completed OpenMM workflow trajectory.

Calls:
  POST /v1/workflows/openmm/<workflow_id>/extract-frame

Environment: FASTFOLD_API_KEY (see load_env.py for resolution order).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from _api import http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_artifact_url, validate_base_url, validate_workflow_id


def _as_number(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _safe_pdb_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return stem or "workflow"


def _latest_task_result(workflow_payload: dict) -> dict:
    tasks = workflow_payload.get("tasks") if isinstance(workflow_payload.get("tasks"), list) else []
    latest = tasks[-1] if tasks else {}
    result_raw = latest.get("result_raw_json") if isinstance(latest, dict) else {}
    return result_raw if isinstance(result_raw, dict) else {}


def _workflow_sim_length_ns(workflow_payload: dict) -> float | None:
    input_payload = workflow_payload.get("input_payload") if isinstance(workflow_payload.get("input_payload"), dict) else {}
    result_raw = _latest_task_result(workflow_payload)
    direct = _as_number(result_raw.get("sim_length_ns"))
    if direct is not None and direct > 0:
        return direct
    from_input = _as_number(input_payload.get("sim_length_ns"))
    if from_input is not None and from_input > 0:
        return from_input
    return None


def _download_file(url: str, out_path: Path) -> None:
    safe_url = validate_artifact_url(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(safe_url, timeout=180.0) as response:
        out_path.write_bytes(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a trajectory frame from a completed FastFold OpenMM workflow as PDB.",
    )
    parser.add_argument("workflow_id", help="OpenMM workflow ID.")
    parser.add_argument("--time-ns", type=float, required=True, help="Time to extract in ns.")
    parser.add_argument("--selection", default="protein or resname LIG", help="MDAnalysis atom selection.")
    parser.add_argument("--dt-in-ps", type=float, default=0.0, help="Timestep override in ps; 0 means auto.")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--json", action="store_true", help="Print full extraction response JSON.")
    parser.add_argument(
        "--download",
        default=None,
        help="Optional output path or directory to download the extracted PDB locally.",
    )
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    workflow_id = validate_workflow_id(args.workflow_id)
    if args.time_ns != args.time_ns or args.time_ns < 0:
        sys.exit("Error: --time-ns must be a non-negative number.")
    if args.dt_in_ps != args.dt_in_ps or args.dt_in_ps < 0:
        sys.exit("Error: --dt-in-ps must be 0 or a positive number.")
    selection = str(args.selection or "").strip()
    if not selection:
        sys.exit("Error: --selection must not be empty.")

    workflow_payload = http_json(base_url, "GET", f"/v1/workflows/{workflow_id}", api_key=api_key)
    sim_length_ns = _workflow_sim_length_ns(workflow_payload)
    if sim_length_ns is not None and args.time_ns > sim_length_ns:
        sys.exit(
            f"Error: --time-ns must be between 0 and {sim_length_ns:g} ns "
            "for this workflow's simulation duration."
        )

    workflow_name = str(workflow_payload.get("name") or workflow_id).strip()
    output_filename = f"{_safe_pdb_stem(workflow_name)}_extracted_frame.pdb"
    payload = http_json(
        base_url,
        "POST",
        f"/v1/workflows/openmm/{workflow_id}/extract-frame",
        api_key=api_key,
        body={
            "timeNs": float(args.time_ns),
            "selection": selection,
            "outputFilename": output_filename,
            "dtInPs": float(args.dt_in_ps),
        },
        timeout=300.0,
    )

    pdb_url = str(payload.get("pdbUrl") or "").strip()
    if not pdb_url:
        sys.exit("Error: extraction response did not include pdbUrl.")
    validate_artifact_url(pdb_url)

    downloaded_to: str | None = None
    if args.download:
        target = Path(args.download).expanduser()
        out_path = target / output_filename if target.exists() and target.is_dir() else target
        if out_path.suffix.lower() != ".pdb":
            out_path = out_path.with_suffix(".pdb")
        _download_file(pdb_url, out_path)
        downloaded_to = str(out_path)

    if args.json:
        out = dict(payload)
        if downloaded_to:
            out["downloadedTo"] = downloaded_to
        print(json.dumps(out, indent=2, default=str))
        return

    print(f"workflow_id: {workflow_id}")
    print(f"frame_index: {payload.get('frameIndex')}")
    print(f"requested_time_ns: {payload.get('requestedTimeNs')}")
    print(f"actual_time_ns: {payload.get('actualTimeNs')}")
    print(f"atom_count: {payload.get('atomCount')}")
    print(f"pdb: {pdb_url}")
    if downloaded_to:
        print(f"downloaded_to: {downloaded_to}")


if __name__ == "__main__":
    main()
