#!/usr/bin/env python3
"""
Generate and validate an OpenMMDL script via /v1/workflows/openmmdl/prepare-script.

This script uploads topology/ligand files to Library, builds workflow_input, then
calls the backend prepare endpoint to receive generated script content and
preprocessing metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _api import http_json, upload_library_file_and_get_ref
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url


def _load_json_file(path_str: str) -> dict:
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        sys.exit(f"Error: JSON file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.exit(f"Error: failed to parse JSON file {path}: {exc}")
    if not isinstance(payload, dict):
        sys.exit(f"Error: input JSON must be an object: {path}")
    return payload


def _deep_merge_dict(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def _effective_workflow_input(prepared_payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    prepared_input = prepared_payload.get("workflow_input")
    if isinstance(prepared_input, dict):
        return prepared_input
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare OpenMMDL script from topology + optional ligands.",
    )
    parser.add_argument("--topology", required=True, help="Path to topology file (.pdb/.cif/.mmcif).")
    parser.add_argument(
        "--ligand",
        action="append",
        default=[],
        help="Path to ligand file (repeat for multiple ligands).",
    )
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--simulation-name", default=None, help="workflow_input.name.")
    parser.add_argument(
        "--run-analysis",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Set workflow_input.run_analysis true/false.",
    )
    parser.add_argument("--sim-length-ns", type=float, default=None, help="Set workflow_input.sim_length_ns.")
    parser.add_argument("--step-time-ps", type=float, default=None, help="Set workflow_input.step_time_ps.")
    parser.add_argument("--analysis-cpus", type=int, default=None, help="Set workflow_input.analysis_cpus.")
    parser.add_argument("--failure-retries", type=int, default=None, help="Set workflow_input.failure_retries.")
    parser.add_argument(
        "--ligand-selection",
        default=None,
        help="Set workflow_input.ligand_selection (max 120 chars).",
    )
    parser.add_argument(
        "--input-json",
        default=None,
        help="Optional JSON file merged into workflow_input for advanced fields.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)

    topology_path = Path(args.topology).expanduser().resolve()
    if not topology_path.is_file():
        sys.exit(f"Error: topology file not found: {topology_path}")

    ligand_paths: list[Path] = []
    for raw in args.ligand:
        p = Path(raw).expanduser().resolve()
        if not p.is_file():
            sys.exit(f"Error: ligand file not found: {p}")
        ligand_paths.append(p)

    simulation_name = (args.simulation_name or f"openmmdl_{topology_path.stem}").strip()
    if not simulation_name:
        sys.exit("Error: workflow_input.name must not be empty.")

    topology_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=topology_path,
        file_type="protein",
        item_name=f"openmmdl-topology-{topology_path.stem}",
    )
    ligand_refs = []
    for ligand_path in ligand_paths:
        ligand_refs.append(
            upload_library_file_and_get_ref(
                base_url,
                api_key=api_key,
                file_path=ligand_path,
                file_type="ligand",
                item_name=f"openmmdl-ligand-{ligand_path.stem}",
            )
        )

    workflow_input: dict[str, Any] = {
        "name": simulation_name,
        "files": {
            "topology": topology_ref,
            "ligands": ligand_refs,
        },
    }
    if args.run_analysis is not None:
        workflow_input["run_analysis"] = bool(args.run_analysis)
    if args.sim_length_ns is not None:
        workflow_input["sim_length_ns"] = float(args.sim_length_ns)
    if args.step_time_ps is not None:
        workflow_input["step_time_ps"] = float(args.step_time_ps)
    if args.analysis_cpus is not None:
        workflow_input["analysis_cpus"] = int(args.analysis_cpus)
    if args.failure_retries is not None:
        workflow_input["failure_retries"] = int(args.failure_retries)
    if args.ligand_selection is not None:
        workflow_input["ligand_selection"] = str(args.ligand_selection)
    if args.input_json:
        workflow_input = _deep_merge_dict(workflow_input, _load_json_file(args.input_json))

    prepared = http_json(
        base_url,
        "POST",
        "/v1/workflows/openmmdl/prepare-script",
        api_key=api_key,
        body={"workflow_input": workflow_input},
    )
    effective_workflow_input = _effective_workflow_input(prepared, workflow_input)

    result = {
        "workflow_input": effective_workflow_input,
        "prepared": prepared,
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("prepared_ok")
    print(str(prepared.get("system_name") or ""))
    print(str(prepared.get("folder_name") or ""))
    script = str(prepared.get("generated_script") or "")
    print(f"generated_script_chars: {len(script)}")


if __name__ == "__main__":
    main()
