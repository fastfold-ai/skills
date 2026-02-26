#!/usr/bin/env python3
"""
Send a markdown report to Fastfold Slack report endpoint.

Posts to /v1/slack/messages/agent-cli-report using FASTFOLD_API_KEY.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _resolve_fastfold_api_key() -> str | None:
    api_key = (os.environ.get("FASTFOLD_API_KEY") or "").strip()
    if api_key:
        return api_key

    config_path = Path.home() / ".fastfold-cli" / "config.json"
    if not config_path.exists():
        return None
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            return None
        cfg_key = str(cfg.get("api.fastfold_cloud_key") or "").strip()
        if not cfg_key:
            return None
        os.environ["FASTFOLD_API_KEY"] = cfg_key
        return cfg_key
    except Exception:
        return None


def _read_markdown(markdown_file: str | None, use_stdin: bool) -> str:
    if use_stdin:
        return sys.stdin.read()
    if not markdown_file:
        raise ValueError("Provide --markdown-file or --stdin.")
    return Path(markdown_file).read_text(encoding="utf-8")


def _post_report(base_url: str, api_key: str, markdown: str, report_name: str | None) -> dict:
    url = f"{base_url.rstrip('/')}/v1/slack/messages/agent-cli-report"
    body = json.dumps(
        {
            "markdown": markdown,
            "report_name": report_name,
            "save_to_library": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = {"message": f"HTTP {exc.code}"}
        return {"ok": False, **payload}
    except urllib.error.URLError as exc:
        return {"ok": False, "message": f"Network error: {exc.reason}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send markdown report to configured Slack channel.")
    parser.add_argument("--markdown-file", help="Path to markdown file")
    parser.add_argument("--stdin", action="store_true", help="Read markdown from stdin")
    parser.add_argument("--report-name", help="Optional report name shown in library item")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="Fastfold API base URL")
    parser.add_argument("--json", action="store_true", help="Print full JSON response")
    args = parser.parse_args()

    api_key = _resolve_fastfold_api_key()
    if not api_key:
        sys.exit(
            "Error: FASTFOLD_API_KEY is not configured. "
            "Run `fastfold setup` or set `api.fastfold_cloud_key` in FastFold CLI config."
        )

    try:
        markdown = _read_markdown(args.markdown_file, args.stdin)
    except Exception as exc:
        sys.exit(f"Error: {exc}")

    if not markdown.strip():
        sys.exit("Error: markdown content is empty.")

    report_name = args.report_name
    if not report_name and args.markdown_file:
        report_name = Path(args.markdown_file).name

    payload = _post_report(args.base_url, api_key, markdown, report_name)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if payload.get("ok"):
            print(f"ok: shared to channel {payload.get('channel_id')}")
            if payload.get("library_item_id"):
                print(f"library_item_id: {payload.get('library_item_id')}")
        else:
            print(payload.get("message") or "Failed to share report.")
            if payload.get("needs_slack_setup"):
                print(payload.get("setup_instructions") or "Configure Slack in Fastfold Cloud integrations.")
            sys.exit(1)


if __name__ == "__main__":
    main()
