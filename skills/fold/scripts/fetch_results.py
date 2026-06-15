#!/usr/bin/env python3
"""
Fetch FastFold job results (GET /v1/jobs/{jobId}/results) and print JSON or a short summary.

Usage:
    fetch_results.py JOB_ID [--base-url URL]
    fetch_results.py JOB_ID --json   # print full API JSON (untrusted content)

Requires: Python standard library only (no external dependencies)
Environment: FASTFOLD_API_KEY (optional for public jobs; required for private jobs)
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_job_id, validate_results_payload


def get_results(base_url: str, api_key: str | None, job_id: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/jobs/{job_id}/results"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
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
        if api_key:
            sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
        sys.exit("Error: Unauthorized. This job is likely private; set FASTFOLD_API_KEY.")
    if status == 404:
        sys.exit("Error: Job not found.")
    if status >= 400:
        sys.exit(f"Error: {status} - {response_text}")
    try:
        return validate_results_payload(json.loads(response_text))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON (status {status}).")


def summary(data: dict) -> str:
    def _prediction_lines(pp: dict, prefix: str = "") -> list[str]:
        lines_out: list[str] = []
        scalar_fields = [
            "cif_url",
            "pdb_url",
            "msa_coverage_plot_url",
            "pae_plot_url",
            "plddt_plot_url",
            "metrics_json_url",
            "config_json_url",
            "citations_bibtex_url",
            "plots_url",
            "meanPLLDT",
            "ptm_score",
            "iptm_score",
            "max_pae_score",
        ]
        for field in scalar_fields:
            value = pp.get(field)
            if value is None or value == "":
                continue
            lines_out.append(f"{prefix}{field}: {value}")

        affinity = pp.get("affinity_result_raw_json")
        if isinstance(affinity, dict) and affinity:
            keys = sorted(str(k) for k in affinity.keys())
            preview = ", ".join(keys[:12])
            if len(keys) > 12:
                preview = f"{preview}, ..."
            lines_out.append(f"{prefix}affinity_result_raw_json: present")
            lines_out.append(f"{prefix}affinity_result_raw_json_keys: {preview}")
        elif affinity not in (None, "", {}):
            lines_out.append(f"{prefix}affinity_result_raw_json: {affinity}")
        return lines_out

    job = data.get("job", {})
    status = job.get("status", "UNKNOWN")
    is_complex = job.get("isComplex", False)
    lines = [f"Status: {status}", f"Complex: {is_complex}"]
    constraints = data.get("constraints") or {}
    if isinstance(constraints, dict) and constraints:
        contact_n = len(constraints.get("contact") or [])
        pocket_n = len(constraints.get("pocket") or [])
        bond_n = len(constraints.get("bond") or [])
        lines.append(f"Constraints: contact={contact_n}, pocket={pocket_n}, bond={bond_n}")
    if status != "COMPLETED":
        return "\n".join(lines)
    sequences = data.get("sequences", [])
    pred = data.get("predictionPayload")
    if is_complex and pred:
        lines.extend(_prediction_lines(pred))
    else:
        for i, seq in enumerate(sequences):
            pp = (seq or {}).get("predictionPayload") or {}
            seq_lines = _prediction_lines(pp, prefix=f"[{i}] ")
            if seq_lines:
                lines.extend(seq_lines)
            else:
                lines.append(f"[{i}] predictionPayload: (none)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Fetch FastFold job results.")
    ap.add_argument("job_id", help="FastFold job ID (UUID)")
    ap.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    ap.add_argument("--json", action="store_true", help="Print full API JSON (untrusted content)")
    args = ap.parse_args()

    api_key = resolve_fastfold_api_key()

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    data = get_results(base_url, api_key, job_id)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(summary(data))


if __name__ == "__main__":
    main()
