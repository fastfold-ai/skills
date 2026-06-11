#!/usr/bin/env python3
"""
Fetch FastFold job results (GET /v1/jobs/{jobId}/results) and print JSON or a short summary.

Usage:
    fetch_results.py JOB_ID [--base-url URL]
    fetch_results.py JOB_ID --json   # print full API JSON (untrusted content)

Requires: Python standard library only (no external dependencies)
Environment: FASTFOLD_API_KEY
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_job_id, validate_results_payload


def get_results(base_url: str, api_key: str, job_id: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/jobs/{job_id}/results"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        status = e.code
        response_text = e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Error: Network error while fetching results: {e.reason}")

    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    if status == 404:
        sys.exit("Error: Job not found.")
    if status >= 400:
        sys.exit(f"Error: {status} - {response_text}")
    try:
        return validate_results_payload(json.loads(response_text))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON (status {status}).")


def summary(data: dict) -> str:
    job = data.get("job", {})
    status = job.get("status", "UNKNOWN")
    is_complex = job.get("isComplex", False)
    lines = [f"Status: {status}", f"Complex: {is_complex}"]
    job_run_id = (
        data.get("jobRunId")
        or (data.get("parameters") or {}).get("jobRunId")
        or next((s.get("jobRunId") for s in (data.get("sequences") or []) if isinstance(s, dict) and s.get("jobRunId")), "")
    )
    if job_run_id:
        lines.append(f"jobRunId: {job_run_id}")
    sequence_ids = []
    for row in (data.get("sequences") or []):
        if not isinstance(row, dict):
            continue
        sequence_id = str(row.get("id") or row.get("sequenceId") or row.get("sequence_id") or "").strip()
        if sequence_id:
            sequence_ids.append(sequence_id)
    if sequence_ids:
        lines.append(f"sequenceIds: {', '.join(sequence_ids)}")
    constraints = data.get("constraints") or {}
    if isinstance(constraints, dict) and constraints:
        contact_n = len(constraints.get("contact") or [])
        pocket_n = len(constraints.get("pocket") or [])
        bond_n = len(constraints.get("bond") or [])
        lines.append(f"Constraints: contact={contact_n}, pocket={pocket_n}, bond={bond_n}")
    if status != "COMPLETED":
        return "\n".join(lines)
    params = data.get("parameters", {})
    sequences = data.get("sequences", [])
    pred = data.get("predictionPayload")
    if is_complex and pred:
        lines.append(f"cif_url: {pred.get('cif_url') or '(none)'}")
        lines.append(f"meanPLLDT: {pred.get('meanPLLDT')}")
        lines.append(f"ptm_score: {pred.get('ptm_score')}")
        lines.append(f"iptm_score: {pred.get('iptm_score')}")
    else:
        for i, seq in enumerate(sequences):
            pp = (seq or {}).get("predictionPayload") or {}
            lines.append(f"[{i}] cif_url: {pp.get('cif_url') or '(none)'}")
            lines.append(f"[{i}] meanPLLDT: {pp.get('meanPLLDT')}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Fetch FastFold job results.")
    ap.add_argument("job_id", help="FastFold job ID (UUID)")
    ap.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    ap.add_argument("--json", action="store_true", help="Print full API JSON (untrusted content)")
    args = ap.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Run `fastfold setup` or set `api.fastfold_cloud_key` in FastFold CLI config."
        )

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    data = get_results(base_url, api_key, job_id)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(summary(data))


if __name__ == "__main__":
    main()
