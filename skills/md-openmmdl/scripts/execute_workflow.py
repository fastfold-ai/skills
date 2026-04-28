#!/usr/bin/env python3
"""
Execute an existing draft workflow via POST /v1/workflows/execute.

Use this for DRAFT OpenMMDL workflows created with create_mode=draft_script.
"""

from __future__ import annotations

import argparse
import json
import sys

from _api import http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute a draft workflow by workflow ID.",
    )
    parser.add_argument("workflow_id", help="Workflow ID (UUID).")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--json", action="store_true", help="Print full JSON response.")
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Set it in environment, .env, or ~/.fastfold-cli/config.json."
        )

    base_url = validate_base_url(args.base_url)
    workflow_id = validate_workflow_id(args.workflow_id)

    payload = http_json(
        base_url,
        "POST",
        "/v1/workflows/execute",
        api_key=api_key,
        body={"workflowId": workflow_id},
    )

    resolved_id = str(payload.get("workflow_id") or workflow_id).strip()
    dashboard_url = f"https://cloud.fastfold.ai/openmmdl/results/{resolved_id}"

    if args.json:
        out = dict(payload)
        out["dashboard_url"] = dashboard_url
        print(json.dumps(out, indent=2, default=str))
        return

    print(resolved_id)
    print(f"[FastFold] dashboard: {dashboard_url}", file=sys.stderr)


if __name__ == "__main__":
    main()
