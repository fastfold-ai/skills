#!/usr/bin/env python3
"""Unified Boltz CLI runner for all supported modes."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys


ROOT = "/tmp/boltz-runs"
PERSIST_ROOT = "/workspace/boltz-artifacts/boltz"


def run(cmd: list[str]) -> str:
    print("$ " + " ".join(shlex.quote(x) for x in cmd), file=sys.stderr)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.stdout.strip()


def extract_run_dir(stdout: str) -> str | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("/"):
            return line
    return None


def mirror_run_dir(run_dir: str) -> str | None:
    run_name = os.path.basename(run_dir.rstrip("/")) or "run"
    src = run_dir
    dest = os.path.join(PERSIST_ROOT, run_name)
    if os.path.abspath(src) == os.path.abspath(dest):
        return dest
    mirror_cmd = (
        f"mkdir -p {shlex.quote(dest)} && "
        f'if [ -d {shlex.quote(src)} ]; then '
        f"tar -C {shlex.quote(src)} -cf - . 2>/dev/null | "
        f"tar -C {shlex.quote(dest)} --touch -xf - 2>/dev/null; "
        "fi"
    )
    proc = subprocess.run(["bash", "-lc", mirror_cmd], text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        print(f"Warning: failed to mirror artifacts from {src} to {dest}", file=sys.stderr)
        return None
    return dest


MODE_SPEC = {
    "sab": {
        "estimate": ["boltz-api", "predictions:structure-and-binding", "estimate-cost", "--model", "boltz-2.1"],
        "start": [
            "boltz-api",
            "predictions:structure-and-binding",
            "start",
            "--model",
            "boltz-2.1",
            "--raw-output",
            "--transform",
            "id",
        ],
        "download_poll": "10",
    },
    "protein-design": {
        "estimate": ["boltz-api", "protein:design", "estimate-cost"],
        "start": ["boltz-api", "protein:design", "start", "--raw-output", "--transform", "id"],
        "download_poll": "60",
    },
    "protein-screen": {
        "estimate": ["boltz-api", "protein:library-screen", "estimate-cost"],
        "start": ["boltz-api", "protein:library-screen", "start", "--raw-output", "--transform", "id"],
        "download_poll": "30",
    },
    "sm-design": {
        "estimate": ["boltz-api", "small-molecule:design", "estimate-cost"],
        "start": ["boltz-api", "small-molecule:design", "start", "--raw-output", "--transform", "id"],
        "download_poll": "60",
    },
    "sm-screen": {
        "estimate": ["boltz-api", "small-molecule:library-screen", "estimate-cost"],
        "start": ["boltz-api", "small-molecule:library-screen", "start", "--raw-output", "--transform", "id"],
        "download_poll": "30",
    },
    "adme": {
        "estimate": ["boltz-api", "predictions:adme", "estimate-cost", "--model", "adme-v1"],
        "run": ["boltz-api", "predictions:adme", "run", "--model", "adme-v1"],
    },
}

RESOURCE_MAP = {
    "sab": "predictions:structure-and-binding",
    "protein_screen": "protein:library-screen",
    "protein_design": "protein:design",
    "sm_screen": "small-molecule:library-screen",
    "sm_design": "small-molecule:design",
    "adme": "predictions:adme",
}


def _run_mode(args: argparse.Namespace) -> int:
    spec = MODE_SPEC[args.mode]
    input_ref = f"@yaml://{args.payload}"
    estimate_output = run([*spec["estimate"], "--input", input_ref])

    if args.estimate_only:
        print("Estimate complete (--estimate-only).", file=sys.stderr)
        return 0
    if not args.yes:
        raise SystemExit("Refusing to submit without --yes. Use --estimate-only to run cost check only.")

    if args.mode == "adme":
        run_stdout = run(
            [
                *spec["run"],
                "--idempotency-key",
                args.run_name,
                "--input",
                input_ref,
                "--name",
                args.run_name,
                "--root-dir",
                args.root_dir,
                "--poll-interval-seconds",
                "5",
            ]
        )
        run_dir = extract_run_dir(run_stdout) or os.path.join(args.root_dir, args.run_name)
        persistent_run_dir = mirror_run_dir(run_dir)
        print(
            json.dumps(
                {
                    "idempotency_key": args.run_name,
                    "run_name": args.run_name,
                    "run_dir": run_dir,
                    "output_root": args.root_dir,
                    "persistent_run_dir": persistent_run_dir,
                    "estimate": estimate_output,
                }
            )
        )
        return 0

    job_id = run([*spec["start"], "--idempotency-key", args.run_name, "--input", input_ref]).splitlines()[-1].strip()
    run_stdout = run(
        [
            "boltz-api",
            "download-results",
            "--id",
            job_id,
            "--name",
            args.run_name,
            "--root-dir",
            args.root_dir,
            "--poll-interval-seconds",
            spec["download_poll"],
        ]
    )
    run_dir = extract_run_dir(run_stdout) or os.path.join(args.root_dir, args.run_name)
    persistent_run_dir = mirror_run_dir(run_dir)
    print(
        json.dumps(
            {
                "job_id": job_id,
                "idempotency_key": args.run_name,
                "run_name": args.run_name,
                "run_dir": run_dir,
                "output_root": args.root_dir,
                "persistent_run_dir": persistent_run_dir,
                "estimate": estimate_output,
            }
        )
    )
    return 0


def _status_mode(args: argparse.Namespace) -> int:
    if args.action == "status":
        run(["boltz-api", "--format", "json", "download-status", "--name", args.run_name, "--root-dir", args.root_dir])
        return 0
    if args.action == "retrieve":
        run(["boltz-api", RESOURCE_MAP[args.resource], "retrieve", "--id", args.job_id, "--format", "json"])
        return 0
    if args.action == "resume":
        run(
            [
                "boltz-api",
                "download-results",
                "--id",
                args.job_id,
                "--name",
                args.run_name,
                "--root-dir",
                args.root_dir,
                "--poll-interval-seconds",
                args.poll_interval_seconds,
            ]
        )
        return 0
    if args.action == "stop":
        run(["boltz-api", RESOURCE_MAP[args.resource], "stop", "--id", args.job_id, "--format", "json"])
        return 0
    # list
    for resource in RESOURCE_MAP.values():
        run(["boltz-api", resource, "list", "--limit", args.limit, "--format", "jsonl"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    for mode in ("sab", "protein-design", "protein-screen", "sm-design", "sm-screen", "adme"):
        p = sub.add_parser(mode)
        p.add_argument("--payload", required=True)
        p.add_argument("--run-name", required=True)
        p.add_argument("--root-dir", default=ROOT)
        p.add_argument("--estimate-only", action="store_true")
        p.add_argument("--yes", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("--action", choices=("status", "retrieve", "resume", "stop", "list"), required=True)
    status.add_argument("--run-name")
    status.add_argument("--job-id")
    status.add_argument("--resource", choices=sorted(RESOURCE_MAP.keys()))
    status.add_argument("--root-dir", default=ROOT)
    status.add_argument("--poll-interval-seconds", default="30")
    status.add_argument("--limit", default="20")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "status":
        if args.action == "status" and not args.run_name:
            raise SystemExit("--run-name is required for status action")
        if args.action in {"retrieve", "stop"} and (not args.job_id or not args.resource):
            raise SystemExit("--job-id and --resource are required for retrieve/stop action")
        if args.action == "resume" and (not args.job_id or not args.run_name):
            raise SystemExit("--job-id and --run-name are required for resume action")
        return _status_mode(args)
    return _run_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
