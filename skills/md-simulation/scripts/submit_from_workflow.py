#!/usr/bin/env python3
"""
Submit a new OpenMM workflow from an existing workflow's stored inputs/settings.

This is the preferred path when the user points at an /openmm/results/<id> page
and asks to run another simulation with the same input files and parameters.
The script fetches the source workflow, copies its input_payload explicitly, and
submits a new POST /v1/workflows request. Optional CLI flags can override common
simulation parameters while keeping the same input files.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _api import http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id


def _clone_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        sys.exit("Error: source workflow is missing input_payload.")
    return json.loads(json.dumps(value))


def _set_if_provided(payload: dict, key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a new calvados_openmm_v1 workflow from an existing workflow's inputs/settings.",
    )
    parser.add_argument("workflow_id", help="Existing OpenMM workflow ID to use as the reference.")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--name", default=None, help="New workflow display name.")
    parser.add_argument("--simulation-name", default=None, help="OpenMM simulation name (workflow_input.name).")
    parser.add_argument(
        "--component-name",
        default=None,
        help="OpenMM component selector (workflow_input.component_name). Must match sequence label/FASTA ID.",
    )
    parser.add_argument("--preset", default=None, help="OpenMM preset override.")
    parser.add_argument("--force-field-family", default=None, help="Force field family override.")
    parser.add_argument("--profile", default=None, help="Residue profile override.")
    parser.add_argument("--temperature", type=float, default=None, help="Temperature override in K.")
    parser.add_argument("--ionic", type=float, default=None, help="Ionic strength override in M.")
    parser.add_argument("--ph", type=float, default=None, help="pH override.")
    parser.add_argument("--step-size-ns", type=float, default=None, help="Frame interval / step size override in ns.")
    parser.add_argument("--sim-length-ns", type=float, default=None, help="Simulation length override in ns.")
    parser.add_argument("--box-length", type=float, default=None, help="Cubic box length override in nm.")
    parser.add_argument("--topology", default=None, help="Topology placement mode override, e.g. center/random/grid/slab.")
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
    public_group = parser.add_mutually_exclusive_group()
    public_group.add_argument("--public", action="store_true", help="Make the new workflow public.")
    public_group.add_argument("--private", action="store_true", help="Make the new workflow private.")
    parser.add_argument("--json", action="store_true", help="Print full submit response JSON instead of workflow_id.")
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    source_workflow_id = validate_workflow_id(args.workflow_id)
    try:
        source = http_json(
            base_url,
            "GET",
            f"/v1/workflows/{source_workflow_id}",
            api_key=api_key,
        )
    except SystemExit as exc:
        detail = str(exc) if exc.code else ""
        sys.exit(
            "Error: could not fetch the reference OpenMM workflow. "
            "You may not have access to that workflow, or it may no longer exist. "
            "Ask the workflow owner to share the workflow/files with you, or provide the input PDB + PAE files directly. "
            "If you only know the UniProt accession, use fetch_uniprot.py and then submit_manual_af_pae.py. "
            "If the source is a FastFold fold job, use submit_from_fold_job.py instead."
            + (f"\nDetails: {detail}" if detail else "")
        )
    workflow_input = _clone_dict(source.get("input_payload"))

    _set_if_provided(workflow_input, "name", args.simulation_name)
    _set_if_provided(workflow_input, "component_name", args.component_name)
    _set_if_provided(workflow_input, "preset", args.preset)
    _set_if_provided(workflow_input, "force_field_family", args.force_field_family)
    _set_if_provided(workflow_input, "residue_profile", args.profile)
    _set_if_provided(workflow_input, "temp", args.temperature)
    _set_if_provided(workflow_input, "ionic", args.ionic)
    _set_if_provided(workflow_input, "pH", args.ph)
    _set_if_provided(workflow_input, "step_size_ns", args.step_size_ns)
    _set_if_provided(workflow_input, "sim_length_ns", args.sim_length_ns)
    _set_if_provided(workflow_input, "topol", args.topology)

    config_payload = workflow_input.get("config")
    if not isinstance(config_payload, dict):
        config_payload = {}
    if args.box_eq is not None:
        config_payload["box_eq"] = bool(args.box_eq)
    if args.pressure is not None:
        config_payload["pressure"] = args.pressure
    if config_payload:
        workflow_input["config"] = config_payload

    component_defaults_payload = workflow_input.get("component_defaults")
    if not isinstance(component_defaults_payload, dict):
        component_defaults_payload = workflow_input.get("componentDefaults")
    if not isinstance(component_defaults_payload, dict):
        component_defaults_payload = {}
    if args.periodic is not None:
        component_defaults_payload["periodic"] = bool(args.periodic)
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
    workflow_input.pop("componentDefaults", None)

    if args.box_length is not None:
        workflow_input["box_length"] = args.box_length
        workflow_input["box"] = [args.box_length, args.box_length, args.box_length]
        workflow_input["box_mode"] = "cube"
    if args.public:
        workflow_input["isPublic"] = True
    elif args.private:
        workflow_input["isPublic"] = False

    display_name = (
        args.name
        or f"{str(source.get('name') or 'OpenMM workflow').strip()} copy"
    ).strip()
    body = {
        "workflow_name": str(source.get("workflow_type") or "calvados_openmm_v1"),
        "name": display_name,
        "workflow_input": workflow_input,
    }
    response_payload = http_json(base_url, "POST", "/v1/workflows", api_key=api_key, body=body)
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
                    "source_workflow_id": source_workflow_id,
                    "name": response_payload.get("name"),
                    "workflow_input": workflow_input,
                },
                indent=2,
            )
        )
    else:
        print(workflow_id)


if __name__ == "__main__":
    main()
