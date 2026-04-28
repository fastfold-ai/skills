#!/usr/bin/env python3
"""
Toggle public/private visibility of an OpenMMDL workflow.

Calls PATCH /v1/workflows/<workflow_id>/public with { "isPublic": <bool> }.
"""

from __future__ import annotations

import argparse
import json
import sys

from _api import http_json
from load_env import resolve_fastfold_api_key
from security_utils import validate_base_url, validate_workflow_id

SHARE_URL_TEMPLATE = "https://cloud.fastfold.ai/openmmdl/results/{workflow_id}?shared=true"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set an OpenMMDL workflow to public or private.",
    )
    parser.add_argument("workflow_id", help="Workflow ID (UUID).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--public", dest="public", action="store_true", help="Make the workflow public.")
    group.add_argument("--private", dest="public", action="store_false", help="Make the workflow private.")
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

    response = http_json(
        base_url,
        "PATCH",
        f"/v1/workflows/{workflow_id}/public",
        api_key=api_key,
        body={"isPublic": bool(args.public)},
    )

    is_public_now = bool(response.get("isPublic"))
    share_url = SHARE_URL_TEMPLATE.format(workflow_id=workflow_id) if is_public_now else ""

    if args.json:
        print(
            json.dumps(
                {
                    "workflow_id": workflow_id,
                    "isPublic": is_public_now,
                    "share_url": share_url,
                },
                indent=2,
            )
        )
        return

    state = "PUBLIC" if is_public_now else "PRIVATE"
    print(f"workflow_id: {workflow_id}")
    print(f"status: {state}")
    if share_url:
        print(f"share_url: {share_url}")


if __name__ == "__main__":
    main()
