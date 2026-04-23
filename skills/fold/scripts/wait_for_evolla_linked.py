#!/usr/bin/env python3
"""
Wait for a fold job, then wait for linked Evolla webhook answers.

Usage:
    python scripts/wait_for_evolla_linked.py JOB_ID --json
    python scripts/wait_for_evolla_linked.py JOB_ID --evolla-timeout 300 --max-not-found-polls 8
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
EVOLLA_TERMINAL_ERR = {"FAILED", "STOPPED"}


def _get_json(url: str, api_key: str, timeout: float = 30.0) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Error: Network error while requesting {url}: {e.reason}")

    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    if status == 404:
        sys.exit("Error: Resource not found.")
    if status >= 400:
        sys.exit(f"Error: {status} from {url} - {body}")

    try:
        return validate_results_payload(json.loads(body))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON from {url} (status {status}).")


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


def extract_sequence_ids(results: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    sequences = results.get("sequences") or []
    if isinstance(sequences, list):
        for row in sequences:
            if not isinstance(row, dict):
                continue
            sequence_id = str(row.get("id") or row.get("sequenceId") or row.get("sequence_id") or "").strip()
            if sequence_id and sequence_id not in seen:
                seen.add(sequence_id)
                out.append(sequence_id)
    sequence_ids_top = results.get("sequencesIds") or []
    if isinstance(sequence_ids_top, list):
        for raw in sequence_ids_top:
            sequence_id = str(raw or "").strip()
            if sequence_id and sequence_id not in seen:
                seen.add(sequence_id)
                out.append(sequence_id)
    return out


def _sequence_rank(sequence_type: str) -> int:
    t = str(sequence_type or "").strip().lower()
    if t == "protein":
        return 0
    if t in {"dna", "rna"}:
        return 1
    if t == "ligand":
        return 3
    return 2


def extract_preferred_sequence_ids(results: dict) -> list[str]:
    candidates: list[tuple[str, int, int]] = []
    sequences = results.get("sequences") or []
    if isinstance(sequences, list):
        for idx, row in enumerate(sequences):
            if not isinstance(row, dict):
                continue
            sequence_id = str(row.get("id") or row.get("sequenceId") or row.get("sequence_id") or "").strip()
            if not sequence_id:
                continue
            sequence_type = str(row.get("sequenceType") or row.get("sequence_type") or "").strip()
            candidates.append((sequence_id, _sequence_rank(sequence_type), idx))
    if not candidates:
        sequence_ids = extract_sequence_ids(results)
        return [sequence_ids[0]] if sequence_ids else []
    candidates.sort(key=lambda item: (item[1], item[2]))
    return [candidates[0][0]]


def get_latest_evolla_item(base_url: str, api_key: str, job_id: str, job_run_id: str, sequence_id: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "source_job_id": job_id,
            "source_job_run_id": job_run_id,
            "source_sequence_id": sequence_id,
            "limit": "1",
        }
    )
    url = f"{base_url.rstrip('/')}/v1/workflows/evolla/linked-history?{params}"
    data = _get_json(url, api_key=api_key, timeout=30.0)
    items = data.get("data") or []
    if not isinstance(items, list) or not items:
        return {
            "workflowStatus": "PENDING",
            "workflowId": "",
            "lastQuestion": "",
            "lastAnswer": "",
            "hasAnswer": False,
            "found": False,
        }
    latest = items[0] if isinstance(items[0], dict) else {}
    last_answer = str(latest.get("lastAnswer") or "").strip()
    return {
        "workflowStatus": str(latest.get("workflowStatus") or "PENDING").upper(),
        "workflowId": str(latest.get("workflowId") or "").strip(),
        "lastQuestion": str(latest.get("lastQuestion") or "").strip(),
        "lastAnswer": last_answer,
        "hasAnswer": bool(last_answer),
        "found": True,
    }


def _sleep_with_backoff(base_interval: float, same_status_count: int, max_interval: float) -> None:
    interval = max(0.2, base_interval)
    if same_status_count >= 4:
        interval = min(max_interval, interval * 1.5)
    if same_status_count >= 8:
        interval = min(max_interval, interval * 2.0)
    time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="Wait for fold completion and linked Evolla webhook answers.")
    ap.add_argument("job_id", help="FastFold job ID (UUID)")
    ap.add_argument("--job-run-id", help="Optional known jobRunId from fold results.")
    ap.add_argument("--sequence-id", action="append", default=[], help="Optional sequence UUID to monitor.")
    ap.add_argument(
        "--all-sequences",
        action="store_true",
        help="When no --sequence-id is provided, monitor all sequences from fold results.",
    )
    ap.add_argument("--poll-interval", type=float, default=4.0, help="Fold polling seconds (default 4)")
    ap.add_argument("--timeout", type=float, default=900.0, help="Fold wait timeout seconds (default 900)")
    ap.add_argument(
        "--evolla-poll-interval",
        type=float,
        default=4.0,
        help="Evolla linked-history polling seconds (default 4)",
    )
    ap.add_argument(
        "--evolla-timeout",
        type=float,
        default=900.0,
        help="Evolla wait timeout seconds (default 900)",
    )
    ap.add_argument(
        "--max-not-found-polls",
        type=int,
        default=8,
        help="Mark a sequence as NOT_FOUND after N linked-history polls with no workflow row (default 8).",
    )
    ap.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    ap.add_argument("--json", action="store_true", help="Print combined fold+evolla JSON to stdout")
    ap.add_argument("--quiet", action="store_true", help="Suppress progress status lines")
    args = ap.parse_args()

    api_key = resolve_fastfold_api_key()
    if not api_key:
        sys.exit("Error: FASTFOLD_API_KEY is not configured. Set it in env/.env or FastFold CLI config.")

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    manual_job_run_id = str(args.job_run_id or "").strip()
    if manual_job_run_id:
        manual_job_run_id = validate_job_id(manual_job_run_id)
    requested_sequence_ids = [validate_job_id(str(v)) for v in (args.sequence_id or []) if str(v).strip()]

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
            if args.json:
                print(json.dumps({"fold": fold_results, "evolla": {"items": [], "skipped": True}}, indent=2))
            sys.exit(1)
        if (time.time() - fold_start) > args.timeout:
            if args.json:
                print(json.dumps({"fold": fold_results, "evolla": {"items": [], "timedOut": True}}, indent=2))
            sys.exit(2)
        _sleep_with_backoff(args.poll_interval, same_fold_status_count, max_interval=20.0)

    job_run_id = manual_job_run_id or extract_job_run_id(fold_results)
    if not job_run_id:
        if args.json:
            print(
                json.dumps(
                    {
                        "fold": fold_results,
                        "evolla": {
                            "items": [],
                            "error": "Could not determine jobRunId from fold results payload.",
                        },
                    },
                    indent=2,
                )
            )
        sys.exit("Error: Could not determine jobRunId from /v1/jobs/{jobId}/results payload.")
    job_run_id = validate_job_id(job_run_id)

    if requested_sequence_ids:
        sequence_ids = requested_sequence_ids
    elif args.all_sequences:
        sequence_ids = [validate_job_id(v) for v in extract_sequence_ids(fold_results)]
    else:
        sequence_ids = [validate_job_id(v) for v in extract_preferred_sequence_ids(fold_results)]
    if not sequence_ids:
        payload = {
            "fold": fold_results,
            "evolla": {
                "jobRunId": job_run_id,
                "items": [],
                "note": "No sequence IDs were found in fold results payload.",
            },
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        if not args.quiet:
            print("[FastFold] No sequence IDs found; skipping linked Evolla polling.", file=sys.stderr)
        sys.exit(0)

    state_by_sequence: dict[str, dict] = {}
    for sequence_id in sequence_ids:
        state_by_sequence[sequence_id] = {
            "sourceSequenceId": sequence_id,
            "workflowId": "",
            "workflowStatus": "PENDING",
            "lastQuestion": "",
            "lastAnswer": "",
            "hasAnswer": False,
            "foundWorkflow": False,
            "done": False,
            "completedWithoutAnswerPolls": 0,
            "notFoundPolls": 0,
            "sameStatusCount": 0,
        }

    evolla_start = time.time()
    timed_out = False
    while True:
        remaining = [sid for sid, st in state_by_sequence.items() if not bool(st.get("done"))]
        if not remaining:
            break
        if (time.time() - evolla_start) > args.evolla_timeout:
            timed_out = True
            break

        for sequence_id in remaining:
            st = state_by_sequence[sequence_id]
            item = get_latest_evolla_item(base_url, api_key, job_id, job_run_id, sequence_id)
            next_status = str(item.get("workflowStatus") or "PENDING").upper()
            next_answer = str(item.get("lastAnswer") or "").strip()
            next_workflow_id = str(item.get("workflowId") or "").strip()
            next_question = str(item.get("lastQuestion") or "").strip()
            found_workflow = bool(item.get("found"))

            prev_status = str(st.get("workflowStatus") or "PENDING").upper()
            if next_status == prev_status:
                st["sameStatusCount"] = int(st.get("sameStatusCount") or 0) + 1
            else:
                st["sameStatusCount"] = 0

            status_changed = next_status != prev_status
            answer_changed = bool(next_answer) and next_answer != str(st.get("lastAnswer") or "")
            if not args.quiet and (status_changed or answer_changed):
                suffix = " (answer ready)" if next_answer else ""
                print(f"[FastFold] Evolla sequence {sequence_id} status: {next_status}{suffix}", file=sys.stderr)

            st["workflowStatus"] = next_status
            st["workflowId"] = next_workflow_id
            st["lastQuestion"] = next_question
            st["lastAnswer"] = next_answer
            st["hasAnswer"] = bool(next_answer)
            st["foundWorkflow"] = found_workflow

            if not found_workflow:
                st["notFoundPolls"] = int(st.get("notFoundPolls") or 0) + 1
                if int(st["notFoundPolls"]) >= max(1, int(args.max_not_found_polls)):
                    st["workflowStatus"] = "NOT_FOUND"
                    st["done"] = True
                continue
            st["notFoundPolls"] = 0

            if next_answer:
                st["done"] = True
                continue
            if next_status in EVOLLA_TERMINAL_ERR:
                st["done"] = True
                continue
            if next_status == "COMPLETED":
                st["completedWithoutAnswerPolls"] = int(st.get("completedWithoutAnswerPolls") or 0) + 1
                if int(st["completedWithoutAnswerPolls"]) >= 2:
                    st["done"] = True
                continue
            st["completedWithoutAnswerPolls"] = 0

        max_same = max(int(state_by_sequence[sid].get("sameStatusCount") or 0) for sid in remaining)
        _sleep_with_backoff(args.evolla_poll_interval, max_same, max_interval=15.0)

    items = []
    for sequence_id in sequence_ids:
        st = state_by_sequence[sequence_id]
        items.append(
            {
                "sourceSequenceId": sequence_id,
                "workflowId": st.get("workflowId") or "",
                "workflowStatus": st.get("workflowStatus") or "PENDING",
                "lastQuestion": st.get("lastQuestion") or "",
                "lastAnswer": st.get("lastAnswer") or "",
                "hasAnswer": bool(st.get("hasAnswer")),
                "foundWorkflow": bool(st.get("foundWorkflow")),
                "notFoundPolls": int(st.get("notFoundPolls") or 0),
            }
        )

    payload = {
        "fold": fold_results,
        "evolla": {
            "jobRunId": job_run_id,
            "timedOut": timed_out,
            "items": items,
        },
    }
    if any(str(i.get("workflowStatus") or "").upper() == "NOT_FOUND" for i in items):
        payload["evolla"]["note"] = (
            "No linked Evolla workflow was found for at least one sequence. "
            "This usually means constraints.webhooks.evolla.enabled was not set "
            "for this fold run, or linked workflow materialization is delayed."
        )

    if args.json:
        print(json.dumps(payload, indent=2))
    elif not args.quiet:
        for item in items:
            sid = item["sourceSequenceId"]
            status = str(item["workflowStatus"] or "PENDING")
            answer = str(item["lastAnswer"] or "").strip()
            if answer:
                print(f"[Evolla] {sid} answer: {answer}", file=sys.stderr)
            elif status == "NOT_FOUND":
                print(f"[Evolla] {sid} status: NOT_FOUND (no linked workflow row found)", file=sys.stderr)
            else:
                print(f"[Evolla] {sid} status: {status}", file=sys.stderr)

    if timed_out:
        sys.exit(2)
    has_terminal_error = any(str(i.get("workflowStatus") or "").upper() in EVOLLA_TERMINAL_ERR for i in items)
    if has_terminal_error:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
