#!/usr/bin/env python3
"""
Submit a calvados_openmm_v1 MD simulation from locally-provided PDB + PAE JSON.

This script:
  1. Creates two Library items (file type: protein, json).
  2. Uploads the PDB and PAE JSON files via /v1/library/<id>/upload-files.
  3. Reads the server-stored filenames from /v1/library/<id>.
  4. Submits POST /v1/workflows with preset `single_af_go` and manual file refs.
  5. Prints workflow_id to stdout (or full JSON with --json).

Environment: FASTFOLD_API_KEY (see load_env.py for resolution order).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _api import http_json, upload_library_file_and_get_ref
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url


def _charge_termini_from_flags(charged_n: bool, charged_c: bool) -> str:
    if charged_n and charged_c:
        return "both"
    if charged_n:
        return "N"
    if charged_c:
        return "C"
    return "none"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit an MD simulation (calvados_openmm_v1) with manual PDB + PAE upload.",
    )
    parser.add_argument("--pdb", required=True, help="Path to the PDB structure file.")
    parser.add_argument("--pae", required=True, help="Path to the PAE JSON file (AlphaFold EBI format).")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--name", default=None, help="Workflow display name.")
    parser.add_argument("--simulation-name", default=None, help="OpenMM simulation name (workflow_input.name).")
    parser.add_argument("--profile", default="calvados3", help="Residue profile (calvados2/calvados3/c2rna/...).")
    parser.add_argument("--temperature", type=float, default=293.15, help="Temperature in K.")
    parser.add_argument("--ionic", type=float, default=0.15, help="Ionic strength in M.")
    parser.add_argument("--ph", type=float, default=7.5, help="pH.")
    parser.add_argument("--step-size-ns", type=float, default=0.01, help="Step size in ns.")
    parser.add_argument("--sim-length-ns", type=float, default=0.2, help="Simulation length in ns.")
    parser.add_argument("--box-length", type=float, default=20, help="Box length in nm.")
    parser.add_argument(
        "--charged-n-terminal-amine",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable workflow_input.component_defaults.charged_N_terminal_amine.",
    )
    parser.add_argument(
        "--charged-c-terminal-carboxyl",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable workflow_input.component_defaults.charged_C_terminal_carboxyl.",
    )
    parser.add_argument(
        "--charged-histidine",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable workflow_input.component_defaults.charged_histidine.",
    )
    parser.add_argument("--public", action="store_true", help="Make the workflow readable via /v1/workflows/public/<id>.")
    parser.add_argument("--json", action="store_true", help="Print full submit response JSON instead of workflow_id.")
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    pdb_path = Path(args.pdb).expanduser().resolve()
    pae_path = Path(args.pae).expanduser().resolve()
    if not pdb_path.is_file():
        sys.exit(f"Error: PDB file not found: {pdb_path}")
    if not pae_path.is_file():
        sys.exit(f"Error: PAE JSON file not found: {pae_path}")

    simulation_name = (args.simulation_name or f"openmm_manual_{pdb_path.stem}").strip()

    pdb_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=pdb_path,
        file_type="protein",
        item_name=f"openmm-manual-pdb-{pdb_path.stem}",
    )
    pae_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=pae_path,
        file_type="json",
        item_name=f"openmm-manual-pae-{pae_path.stem}",
    )

    workflow_input: dict = {
        "preset": "single_af_go",
        "name": simulation_name,
        "force_field_family": "calvados",
        "residue_profile": args.profile,
        "temp": args.temperature,
        "ionic": args.ionic,
        "pH": args.ph,
        "step_size_ns": args.step_size_ns,
        "sim_length_ns": args.sim_length_ns,
        "box_length": args.box_length,
        "files": {
            "pdb": pdb_ref,
            "pae": pae_ref,
        },
    }
    component_defaults_payload: dict = {}
    if args.charged_n_terminal_amine is not None:
        component_defaults_payload["charged_N_terminal_amine"] = bool(args.charged_n_terminal_amine)
    if args.charged_c_terminal_carboxyl is not None:
        component_defaults_payload["charged_C_terminal_carboxyl"] = bool(args.charged_c_terminal_carboxyl)
    if args.charged_histidine is not None:
        component_defaults_payload["charged_histidine"] = bool(args.charged_histidine)
    if (
        args.charged_n_terminal_amine is not None
        or args.charged_c_terminal_carboxyl is not None
    ):
        charged_n = (
            bool(args.charged_n_terminal_amine)
            if args.charged_n_terminal_amine is not None
            else True
        )
        charged_c = (
            bool(args.charged_c_terminal_carboxyl)
            if args.charged_c_terminal_carboxyl is not None
            else True
        )
        component_defaults_payload["charge_termini"] = _charge_termini_from_flags(charged_n, charged_c)
    if component_defaults_payload:
        workflow_input["component_defaults"] = component_defaults_payload
    if args.public:
        workflow_input["isPublic"] = True

    display_name = (args.name or f"OpenMM manual {pdb_path.stem}").strip()
    body = {
        "workflow_name": "calvados_openmm_v1",
        "name": display_name,
        "workflow_input": workflow_input,
    }
    response_payload = http_json(base_url, "POST", "/v1/workflows", api_key=api_key, body=body)
    workflow_id = str(response_payload.get("workflow_id") or "").strip()
    if not workflow_id:
        sys.exit("Error: workflow submit response missing workflow_id.")

    share_url = (
        f"https://cloud.fastfold.ai/openmm/results/{workflow_id}?shared=true"
        if args.public
        else ""
    )

    if args.json:
        print(
            json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": response_payload.get("status"),
                    "workflow_type": response_payload.get("workflow_type"),
                    "isPublic": bool(args.public),
                    "share_url": share_url,
                    "files": {"pdb": pdb_ref, "pae": pae_ref},
                    "name": response_payload.get("name"),
                },
                indent=2,
            )
        )
    else:
        print(workflow_id)
        if share_url:
            print(f"[FastFold] Public share URL: {share_url}", file=sys.stderr)


if __name__ == "__main__":
    main()
