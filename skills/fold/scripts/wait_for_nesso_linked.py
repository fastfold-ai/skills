#!/usr/bin/env python3
"""
Wait for a fold job, then wait for linked Nesso-1 affinity webhook results.

Use when the fold job was submitted with:
  constraints.webhooks.nesso.enabled = true
  (event on_start; protein_chain_id + ligand_chain_id required)

Nesso launches a child affinity job when the parent fold starts. Affinity merges
back onto the parent as:
  constraints.webhooks.nesso.status
  constraints.webhooks.nesso.affinity_result_raw_json
and may also appear on sequence predictionPayload.affinity_result_raw_json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_job_id, validate_results_payload


FOLD_TERMINAL_OK = {"COMPLETED"}
FOLD_TERMINAL_ERR = {"FAILED", "STOPPED"}
NESSO_TERMINAL_OK = {"completed", "succeeded", "success"}
NESSO_TERMINAL_ERR = {"failed", "error"}


def _get_json(url: str, api_key: str, *, timeout: float = 30.0) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Error: Network error while requesting {url}: {e.reason}")

    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    if status >= 400:
        sys.exit(f"Error: {status} from {url} - {body}")

    try:
        return validate_results_payload(json.loads(body))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON from {url} (status {status}).")


def get_fold_results(base_url: str, api_key: str, job_id: str) -> dict:
    return _get_json(f"{base_url.rstrip('/')}/v1/jobs/{job_id}/results", api_key=api_key)


def _job_status(results: dict) -> str:
    job = results.get("job") if isinstance(results.get("job"), dict) else {}
    raw = results.get("jobStatus") or job.get("status") or job.get("jobStatus") or ""
    return str(raw or "").strip().upper()


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def extract_nesso_webhook_state(results: dict) -> dict:
    """Return constraints.webhooks.nesso blob (may be empty)."""
    constraints = _as_dict(results.get("constraints"))
    if not constraints:
        job = _as_dict(results.get("job"))
        constraints = _as_dict(job.get("constraints"))
    webhooks = _as_dict(constraints.get("webhooks"))
    return _as_dict(webhooks.get("nesso"))


def extract_affinity_payload(results: dict, nesso: dict) -> dict | None:
    affinity = nesso.get("affinity_result_raw_json")
    if isinstance(affinity, dict) and affinity:
        return affinity

    top = _as_dict(results.get("predictionPayload"))
    affinity = top.get("affinity_result_raw_json")
    if isinstance(affinity, dict) and affinity:
        return affinity

    sequences = results.get("sequences")
    if isinstance(sequences, list):
        for row in sequences:
            if not isinstance(row, dict):
                continue
            pp = _as_dict(row.get("predictionPayload"))
            affinity = pp.get("affinity_result_raw_json")
            if isinstance(affinity, dict) and affinity:
                source = str(affinity.get("affinity_source") or "").strip().lower()
                if source == "nesso" or affinity.get("affinity_pred_value") is not None:
                    return affinity
    return None


def _sleep_with_backoff(base: float, same_count: int, *, max_interval: float = 20.0) -> None:
    delay = min(max_interval, float(base) * (1.0 + 0.25 * max(0, same_count - 1)))
    time.sleep(delay)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Wait for fold completion and linked Nesso-1 affinity webhook results."
    )
    ap.add_argument("job_id", help="Parent fold job UUID")
    ap.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    ap.add_argument("--poll-interval", type=float, default=5.0, help="Fold poll interval seconds")
    ap.add_argument("--timeout", type=float, default=900.0, help="Fold wait timeout seconds")
    ap.add_argument(
        "--nesso-poll-interval",
        type=float,
        default=5.0,
        help="Nesso affinity poll interval seconds",
    )
    ap.add_argument(
        "--nesso-timeout",
        type=float,
        default=900.0,
        help="Nesso affinity wait timeout seconds after fold completes (or while pending)",
    )
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout")
    args = ap.parse_args()

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set Integrations → Fastfold AI Cloud or export FASTFOLD_API_KEY."
        )

    fold_start = time.time()
    last_status = ""
    same_status_count = 0
    results: dict = {}

    while True:
        results = get_fold_results(base_url, api_key, job_id)
        status = _job_status(results)
        if status != last_status:
            print(f"[FastFold] Fold status: {status or 'UNKNOWN'}", file=sys.stderr)
            last_status = status
            same_status_count = 0
        else:
            same_status_count += 1

        if status in FOLD_TERMINAL_OK:
            break
        if status in FOLD_TERMINAL_ERR:
            sys.exit(f"Error: Fold job ended with status {status}")
        if (time.time() - fold_start) > args.timeout:
            sys.exit(f"Error: Timed out waiting for fold job {job_id} after {args.timeout:.0f}s")
        _sleep_with_backoff(args.poll_interval, same_status_count)

    nesso_start = time.time()
    last_nesso = ""
    same_nesso_count = 0
    nesso: dict = {}
    affinity: dict | None = None

    while True:
        results = get_fold_results(base_url, api_key, job_id)
        nesso = extract_nesso_webhook_state(results)
        nesso_status = str(nesso.get("status") or "").strip().lower()
        affinity = extract_affinity_payload(results, nesso)

        if nesso_status != last_nesso:
            print(
                f"[FastFold] Nesso webhook status: {nesso_status or ('present' if nesso else 'missing')}",
                file=sys.stderr,
            )
            last_nesso = nesso_status
            same_nesso_count = 0
        else:
            same_nesso_count += 1

        if nesso_status in NESSO_TERMINAL_OK or (affinity and not nesso_status):
            break
        if nesso_status in NESSO_TERMINAL_ERR:
            err = str(nesso.get("error") or nesso.get("message") or nesso_status)
            sys.exit(f"Error: Nesso webhook failed ({err})")

        if not nesso and (time.time() - nesso_start) > min(60.0, args.nesso_timeout):
            # Give the on_start subscription a short window to appear, then fail clearly.
            if (time.time() - nesso_start) > args.nesso_timeout:
                sys.exit(
                    "Error: No constraints.webhooks.nesso state on fold results. "
                    "Verify constraints.webhooks.nesso.enabled was set with protein_chain_id "
                    "and ligand_chain_id (event on_start)."
                )

        if (time.time() - nesso_start) > args.nesso_timeout:
            sys.exit(
                f"Error: Timed out waiting for Nesso affinity after {args.nesso_timeout:.0f}s "
                f"(last status={nesso_status or 'unknown'})"
            )
        _sleep_with_backoff(args.nesso_poll_interval, same_nesso_count)

    out = {
        "jobId": job_id,
        "foldStatus": _job_status(results),
        "nesso": {
            "status": str(nesso.get("status") or ("completed" if affinity else "")),
            "enabled": nesso.get("enabled"),
            "event": nesso.get("event"),
            "protein_chain_id": nesso.get("protein_chain_id") or nesso.get("proteinChainId"),
            "ligand_chain_id": nesso.get("ligand_chain_id") or nesso.get("ligandChainId"),
            "child_job_id": nesso.get("child_job_id") or nesso.get("childJobId"),
            "child_job_run_id": nesso.get("child_job_run_id") or nesso.get("childJobRunId"),
            "affinity_result_raw_json": affinity,
            "metrics_json_url": nesso.get("metrics_json_url"),
        },
    }

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        aff = affinity or {}
        pred = aff.get("affinity_pred_value")
        print(f"Fold: {_job_status(results)}")
        print(f"Nesso: {out['nesso']['status']}")
        if pred is not None:
            print(f"affinity_pred_value: {pred}")
        child = out["nesso"].get("child_job_id")
        if child:
            print(f"Nesso child job: {child}")


if __name__ == "__main__":
    main()
