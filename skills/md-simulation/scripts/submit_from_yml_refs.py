#!/usr/bin/env python3
"""
Advanced Lane 2 submit path for MD simulations:

Upload custom config.yaml + components.yaml and all required input files to
Library, then submit a runnable OpenMM workflow with explicit file refs.

This script is intentionally "advanced only". It preserves uploaded YML refs in
workflow_input.yml_reference for traceability/future migration while still
submitting with the currently-supported OpenMM fields.
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


def _parse_pressure(raw: str) -> list[float]:
    parts = [part.strip() for part in str(raw).split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("pressure must be 3 comma-separated numbers, e.g. 0.1,0,0")
    out: list[float] = []
    for idx, part in enumerate(parts):
        try:
            out.append(float(part))
        except Exception as exc:
            raise argparse.ArgumentTypeError(f"pressure[{idx}] is not a number: '{part}'") from exc
    return out


def _charge_termini_from_flags(charged_n: bool, charged_c: bool) -> str:
    if charged_n and charged_c:
        return "both"
    if charged_n:
        return "N"
    if charged_c:
        return "C"
    return "none"


def _validate_file(path_str: str, *, label: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        sys.exit(f"Error: {label} file not found: {path}")
    return path


def _parse_json_object(raw: str, *, field_name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError(f"{field_name} must be a JSON object.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Advanced only: submit OpenMM from custom YML references + uploaded input files. "
            "Stores YML refs under workflow_input.yml_reference."
        ),
    )
    parser.add_argument("--config-yaml", required=True, help="Path to config.yaml.")
    parser.add_argument("--components-yaml", required=True, help="Path to components.yaml.")
    parser.add_argument("--residues-csv", required=True, help="Path to residues.csv.")
    parser.add_argument("--fasta", default=None, help="Path to FASTA (sequence-only mode).")
    parser.add_argument("--pdb", default=None, help="Path to PDB (AF/structure mode).")
    parser.add_argument("--pae", default=None, help="Path to PAE JSON (AF/structure mode).")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--name", default=None, help="Workflow display name.")
    parser.add_argument("--simulation-name", default=None, help="OpenMM simulation name (workflow_input.name).")
    parser.add_argument(
        "--component-name",
        default=None,
        help="OpenMM component selector (workflow_input.component_name).",
    )
    parser.add_argument(
        "--profile",
        "--force-field",
        dest="profile",
        default="calvados3",
        help="Force field (workflow_input.residue_profile), e.g. calvados2/calvados3/c2rna/...",
    )
    parser.add_argument("--temperature", type=float, default=293.15, help="Temperature in K.")
    parser.add_argument("--ionic", type=float, default=0.15, help="Ionic strength in M.")
    parser.add_argument("--ph", type=float, default=7.5, help="pH.")
    parser.add_argument("--step-size-ns", type=float, default=0.01, help="Step size in ns.")
    parser.add_argument("--sim-length-ns", type=float, default=0.2, help="Simulation length in ns.")
    parser.add_argument("--box-length", type=float, default=20, help="Box length in nm.")
    parser.add_argument("--topology", default="center", help="Topology mode (center/random/grid/slab).")
    parser.add_argument(
        "--ext-force-expr",
        default=None,
        help="External force expression; when set, enables workflow_input.ext_force and sets ext_force_expr.",
    )
    parser.add_argument(
        "--box-eq",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable workflow_input.config.box_eq.",
    )
    parser.add_argument(
        "--pressure",
        type=_parse_pressure,
        default=None,
        metavar="X,Y,Z",
        help="Override workflow_input.config.pressure (3-vector), e.g. 0.1,0,0.",
    )
    parser.add_argument(
        "--periodic",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable workflow_input.component_defaults.periodic.",
    )
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
    parser.add_argument(
        "--nmol",
        type=int,
        default=None,
        help="Optional workflow_input.component_defaults.nmol override.",
    )
    parser.add_argument(
        "--molecule-type",
        default=None,
        help="Optional workflow_input.component_defaults.molecule_type override (e.g., protein/rna).",
    )
    parser.add_argument(
        "--component-defaults-json",
        type=lambda raw: _parse_json_object(raw, field_name="--component-defaults-json"),
        default=None,
        help='JSON object merged into workflow_input.component_defaults, e.g. \'{"rna_kb1":1400}\'',
    )
    parser.add_argument("--public", action="store_true", help="Make the workflow public.")
    parser.add_argument("--dry-run", action="store_true", help="Print submit body and exit without API calls.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    args = parser.parse_args()

    config_yaml_path = _validate_file(args.config_yaml, label="config.yaml")
    components_yaml_path = _validate_file(args.components_yaml, label="components.yaml")
    residues_csv_path = _validate_file(args.residues_csv, label="residues.csv")

    has_fasta = bool(args.fasta)
    has_pdb = bool(args.pdb)
    has_pae = bool(args.pae)
    if has_fasta and (has_pdb or has_pae):
        sys.exit("Error: provide either --fasta OR --pdb/--pae, not both.")
    if not has_fasta and not (has_pdb and has_pae):
        sys.exit("Error: provide --fasta (sequence mode) or both --pdb and --pae (AF/structure mode).")
    if has_fasta:
        fasta_path = _validate_file(str(args.fasta), label="fasta")
        pdb_path = None
        pae_path = None
    else:
        fasta_path = None
        pdb_path = _validate_file(str(args.pdb), label="pdb")
        pae_path = _validate_file(str(args.pae), label="pae")

    simulation_name = (args.simulation_name or f"openmm_yml_ref_{config_yaml_path.stem}").strip()
    display_name = (args.name or f"OpenMM from YML refs {simulation_name}").strip()
    preset = "single_idr_fasta" if fasta_path else "single_af_go"

    # Dry-run can still be useful for reviewing payload shape.
    if args.dry_run:
        dry_body = {
            "workflow_name": "calvados_openmm_v1",
            "name": display_name,
            "workflow_input": {
                "preset": preset,
                "name": simulation_name,
                "component_name": args.component_name,
                "force_field_family": "calvados",
                "residue_profile": args.profile,
                "temp": args.temperature,
                "ionic": args.ionic,
                "pH": args.ph,
                "step_size_ns": args.step_size_ns,
                "sim_length_ns": args.sim_length_ns,
                "box_length": args.box_length,
                "topol": args.topology,
                "ext_force": bool(args.ext_force_expr),
                "ext_force_expr": str(args.ext_force_expr or ""),
                "files": {
                    "residues": "<library-ref>",
                    "fasta" if fasta_path else "pdb": "<library-ref>",
                    None if fasta_path else "pae": "<library-ref>",
                },
                "yml_reference": {
                    "mode": "lane2_custom_upload_v1",
                    "config": "<library-ref>",
                    "components": "<library-ref>",
                    "file_bindings": "<library-refs>",
                },
            },
        }
        # Remove placeholder None-key produced by conditional dict key above.
        dry_files = dry_body["workflow_input"]["files"]
        if None in dry_files:
            dry_files.pop(None)
        print(json.dumps(dry_body, indent=2))
        return

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )
    base_url = validate_base_url(args.base_url)

    config_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=config_yaml_path,
        file_type="yml",
        item_name=f"openmm-yml-config-{config_yaml_path.stem}",
    )
    components_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=components_yaml_path,
        file_type="yml",
        item_name=f"openmm-yml-components-{components_yaml_path.stem}",
    )
    residues_ref = upload_library_file_and_get_ref(
        base_url,
        api_key=api_key,
        file_path=residues_csv_path,
        file_type="csv",
        item_name=f"openmm-yml-residues-{residues_csv_path.stem}",
    )

    files_payload: dict = {"residues": residues_ref}
    file_bindings_payload: dict = {"residues": residues_ref}
    if fasta_path:
        fasta_ref = upload_library_file_and_get_ref(
            base_url,
            api_key=api_key,
            file_path=fasta_path,
            file_type="protein",
            item_name=f"openmm-yml-fasta-{fasta_path.stem}",
        )
        files_payload["fasta"] = fasta_ref
        file_bindings_payload["fasta"] = fasta_ref
    else:
        pdb_ref = upload_library_file_and_get_ref(
            base_url,
            api_key=api_key,
            file_path=pdb_path,
            file_type="protein",
            item_name=f"openmm-yml-pdb-{pdb_path.stem}",
        )
        pae_ref = upload_library_file_and_get_ref(
            base_url,
            api_key=api_key,
            file_path=pae_path,
            file_type="json",
            item_name=f"openmm-yml-pae-{pae_path.stem}",
        )
        files_payload["pdb"] = pdb_ref
        files_payload["pae"] = pae_ref
        file_bindings_payload["pdb"] = pdb_ref
        file_bindings_payload["pae"] = pae_ref

    workflow_input: dict = {
        "preset": preset,
        "name": simulation_name,
        "force_field_family": "calvados",
        "residue_profile": args.profile,
        "temp": args.temperature,
        "ionic": args.ionic,
        "pH": args.ph,
        "step_size_ns": args.step_size_ns,
        "sim_length_ns": args.sim_length_ns,
        "box_length": args.box_length,
        "topol": args.topology,
        "files": files_payload,
        # Advanced lane2 metadata for traceability/future YML-native mode.
        "yml_reference": {
            "mode": "lane2_custom_upload_v1",
            "config": config_ref,
            "components": components_ref,
            "file_bindings": file_bindings_payload,
        },
    }
    if args.ext_force_expr:
        workflow_input["ext_force"] = True
        workflow_input["ext_force_expr"] = str(args.ext_force_expr).strip()
    if args.component_name:
        workflow_input["component_name"] = str(args.component_name).strip()
    if args.public:
        workflow_input["isPublic"] = True

    config_payload: dict = {"box": [args.box_length, args.box_length, args.box_length], "topol": args.topology}
    if args.box_eq is not None:
        config_payload["box_eq"] = bool(args.box_eq)
    if args.pressure is not None:
        config_payload["pressure"] = args.pressure
    workflow_input["config"] = config_payload

    component_defaults_payload: dict = {}
    if args.periodic is not None:
        component_defaults_payload["periodic"] = bool(args.periodic)
    if args.charged_n_terminal_amine is not None:
        component_defaults_payload["charged_N_terminal_amine"] = bool(args.charged_n_terminal_amine)
    if args.charged_c_terminal_carboxyl is not None:
        component_defaults_payload["charged_C_terminal_carboxyl"] = bool(args.charged_c_terminal_carboxyl)
    if args.charged_histidine is not None:
        component_defaults_payload["charged_histidine"] = bool(args.charged_histidine)
    if args.nmol is not None:
        if args.nmol <= 0:
            sys.exit("Error: --nmol must be a positive integer.")
        component_defaults_payload["nmol"] = int(args.nmol)
    if args.molecule_type:
        component_defaults_payload["molecule_type"] = str(args.molecule_type).strip()
    if args.charged_n_terminal_amine is not None or args.charged_c_terminal_carboxyl is not None:
        charged_n = bool(args.charged_n_terminal_amine) if args.charged_n_terminal_amine is not None else True
        charged_c = bool(args.charged_c_terminal_carboxyl) if args.charged_c_terminal_carboxyl is not None else True
        component_defaults_payload["charge_termini"] = _charge_termini_from_flags(charged_n, charged_c)
    if args.component_defaults_json:
        component_defaults_payload.update(args.component_defaults_json)
    if component_defaults_payload:
        workflow_input["component_defaults"] = component_defaults_payload

    submit_body = {
        "workflow_name": "calvados_openmm_v1",
        "name": display_name,
        "workflow_input": workflow_input,
    }
    response_payload = http_json(base_url, "POST", "/v1/workflows", api_key=api_key, body=submit_body)
    workflow_id = str(response_payload.get("workflow_id") or "").strip()
    if not workflow_id:
        sys.exit("Error: workflow submit response missing workflow_id.")

    if args.json:
        print(
            json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": response_payload.get("status"),
                    "workflow_type": response_payload.get("workflow_type"),
                    "name": response_payload.get("name"),
                    "preset": preset,
                    "files": files_payload,
                    "yml_reference": workflow_input["yml_reference"],
                },
                indent=2,
            )
        )
    else:
        print(workflow_id)
        print(
            "[FastFold] Advanced lane2 submit: workflow executes from explicit params/files; "
            "YML refs were attached under workflow_input.yml_reference.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
