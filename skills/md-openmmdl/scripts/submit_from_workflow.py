#!/usr/bin/env python3
"""
Submit a new OpenMMDL workflow from an existing workflow's stored inputs/settings.

This script fetches /v1/workflows/<id>, clones input_payload, applies optional
overrides, then submits POST /v1/workflows with workflow_name=openmmdl_v1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _api import http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id


def _clone_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        sys.exit("Error: source workflow is missing input_payload.")
    return json.loads(json.dumps(value))


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


def _set_if_provided(payload: dict, key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _effective_workflow_input(prepared_payload: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(prepared_payload, dict):
        prepared_input = prepared_payload.get("workflow_input")
        if isinstance(prepared_input, dict):
            return prepared_input
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a new openmmdl_v1 workflow from an existing workflow.",
    )
    parser.add_argument("workflow_id", help="Existing OpenMMDL workflow ID to use as source.")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--name", default=None, help="New workflow display name.")
    parser.add_argument("--simulation-name", default=None, help="Override workflow_input.name.")
    parser.add_argument(
        "--run-analysis",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override workflow_input.run_analysis.",
    )
    parser.add_argument("--sim-length-ns", type=float, default=None, help="Override workflow_input.sim_length_ns.")
    parser.add_argument("--step-time-ps", type=float, default=None, help="Override workflow_input.step_time_ps.")
    parser.add_argument("--analysis-cpus", type=int, default=None, help="Override workflow_input.analysis_cpus.")
    parser.add_argument("--failure-retries", type=int, default=None, help="Override workflow_input.failure_retries.")
    parser.add_argument("--ligand-selection", default=None, help="Override workflow_input.ligand_selection.")
    parser.add_argument(
        "--input-json",
        default=None,
        help="Optional JSON file merged into workflow_input for advanced fields.",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Run /v1/workflows/openmmdl/prepare-script before submit.",
    )
    parser.add_argument(
        "--draft-script",
        action="store_true",
        help="Create workflow in DRAFT mode (create_mode=draft_script).",
    )
    public_group = parser.add_mutually_exclusive_group()
    public_group.add_argument("--public", action="store_true", help="Set workflow_input.isPublic=true.")
    public_group.add_argument("--private", action="store_true", help="Set workflow_input.isPublic=false.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
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
        source = http_json(base_url, "GET", f"/v1/workflows/{source_workflow_id}", api_key=api_key)
    except SystemExit as exc:
        detail = str(exc) if exc.code else ""
        sys.exit(
            "Error: could not fetch the reference OpenMMDL workflow. "
            "You may not have access to that workflow, or it may no longer exist."
            + (f"\nDetails: {detail}" if detail else "")
        )

    source_type = str(source.get("workflow_type") or "").strip().lower()
    if source_type and source_type != "openmmdl_v1":
        sys.exit(f"Error: source workflow type is {source_type!r}, expected 'openmmdl_v1'.")

    workflow_input = _clone_dict(source.get("input_payload"))
    _set_if_provided(workflow_input, "name", args.simulation_name)
    _set_if_provided(workflow_input, "run_analysis", args.run_analysis)
    _set_if_provided(workflow_input, "sim_length_ns", args.sim_length_ns)
    _set_if_provided(workflow_input, "step_time_ps", args.step_time_ps)
    _set_if_provided(workflow_input, "analysis_cpus", args.analysis_cpus)
    _set_if_provided(workflow_input, "failure_retries", args.failure_retries)
    _set_if_provided(workflow_input, "ligand_selection", args.ligand_selection)
    if args.public:
        workflow_input["isPublic"] = True
    elif args.private:
        workflow_input["isPublic"] = False
    if args.input_json:
        workflow_input = _deep_merge_dict(workflow_input, _load_json_file(args.input_json))

    prepare_payload: dict[str, Any] | None = None
    if args.prepare:
        prepare_payload = http_json(
            base_url,
            "POST",
            "/v1/workflows/openmmdl/prepare-script",
            api_key=api_key,
            body={"workflow_input": workflow_input},
        )
        workflow_input = _effective_workflow_input(prepare_payload, workflow_input)
        if not isinstance(prepare_payload.get("workflow_input"), dict):
            for key in (
                "system_name",
                "folder_name",
                "topology_file",
                "ligand_files",
                "processed_topology_file",
                "processed_topology_b64",
                "missing_residue_spans",
                "missing_heavy_atoms",
            ):
                if key in prepare_payload:
                    workflow_input[key] = prepare_payload[key]

    if args.draft_script:
        workflow_input["create_mode"] = "draft_script"

    display_name = (
        args.name
        or f"{str(source.get('name') or 'OpenMMDL workflow').strip()} copy"
    ).strip()

    body: dict[str, Any] = {
        "workflow_name": "openmmdl_v1",
        "name": display_name,
        "workflow_input": workflow_input,
    }
    if args.draft_script:
        body["create_mode"] = "draft_script"

    submit_payload = http_json(base_url, "POST", "/v1/workflows", api_key=api_key, body=body)
    workflow_id = str(submit_payload.get("workflow_id") or "").strip()
    if not workflow_id:
        sys.exit("Error: workflow submit response missing workflow_id.")
    submitted_workflow_input = (
        submit_payload.get("input_payload")
        if isinstance(submit_payload.get("input_payload"), dict)
        else workflow_input
    )

    share_url = (
        f"https://cloud.fastfold.ai/openmmdl/results/{workflow_id}?shared=true"
        if bool(submitted_workflow_input.get("isPublic"))
        else ""
    )
    dashboard_url = f"https://cloud.fastfold.ai/openmmdl/results/{workflow_id}"

    if args.json:
        print(
            json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": submit_payload.get("status"),
                    "workflow_type": submit_payload.get("workflow_type"),
                    "name": submit_payload.get("name"),
                    "source_workflow_id": source_workflow_id,
                    "create_mode": "draft_script" if args.draft_script else "run_now",
                    "dashboard_url": dashboard_url,
                    "share_url": share_url,
                    "prepare": prepare_payload,
                    "submitted_workflow_input": submitted_workflow_input,
                },
                indent=2,
            )
        )
        return

    print(workflow_id)
    print(f"[FastFold] dashboard: {dashboard_url}", file=sys.stderr)
    if share_url:
        print(f"[FastFold] public share URL: {share_url}", file=sys.stderr)
    if args.draft_script:
        print("[FastFold] workflow created in DRAFT mode.", file=sys.stderr)


if __name__ == "__main__":
    main()
