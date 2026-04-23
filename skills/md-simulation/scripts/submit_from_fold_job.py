#!/usr/bin/env python3
"""
Submit a calvados_openmm_v1 MD simulation starting from an existing FastFold fold job.

This script:
  1. Fetches /v1/jobs/<job_id>/results.
  2. Extracts jobRunId and the protein sequenceId.
  3. Submits POST /v1/workflows with preset `single_af_go` and sourceType=fold_job.
  4. Prints workflow_id to stdout (or full JSON with --json).

Status/metrics are intentionally separate: use `wait_for_workflow.py` to
wait for terminal state and metrics/plot propagation.

Environment: FASTFOLD_API_KEY (see load_env.py for resolution order).
"""

from __future__ import annotations

import argparse
import json
import sys

from _api import extract_fold_job_ids, http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_job_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit an MD simulation (calvados_openmm_v1) from an existing FastFold fold job.",
    )
    parser.add_argument("job_id", help="FastFold fold job ID (UUID).")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--name", default=None, help="Workflow display name.")
    parser.add_argument("--simulation-name", default=None, help="OpenMM simulation name (workflow_input.name).")
    parser.add_argument("--preset", default="single_af_go", choices=["single_af_go"],
                        help="OpenMM input preset. Only single_af_go is supported for fold-job mode.")
    parser.add_argument("--profile", default="calvados3", help="Residue profile (calvados2/calvados3/c2rna/...).")
    parser.add_argument("--temperature", type=float, default=293.15, help="Temperature in K.")
    parser.add_argument("--ionic", type=float, default=0.15, help="Ionic strength in M.")
    parser.add_argument("--ph", type=float, default=7.5, help="pH.")
    parser.add_argument("--step-size-ns", type=float, default=0.01, help="Step size in ns.")
    parser.add_argument("--sim-length-ns", type=float, default=0.2, help="Simulation length in ns.")
    parser.add_argument("--box-length", type=float, default=20, help="Box length in nm.")
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
    job_id = validate_job_id(args.job_id)

    job_results = http_json(base_url, "GET", f"/v1/jobs/{job_id}/results", api_key=api_key)
    job_run_id, sequence_id = extract_fold_job_ids(job_results)
    if not job_run_id or not sequence_id:
        sys.exit("Error: could not resolve jobRunId / protein sequenceId from fold results.")
    job_run_id = validate_job_id(job_run_id)
    sequence_id = validate_job_id(sequence_id)

    simulation_name = (args.simulation_name or f"openmm_{job_id[:8]}").strip()
    workflow_input: dict = {
        "preset": args.preset,
        "name": simulation_name,
        "force_field_family": "calvados",
        "residue_profile": args.profile,
        "temp": args.temperature,
        "ionic": args.ionic,
        "pH": args.ph,
        "step_size_ns": args.step_size_ns,
        "sim_length_ns": args.sim_length_ns,
        "box_length": args.box_length,
        "files": {},
        "sourceType": "fold_job",
        "sourceJobId": job_id,
        "sourceJobRunId": job_run_id,
        "sourceSequenceId": sequence_id,
    }
    if args.public:
        workflow_input["isPublic"] = True

    display_name = (args.name or f"OpenMM via fold {job_id[:8]}").strip()
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
                    "source": {
                        "job_id": job_id,
                        "job_run_id": job_run_id,
                        "sequence_id": sequence_id,
                    },
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
