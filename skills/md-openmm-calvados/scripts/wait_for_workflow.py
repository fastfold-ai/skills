#!/usr/bin/env python3
"""
Wait for an MD workflow to complete, then wait for metrics/artifacts to settle.

Stages:
  1. Poll /v1/workflows/status/<id> with bounded timeout until terminal state
     (COMPLETED, FAILED, STOPPED).
  2. If the task completed, poll /v1/workflows/public/<id> (public, no auth)
     or /v1/workflows/<id> (authed) until artifacts and metrics populate in
     result_raw_json (bounded by --metrics-timeout).

Exit codes:
  0 - terminal COMPLETED with metrics populated (or COMPLETED and metrics window exceeded)
  1 - terminal FAILED or STOPPED
  2 - timeout waiting for terminal status
  3 - terminal COMPLETED but metrics never appeared within --metrics-timeout

Environment: FASTFOLD_API_KEY (see load_env.py for resolution order).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from _api import TERMINAL_WORKFLOW_STATES, build_result_links, http_json, summarize_task_result
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id


def _latest_task_summary(response_payload: dict) -> dict:
    tasks = response_payload.get("tasks") if isinstance(response_payload.get("tasks"), list) else []
    latest = tasks[-1] if tasks else {}
    result_raw = latest.get("result_raw_json") if isinstance(latest, dict) else {}
    summary = summarize_task_result(result_raw)
    summary["workflow_status"] = response_payload.get("status")
    summary["task_status"] = latest.get("status") if isinstance(latest, dict) else None
    return summary


def _fetch_workflow_payload(
    base_url: str,
    api_key: str,
    workflow_id: str,
    *,
    is_public: bool,
) -> dict:
    if is_public:
        return http_json(
            base_url,
            "GET",
            f"/v1/workflows/public/{workflow_id}",
            api_key=api_key,
            auth=False,
        )
    # GET /v1/workflows/{id} returns the full workflow including
    # tasks[-1].result_raw_json, which is where artifacts/metrics land.
    # The /task-results endpoint intentionally omits result_raw_json, so
    # it can't be used to detect metrics settling.
    return http_json(
        base_url,
        "GET",
        f"/v1/workflows/{workflow_id}",
        api_key=api_key,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait for an MD workflow to complete and for metrics/plots to appear.",
    )
    parser.add_argument("workflow_id", help="Workflow ID (UUID) returned by /v1/workflows.")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Status poll interval (seconds).")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Max seconds to wait for terminal status.")
    parser.add_argument(
        "--metrics-timeout",
        type=float,
        default=900.0,
        help="Max seconds to wait for metrics/artifacts after terminal status.",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help=(
            "Use /v1/workflows/public/<id> (no auth) for result polling. "
            "Only works when the workflow was submitted with isPublic=true."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print combined JSON to stdout.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress log lines on stderr.")
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    workflow_id = validate_workflow_id(args.workflow_id)

    # Stage 1: wait for terminal status
    status_start = time.time()
    last_status = ""
    while True:
        status_payload = http_json(
            base_url,
            "GET",
            f"/v1/workflows/status/{workflow_id}",
            api_key=api_key,
        )
        status = str(status_payload.get("status") or "UNKNOWN").upper()
        if status != last_status:
            last_status = status
            if not args.quiet:
                print(
                    f"[FastFold] workflow {workflow_id} status: {status}",
                    file=sys.stderr,
                )
        if status in TERMINAL_WORKFLOW_STATES:
            break
        if (time.time() - status_start) > args.timeout:
            if args.json:
                print(json.dumps({"workflow_id": workflow_id, "status": status, "timedOut": True}, indent=2))
            sys.exit(2)
        time.sleep(max(0.5, float(args.poll_interval)))

    if status in {"FAILED", "STOPPED"}:
        if args.json:
            print(
                json.dumps(
                    {
                        "workflow_id": workflow_id,
                        "status": status,
                        "terminal": True,
                        "success": False,
                    },
                    indent=2,
                )
            )
        sys.exit(1)

    # Stage 2: wait for metrics/artifacts to settle (bounded)
    metrics_start = time.time()
    final_payload: dict = {}
    final_summary: dict = {}
    while True:
        final_payload = _fetch_workflow_payload(base_url, api_key, workflow_id, is_public=args.public)
        # Both public and authed endpoints now return a workflow-shaped
        # payload with `tasks[]` where the latest task has `result_raw_json`.
        final_summary = _latest_task_summary(final_payload)

        if final_summary.get("has_metrics") and final_summary.get("artifact_count"):
            break
        if (time.time() - metrics_start) > args.metrics_timeout:
            if args.json:
                print(
                    json.dumps(
                        {
                            "workflow_id": workflow_id,
                            "status": status,
                            "terminal": True,
                            "success": True,
                            "metrics_ready": False,
                            "summary": final_summary,
                        },
                        indent=2,
                    )
                )
            sys.exit(3)
        time.sleep(max(1.0, float(args.poll_interval)))

    # Detect isPublic flag from the final payload for the public link.
    is_public = False
    if isinstance(final_payload, dict):
        input_payload = final_payload.get("input_payload") if isinstance(final_payload.get("input_payload"), dict) else {}
        if isinstance(input_payload, dict):
            is_public = bool(input_payload.get("isPublic"))
    links = build_result_links(workflow_id, is_public=is_public)

    if args.json:
        print(
            json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": status,
                    "terminal": True,
                    "success": True,
                    "metrics_ready": True,
                    "summary": final_summary,
                    "links": links,
                },
                indent=2,
            )
        )
    else:
        print(
            f"[FastFold] workflow {workflow_id} ready: "
            f"status={status} task_status={final_summary.get('task_status')} "
            f"artifacts={final_summary.get('artifact_count')} "
            f"metrics={bool(final_summary.get('has_metrics'))}",
            file=sys.stderr,
        )
        print(f"[FastFold] dashboard: {links['dashboard_url']}", file=sys.stderr)
        if links.get("public_share_url"):
            print(f"[FastFold] public share: {links['public_share_url']}", file=sys.stderr)
        print(f"[FastFold] {links['py2dmol_invitation']}", file=sys.stderr)
        print(f"[FastFold] py2dmol: {links['py2dmol_url']}", file=sys.stderr)
        print(workflow_id)


if __name__ == "__main__":
    main()
