#!/usr/bin/env python3
"""
Wait for a fold job, then wait for linked OpenMM webhook workflow results.

Usage:
    python scripts/wait_for_openmm_linked.py JOB_ID --json
    python scripts/wait_for_openmm_linked.py JOB_ID --workflow-timeout 2400 --metrics-timeout 900
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_job_id, validate_results_payload

FOLD_TERMINAL_OK = {"COMPLETED"}
FOLD_TERMINAL_ERR = {"FAILED", "STOPPED"}
DELIVERY_TERMINAL_OK = {"SUCCEEDED", "SUCCESS"}
DELIVERY_TERMINAL_ERR = {"FAILED", "ERROR"}
WORKFLOW_TERMINAL_OK = {"COMPLETED"}
WORKFLOW_TERMINAL_ERR = {"FAILED", "STOPPED", "CANCELED", "CANCELLED"}


def _request_json(
    url: str,
    api_key: str,
    *,
    timeout: float = 30.0,
    allow_404: bool = False,
) -> tuple[int, dict]:
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
    if status == 404 and allow_404:
        return 404, {}
    if status >= 400:
        sys.exit(f"Error: {status} from {url} - {body}")

    try:
        data = validate_results_payload(json.loads(body))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON from {url} (status {status}).")
    return status, data


def _get_json(url: str, api_key: str, *, timeout: float = 30.0) -> dict:
    _, data = _request_json(url, api_key, timeout=timeout)
    return data


def get_fold_results(base_url: str, api_key: str, job_id: str) -> dict:
    return _get_json(f"{base_url.rstrip('/')}/v1/jobs/{job_id}/results", api_key=api_key, timeout=30.0)


def extract_job_run_id(results: dict) -> str:
    candidates = [
        results.get("jobRunId"),
        (results.get("job") or {}).get("jobRunId"),
        (results.get("parameters") or {}).get("jobRunId"),
    ]
    sequences = results.get("sequences") or []
    if isinstance(sequences, list):
        for row in sequences:
            if isinstance(row, dict):
                candidates.append(row.get("jobRunId"))
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _mapping_value(mapping: dict, *keys: str) -> str:
    for key in keys:
        value = str(mapping.get(key) or "").strip()
        if value:
            return value
    return ""


def list_openmm_subscriptions_for_run(
    base_url: str,
    api_key: str,
    *,
    job_id: str,
    job_run_id: str,
) -> list[dict]:
    data = _get_json(f"{base_url.rstrip('/')}/v1/webhooks/subscriptions", api_key=api_key, timeout=30.0)
    rows = data.get("data") if isinstance(data.get("data"), list) else []
    out: list[dict] = []
    job_id_lower = job_id.strip().lower()
    run_id_lower = job_run_id.strip().lower()

    for row in rows:
        if not isinstance(row, dict):
            continue
        target_type = str(row.get("target_type") or "").strip().lower()
        if target_type != "calvados_openmm_v1":
            continue

        mapping = row.get("input_mapping") if isinstance(row.get("input_mapping"), dict) else {}
        source_job = _mapping_value(mapping, "sourceJobId", "source_job_id").lower()
        source_run = _mapping_value(mapping, "sourceJobRunId", "source_job_run_id").lower()
        by_mapping = bool(source_job and source_job == job_id_lower and (not source_run or source_run == run_id_lower))

        raw_name = str(row.get("name") or "").strip().lower()
        by_name_prefix = raw_name.startswith(f"fold:{job_id_lower}:")

        if by_mapping or by_name_prefix:
            out.append(row)
    return out


def list_deliveries_for_subscriptions(
    base_url: str,
    api_key: str,
    *,
    subscription_ids: set[str],
    limit: int,
) -> list[dict]:
    if not subscription_ids:
        return []
    params = urllib.parse.urlencode({"limit": str(max(1, int(limit)))})
    data = _get_json(f"{base_url.rstrip('/')}/v1/webhooks/deliveries?{params}", api_key=api_key, timeout=30.0)
    rows = data.get("data") if isinstance(data.get("data"), list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("subscription_id") or "") in subscription_ids:
            out.append(row)
    out.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return out


def get_openmm_workflow_status(
    base_url: str,
    api_key: str,
    workflow_id: str,
) -> str:
    status_payload = _get_json(
        f"{base_url.rstrip('/')}/v1/workflows/status/{workflow_id}",
        api_key=api_key,
        timeout=30.0,
    )
    return str(status_payload.get("status") or "UNKNOWN").upper()


def get_workflow_payload(base_url: str, api_key: str, workflow_id: str) -> dict:
    status, data = _request_json(
        f"{base_url.rstrip('/')}/v1/workflows/{workflow_id}",
        api_key=api_key,
        timeout=30.0,
        allow_404=True,
    )
    if status == 404:
        return {}
    return data


def summarize_workflow_payload(payload: dict) -> dict:
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    latest = tasks[-1] if tasks and isinstance(tasks[-1], dict) else {}
    result_raw = latest.get("result_raw_json") if isinstance(latest.get("result_raw_json"), dict) else {}
    artifacts = result_raw.get("artifacts") if isinstance(result_raw.get("artifacts"), list) else []
    metrics = result_raw.get("metrics") if isinstance(result_raw.get("metrics"), dict) else {}
    return {
        "taskStatus": str(latest.get("status") or "").upper(),
        "artifactCount": len(artifacts),
        "hasMetrics": bool(metrics),
        "metricsKeys": sorted(metrics.keys()) if metrics else [],
    }


def build_openmm_links(workflow_id: str, is_public: bool) -> dict:
    dashboard_url = f"https://cloud.fastfold.ai/openmm/results/{workflow_id}"
    return {
        "dashboard_url": dashboard_url,
        "public_share_url": f"{dashboard_url}?shared=true" if is_public else "",
        "py2dmol_url": f"https://cloud.fastfold.ai/py2dmol/new?from=openmm_workflow&workflow_id={workflow_id}",
    }


def _sleep_with_backoff(base_interval: float, same_status_count: int, max_interval: float) -> None:
    interval = max(0.2, base_interval)
    if same_status_count >= 4:
        interval = min(max_interval, interval * 1.5)
    if same_status_count >= 8:
        interval = min(max_interval, interval * 2.0)
    time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Wait for fold completion, linked OpenMM webhook delivery, and OpenMM workflow completion."
    )
    ap.add_argument("job_id", help="FastFold job ID (UUID)")
    ap.add_argument("--job-run-id", help="Optional known jobRunId. If omitted, resolved from fold results.")
    ap.add_argument("--poll-interval", type=float, default=4.0, help="Fold polling seconds (default 4)")
    ap.add_argument("--timeout", type=float, default=900.0, help="Fold wait timeout seconds (default 900)")
    ap.add_argument(
        "--webhook-poll-interval",
        type=float,
        default=4.0,
        help="Webhook delivery polling seconds (default 4)",
    )
    ap.add_argument(
        "--webhook-timeout",
        type=float,
        default=600.0,
        help="Webhook linkage timeout seconds (default 600)",
    )
    ap.add_argument(
        "--workflow-poll-interval",
        type=float,
        default=6.0,
        help="OpenMM workflow status polling seconds (default 6)",
    )
    ap.add_argument(
        "--workflow-timeout",
        type=float,
        default=2400.0,
        help="OpenMM workflow wait timeout seconds (default 2400)",
    )
    ap.add_argument(
        "--metrics-timeout",
        type=float,
        default=900.0,
        help="Seconds to wait for OpenMM metrics/artifacts after workflow completion (default 900)",
    )
    ap.add_argument(
        "--delivery-limit",
        type=int,
        default=200,
        help="How many recent deliveries to scan per poll (default 200)",
    )
    ap.add_argument(
        "--max-not-found-polls",
        type=int,
        default=8,
        help="Mark webhook linkage as NOT_FOUND after N polls with no delivery row (default 8).",
    )
    ap.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    ap.add_argument("--json", action="store_true", help="Print combined fold+openmm JSON to stdout")
    ap.add_argument("--quiet", action="store_true", help="Suppress progress status lines")
    args = ap.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit("Error: FASTFOLD_API_KEY is not configured. Set it in .env or environment.")

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    manual_job_run_id = str(args.job_run_id or "").strip()
    if manual_job_run_id:
        manual_job_run_id = validate_job_id(manual_job_run_id)

    # Step 1: wait for fold completion
    fold_start = time.time()
    fold_results: dict = {}
    last_fold_status = ""
    same_fold_status_count = 0
    while True:
        fold_results = get_fold_results(base_url, api_key, job_id)
        status = str((fold_results.get("job") or {}).get("status") or "UNKNOWN").upper()
        if status == last_fold_status:
            same_fold_status_count += 1
        else:
            same_fold_status_count = 0
            last_fold_status = status
            if not args.quiet:
                print(f"[FastFold] job {job_id} status: {status}", file=sys.stderr)

        if status in FOLD_TERMINAL_OK:
            break
        if status in FOLD_TERMINAL_ERR:
            payload = {
                "fold": fold_results,
                "openmm": {"skipped": True, "reason": f"Fold ended in terminal error status {status}"},
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(1)
        if (time.time() - fold_start) > args.timeout:
            payload = {
                "fold": fold_results,
                "openmm": {"timedOut": True, "reason": "Timed out waiting for fold completion."},
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(2)

        _sleep_with_backoff(args.poll_interval, same_fold_status_count, max_interval=20.0)

    job_run_id = manual_job_run_id or extract_job_run_id(fold_results)
    if not job_run_id:
        payload = {
            "fold": fold_results,
            "openmm": {"error": "Could not determine jobRunId from fold results payload."},
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        sys.exit("Error: Could not determine jobRunId from /v1/jobs/{jobId}/results payload.")
    job_run_id = validate_job_id(job_run_id)

    # Step 2: wait for OpenMM webhook delivery with triggered target id
    webhook_start = time.time()
    last_delivery_status = ""
    same_delivery_status_count = 0
    not_found_polls = 0
    matched_subscriptions: list[dict] = []
    latest_delivery: dict = {}
    openmm_workflow_id = ""

    while True:
        matched_subscriptions = list_openmm_subscriptions_for_run(
            base_url,
            api_key,
            job_id=job_id,
            job_run_id=job_run_id,
        )
        subscription_ids = {str(row.get("id") or "") for row in matched_subscriptions if str(row.get("id") or "")}
        deliveries = list_deliveries_for_subscriptions(
            base_url,
            api_key,
            subscription_ids=subscription_ids,
            limit=max(1, int(args.delivery_limit)),
        )
        latest_delivery = deliveries[0] if deliveries else {}
        delivery_status = str(latest_delivery.get("status") or "PENDING").upper()
        openmm_workflow_id = str(latest_delivery.get("triggered_target_id") or "").strip()

        if latest_delivery:
            not_found_polls = 0
        else:
            not_found_polls += 1

        if delivery_status == last_delivery_status:
            same_delivery_status_count += 1
        else:
            same_delivery_status_count = 0
            last_delivery_status = delivery_status
            if not args.quiet:
                print(f"[FastFold] OpenMM webhook delivery status: {delivery_status}", file=sys.stderr)

        if openmm_workflow_id and delivery_status in DELIVERY_TERMINAL_OK:
            break
        if delivery_status in DELIVERY_TERMINAL_ERR:
            payload = {
                "fold": fold_results,
                "openmm": {
                    "jobRunId": job_run_id,
                    "subscriptionIds": sorted(subscription_ids),
                    "delivery": latest_delivery,
                    "timedOut": False,
                    "workflowId": openmm_workflow_id,
                    "workflowStatus": "NOT_STARTED",
                },
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(1)
        if not_found_polls >= max(1, int(args.max_not_found_polls)):
            payload = {
                "fold": fold_results,
                "openmm": {
                    "jobRunId": job_run_id,
                    "subscriptionIds": sorted(subscription_ids),
                    "delivery": latest_delivery,
                    "timedOut": False,
                    "workflowId": "",
                    "workflowStatus": "NOT_FOUND",
                    "note": (
                        "No linked OpenMM webhook delivery row was found. "
                        "Verify constraints.webhooks.openmm.enabled was set for this fold run."
                    ),
                },
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(2)
        if (time.time() - webhook_start) > args.webhook_timeout:
            payload = {
                "fold": fold_results,
                "openmm": {
                    "jobRunId": job_run_id,
                    "subscriptionIds": sorted(subscription_ids),
                    "delivery": latest_delivery,
                    "timedOut": True,
                    "workflowId": openmm_workflow_id,
                    "workflowStatus": "PENDING",
                },
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(2)

        _sleep_with_backoff(args.webhook_poll_interval, same_delivery_status_count, max_interval=20.0)

    openmm_workflow_id = validate_job_id(openmm_workflow_id)

    # Step 3: wait for linked OpenMM workflow completion
    workflow_start = time.time()
    last_workflow_status = ""
    same_workflow_status_count = 0
    workflow_status = "UNKNOWN"
    while True:
        workflow_status = get_openmm_workflow_status(base_url, api_key, openmm_workflow_id)
        if workflow_status == last_workflow_status:
            same_workflow_status_count += 1
        else:
            same_workflow_status_count = 0
            last_workflow_status = workflow_status
            if not args.quiet:
                print(
                    f"[FastFold] OpenMM workflow {openmm_workflow_id} status: {workflow_status}",
                    file=sys.stderr,
                )

        if workflow_status in WORKFLOW_TERMINAL_OK | WORKFLOW_TERMINAL_ERR:
            break
        if (time.time() - workflow_start) > args.workflow_timeout:
            payload = {
                "fold": fold_results,
                "openmm": {
                    "jobRunId": job_run_id,
                    "subscriptionIds": sorted(
                        {str(row.get("id") or "") for row in matched_subscriptions if str(row.get("id") or "")}
                    ),
                    "delivery": latest_delivery,
                    "timedOut": True,
                    "workflowId": openmm_workflow_id,
                    "workflowStatus": workflow_status,
                },
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(2)
        _sleep_with_backoff(args.workflow_poll_interval, same_workflow_status_count, max_interval=20.0)

    if workflow_status in WORKFLOW_TERMINAL_ERR:
        payload = {
            "fold": fold_results,
            "openmm": {
                "jobRunId": job_run_id,
                "subscriptionIds": sorted(
                    {str(row.get("id") or "") for row in matched_subscriptions if str(row.get("id") or "")}
                ),
                "delivery": latest_delivery,
                "timedOut": False,
                "workflowId": openmm_workflow_id,
                "workflowStatus": workflow_status,
            },
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        sys.exit(1)

    # Step 4: wait for metrics/artifacts to settle
    metrics_start = time.time()
    workflow_payload: dict = {}
    workflow_summary: dict = {}
    while True:
        workflow_payload = get_workflow_payload(base_url, api_key, openmm_workflow_id)
        workflow_summary = summarize_workflow_payload(workflow_payload) if workflow_payload else {}
        if workflow_summary.get("artifactCount") and workflow_summary.get("hasMetrics"):
            break
        if (time.time() - metrics_start) > args.metrics_timeout:
            payload = {
                "fold": fold_results,
                "openmm": {
                    "jobRunId": job_run_id,
                    "subscriptionIds": sorted(
                        {str(row.get("id") or "") for row in matched_subscriptions if str(row.get("id") or "")}
                    ),
                    "delivery": latest_delivery,
                    "timedOut": False,
                    "workflowId": openmm_workflow_id,
                    "workflowStatus": workflow_status,
                    "metricsReady": False,
                    "summary": workflow_summary,
                },
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            sys.exit(3)
        time.sleep(max(1.0, float(args.workflow_poll_interval)))

    input_payload = workflow_payload.get("input_payload") if isinstance(workflow_payload.get("input_payload"), dict) else {}
    is_public = bool(input_payload.get("isPublic")) if isinstance(input_payload, dict) else False
    links = build_openmm_links(openmm_workflow_id, is_public)

    payload = {
        "fold": fold_results,
        "openmm": {
            "jobRunId": job_run_id,
            "subscriptionIds": sorted(
                {str(row.get("id") or "") for row in matched_subscriptions if str(row.get("id") or "")}
            ),
            "delivery": latest_delivery,
            "timedOut": False,
            "workflowId": openmm_workflow_id,
            "workflowStatus": workflow_status,
            "metricsReady": True,
            "summary": workflow_summary,
            "links": links,
        },
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    elif not args.quiet:
        print(
            f"[FastFold] OpenMM linked workflow ready: {openmm_workflow_id} "
            f"(status={workflow_status}, artifacts={workflow_summary.get('artifactCount')})",
            file=sys.stderr,
        )
        print(f"[FastFold] dashboard: {links['dashboard_url']}", file=sys.stderr)
        if links.get("public_share_url"):
            print(f"[FastFold] public share: {links['public_share_url']}", file=sys.stderr)
        print(
            "[FastFold] Trajectory is available for this run to visualize simulation, "
            "generate animations, and use playback controls in Py2DMol.",
            file=sys.stderr,
        )
        print(f"[FastFold] py2dmol: {links['py2dmol_url']}", file=sys.stderr)
        print(openmm_workflow_id)

    sys.exit(0)


if __name__ == "__main__":
    main()
