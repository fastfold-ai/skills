#!/usr/bin/env python3
"""
Fetch final MD workflow results: status, artifacts, and metrics summary.

By default, reads `/v1/workflows/<id>` (authed) to get the full workflow
including `tasks[-1].result_raw_json` (artifacts, `metrics`, `metricsJson`).
With `--public`, reads `/v1/workflows/public/<id>` (no auth) for the same
shape on public workflows.

Environment: FASTFOLD_API_KEY (see load_env.py for resolution order).
"""

from __future__ import annotations

import argparse
import json
import sys

from _api import build_result_links, http_json, summarize_task_result
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id


def _format_artifact_row(entry: dict) -> str:
    path = entry.get("path") or ""
    url = entry.get("url") or ""
    size = entry.get("sizeBytes")
    size_str = f" ({size} bytes)" if isinstance(size, int) else ""
    return f"- {path}{size_str} {url}".rstrip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch MD workflow status, artifacts, and metrics summary.",
    )
    parser.add_argument("workflow_id", help="Workflow ID (UUID).")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument(
        "--public",
        action="store_true",
        help=(
            "Read from /v1/workflows/public/<id> (no auth). "
            "Required to access artifacts/metrics when the workflow is private and you only have an API key."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON summary.")
    parser.add_argument(
        "--full-metrics",
        action="store_true",
        help="When used with --json, include the full metrics object (large).",
    )
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    workflow_id = validate_workflow_id(args.workflow_id)

    status_payload = http_json(
        base_url,
        "GET",
        f"/v1/workflows/status/{workflow_id}",
        api_key=api_key,
    )
    workflow_status = str(status_payload.get("status") or "").upper()
    status_tasks = status_payload.get("tasks") if isinstance(status_payload.get("tasks"), list) else []
    task_statuses = [str(t.get("status") or "") for t in status_tasks if isinstance(t, dict)]

    summary: dict = {
        "workflow_id": workflow_id,
        "workflow_status": workflow_status,
        "task_statuses": task_statuses,
    }
    is_public_workflow = False

    if args.public:
        payload = http_json(
            base_url,
            "GET",
            f"/v1/workflows/public/{workflow_id}",
            api_key=api_key,
            auth=False,
        )
    else:
        # GET /v1/workflows/{id} returns the full workflow, including
        # tasks[-1].result_raw_json which carries artifacts and metrics.
        payload = http_json(
            base_url,
            "GET",
            f"/v1/workflows/{workflow_id}",
            api_key=api_key,
        )

    input_payload = payload.get("input_payload") if isinstance(payload.get("input_payload"), dict) else {}
    is_public_workflow = bool(input_payload.get("isPublic")) if isinstance(input_payload, dict) else args.public
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    latest = tasks[-1] if tasks else {}
    result_raw = latest.get("result_raw_json") if isinstance(latest, dict) else {}
    task_summary = summarize_task_result(result_raw)
    task_summary["task_status"] = latest.get("status") if isinstance(latest, dict) else None
    task_summary["output_library_items"] = (
        latest.get("output_library_items") if isinstance(latest, dict) else None
    )
    summary["result_summary"] = task_summary
    summary["links"] = build_result_links(workflow_id, is_public=is_public_workflow)

    if args.json:
        if not args.full_metrics:
            result_summary = summary.get("result_summary")
            if isinstance(result_summary, dict):
                metrics = result_summary.get("metrics")
                if isinstance(metrics, dict):
                    result_summary["metrics_keys"] = sorted(metrics.keys())
                    del result_summary["metrics"]
                if isinstance(result_summary.get("metricsJson"), dict):
                    del result_summary["metricsJson"]
        print(json.dumps(summary, indent=2, default=str))
        return

    # Plain text summary
    result_summary = summary.get("result_summary") or {}
    print(f"workflow_id: {workflow_id}")
    print(f"workflow_status: {workflow_status}")
    print(f"task_status: {result_summary.get('task_status')}")
    print(f"artifacts: {result_summary.get('artifact_count', 0)}")
    metrics = result_summary.get("metrics") if isinstance(result_summary.get("metrics"), dict) else {}
    if metrics:
        print("metrics_keys: " + ", ".join(sorted(metrics.keys())))
    artifacts = result_summary.get("artifacts") if isinstance(result_summary.get("artifacts"), list) else []
    if artifacts:
        print("artifacts:")
        for entry in artifacts:
            print(_format_artifact_row(entry))

    links = summary.get("links") if isinstance(summary.get("links"), dict) else {}
    if links:
        print("")
        print(f"dashboard: {links.get('dashboard_url', '')}")
        if links.get("public_share_url"):
            print(f"public_share: {links.get('public_share_url')}")
        print("")
        print(links.get("py2dmol_invitation", ""))
        print(f"py2dmol: {links.get('py2dmol_url', '')}")


if __name__ == "__main__":
    main()
