#!/usr/bin/env python3
"""Unified Boltz CLI runner for all supported modes."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = "/tmp/boltz-runs"
PERSIST_ROOT = "/workspace/boltz-artifacts/boltz"
BOLTZ_INSTALL_SCRIPT = (
    "set -euo pipefail; curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
)
BOLTZ_API_BIN = "boltz-api"


def find_boltz_cli() -> str | None:
    """Return the first available boltz-api executable path."""
    in_path = shutil.which("boltz-api")
    if in_path:
        return in_path
    for candidate in (
        Path.home() / ".local" / "bin" / "boltz-api",
        Path.home() / ".boltz" / "bin" / "boltz-api",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def ensure_boltz_cli() -> str:
    """Install boltz-api with the official installer when missing."""
    global BOLTZ_API_BIN

    existing = find_boltz_cli()
    if existing:
        BOLTZ_API_BIN = existing
        return existing

    if not shutil.which("curl") or not shutil.which("sh"):
        raise SystemExit(
            "boltz-api is not available and automatic install requires curl + sh. "
            "Install manually: curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )

    print("boltz-api not found; installing via official Boltz installer...", file=sys.stderr)
    proc = subprocess.run(
        ["sh", "-lc", BOLTZ_INSTALL_SCRIPT],
        text=True,
        capture_output=True,
        timeout=180,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        detail = detail.splitlines()[-1] if detail else "installer exited with a non-zero code"
        raise SystemExit(
            "boltz-api automatic install failed: "
            f"{detail}. Retry manually: curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )

    installed = find_boltz_cli()
    if not installed:
        raise SystemExit(
            "boltz-api installer completed, but executable was not found. "
            "Ensure ~/.local/bin is on PATH or rerun the official installer."
        )

    version_proc = subprocess.run(
        [installed, "--version"],
        text=True,
        capture_output=True,
        timeout=10,
    )
    version = (version_proc.stdout or version_proc.stderr or "").strip().splitlines()
    version_text = version[0] if version else "unknown version"
    print(f"Installed boltz-api at {installed} ({version_text})", file=sys.stderr)
    BOLTZ_API_BIN = installed
    return installed


def run(cmd: list[str]) -> str:
    if cmd and cmd[0] == "boltz-api":
        cmd = [BOLTZ_API_BIN, *cmd[1:]]
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


def capture(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command quietly and return (returncode, stdout, stderr) without raising."""
    if cmd and cmd[0] == "boltz-api":
        cmd = [BOLTZ_API_BIN, *cmd[1:]]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def persist_dir_for(run_name: str) -> str:
    return os.path.join(PERSIST_ROOT, run_name)


def mirror_run_dir(run_dir: str) -> str | None:
    run_name = os.path.basename(run_dir.rstrip("/")) or "run"
    src = run_dir
    dest = persist_dir_for(run_name)
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


def write_manifest(run_name: str, run_dir: str, data: dict) -> None:
    """Persist a durable run manifest to both the ephemeral run dir and the workspace mirror.

    The sandbox /tmp tree is wiped on eviction, so the workspace copy is what lets us
    recover the job_id (and resource) for a run-name after the sandbox is recreated.
    """
    payload = json.dumps(data, indent=2)
    for target in (run_dir, persist_dir_for(run_name)):
        try:
            os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "manifest.json"), "w") as fh:
                fh.write(payload)
        except OSError as exc:  # best-effort durability; never fail the run on this
            print(f"Warning: could not write manifest to {target}: {exc}", file=sys.stderr)


def read_persisted_manifest(run_name: str) -> dict | None:
    path = os.path.join(persist_dir_for(run_name), "manifest.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def restore_from_persist(run_name: str, root_dir: str) -> bool:
    """Copy a workspace mirror back into /tmp when local run metadata is missing.

    Returns True only when local run metadata exists afterwards.
    """
    local_dir = os.path.join(root_dir, run_name)
    persist_dir = persist_dir_for(run_name)
    local_meta = os.path.join(local_dir, ".boltz-run.json")
    if os.path.exists(local_meta):
        return True
    if not os.path.isdir(persist_dir):
        return False
    restore_cmd = (
        f"mkdir -p {shlex.quote(local_dir)} && "
        f"tar -C {shlex.quote(persist_dir)} -cf - . 2>/dev/null | "
        f"tar -C {shlex.quote(local_dir)} --touch -xf - 2>/dev/null"
    )
    subprocess.run(["bash", "-lc", restore_cmd], text=True, capture_output=True)
    if os.path.exists(local_meta):
        print(f"Restored local run dir from workspace mirror: {persist_dir} -> {local_dir}", file=sys.stderr)
        return True
    return False


def find_job_by_run_name(run_name: str) -> tuple[str | None, str | None]:
    """Recover (job_id, resource_key) for a run-name directly from the Boltz API.

    Prefers the persisted workspace manifest, then falls back to scanning API list
    output across resources for a job whose idempotency_key matches the run-name.
    """
    manifest = read_persisted_manifest(run_name)
    if manifest and manifest.get("job_id"):
        return manifest.get("job_id"), manifest.get("resource")
    # No manifest: scan every job across resources. --max-items -1 auto-paginates the
    # cursor-based listing so we don't miss the target in a workspace with many jobs.
    for resource_key, resource in RESOURCE_MAP.items():
        rc, out, _ = capture(["boltz-api", resource, "list", "--max-items", "-1", "--format", "jsonl"])
        if rc != 0:
            continue
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("idempotency_key") == run_name:
                return obj.get("id"), resource_key
    return None, None


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

# Pipeline resources support early `stop` and paginated `list-results`.
# Predictions (`sab`, `adme`) do not: they finish quickly and expose results via `retrieve`.
PIPELINE_RESOURCES = {"protein_design", "protein_screen", "sm_design", "sm_screen"}


def _run_mode(args: argparse.Namespace) -> int:
    spec = MODE_SPEC[args.mode]
    input_ref = f"@yaml://{args.payload}"
    estimate_output = run([*spec["estimate"], "--input", input_ref])

    if args.estimate_only:
        print("Estimate complete (--estimate-only).", file=sys.stderr)
        return 0
    if not args.yes:
        raise SystemExit("Refusing to submit without --yes. Use --estimate-only to run cost check only.")

    resource_key = args.mode.replace("-", "_")

    if args.mode == "adme":
        write_manifest(
            args.run_name,
            os.path.join(args.root_dir, args.run_name),
            {"run_name": args.run_name, "mode": args.mode, "resource": resource_key, "idempotency_key": args.run_name},
        )
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
    # Persist the run manifest immediately (before the long download poll) so the
    # job_id survives sandbox eviction / an interrupted wait and stays recoverable.
    write_manifest(
        args.run_name,
        os.path.join(args.root_dir, args.run_name),
        {
            "run_name": args.run_name,
            "job_id": job_id,
            "mode": args.mode,
            "resource": resource_key,
            "idempotency_key": args.run_name,
        },
    )
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


def _download_and_mirror(job_id: str, run_name: str, root_dir: str, poll_interval_seconds: str) -> tuple[str, str | None]:
    """Download a job's artifacts into /tmp, then mirror them to the persistent workspace."""
    run(
        [
            "boltz-api",
            "download-results",
            "--id",
            job_id,
            "--name",
            run_name,
            "--root-dir",
            root_dir,
            "--poll-interval-seconds",
            poll_interval_seconds,
        ]
    )
    run_dir = os.path.join(root_dir, run_name)
    persistent_run_dir = mirror_run_dir(run_dir)
    return run_dir, persistent_run_dir


def _status_mode(args: argparse.Namespace) -> int:
    if args.action == "status":
        # /tmp is ephemeral; pull the workspace mirror back before reading local checkpoint state.
        restore_from_persist(args.run_name, args.root_dir)
        run(["boltz-api", "--format", "json", "download-status", "--name", args.run_name, "--root-dir", args.root_dir])
        return 0
    if args.action == "retrieve":
        run(["boltz-api", RESOURCE_MAP[args.resource], "retrieve", "--id", args.job_id, "--format", "json"])
        return 0
    if args.action == "list-results":
        # Paginated per-item results straight from the API (no archive download needed).
        if args.resource not in PIPELINE_RESOURCES:
            raise SystemExit(
                "list-results is only available for design/screen runs "
                "(protein_design, protein_screen, sm_design, sm_screen). "
                "For sab/adme, use --action retrieve to read results."
            )
        cmd = ["boltz-api", RESOURCE_MAP[args.resource], "list-results", "--id", args.job_id, "--format", "jsonl"]
        if args.after_id:
            cmd += ["--after-id", args.after_id]
        # --max-items -1 auto-paginates the full result set; otherwise cap with --limit.
        cmd += ["--max-items", args.max_items] if args.max_items else ["--limit", args.limit]
        run(cmd)
        return 0
    if args.action == "resume":
        # Always persist fetched results to the workspace so they survive sandbox eviction.
        run_dir, persistent_run_dir = _download_and_mirror(
            args.job_id, args.run_name, args.root_dir, args.poll_interval_seconds
        )
        print(
            json.dumps(
                {
                    "job_id": args.job_id,
                    "run_name": args.run_name,
                    "run_dir": run_dir,
                    "output_root": args.root_dir,
                    "persistent_run_dir": persistent_run_dir,
                }
            )
        )
        return 0
    if args.action == "recover":
        # Recover a run after sandbox eviction without re-submitting (never billable):
        # resolve job_id from the workspace manifest or the Boltz API, then re-download + mirror.
        job_id = args.job_id
        resource_key = args.resource
        if not job_id:
            job_id, resolved_resource = find_job_by_run_name(args.run_name)
            resource_key = resource_key or resolved_resource
        if not job_id:
            raise SystemExit(
                f"Could not recover job for run-name '{args.run_name}'. "
                "No workspace manifest and no matching idempotency_key in the Boltz API. "
                "Pass --job-id explicitly, or use 'status --action list' to find it."
            )
        run_dir, persistent_run_dir = _download_and_mirror(
            job_id, args.run_name, args.root_dir, args.poll_interval_seconds
        )
        # Refresh the manifest so future recoveries are a single workspace read.
        write_manifest(
            args.run_name,
            run_dir,
            {"run_name": args.run_name, "job_id": job_id, "resource": resource_key, "idempotency_key": args.run_name},
        )
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "resource": resource_key,
                    "run_name": args.run_name,
                    "run_dir": run_dir,
                    "output_root": args.root_dir,
                    "persistent_run_dir": persistent_run_dir,
                }
            )
        )
        return 0
    if args.action == "stop":
        if args.resource not in PIPELINE_RESOURCES:
            raise SystemExit(
                "stop is only available for design/screen runs "
                "(protein_design, protein_screen, sm_design, sm_screen). "
                "sab/adme predictions cannot be stopped; they finish on their own."
            )
        run(["boltz-api", RESOURCE_MAP[args.resource], "stop", "--id", args.job_id, "--format", "json"])
        return 0
    if args.action == "delete-data":
        # Destructive: permanently deletes input/output/result data (irreversible).
        if not args.confirm_delete:
            raise SystemExit(
                "Refusing to delete data without --confirm-delete. "
                "delete-data permanently removes the run's input/output/result data (irreversible); "
                "only the run record is retained with a data_deleted_at timestamp."
            )
        run(["boltz-api", RESOURCE_MAP[args.resource], "delete-data", "--id", args.job_id, "--format", "json"])
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
    status.add_argument(
        "--action",
        choices=("status", "retrieve", "list-results", "resume", "recover", "stop", "delete-data", "list"),
        required=True,
    )
    status.add_argument("--run-name")
    status.add_argument("--job-id")
    status.add_argument("--resource", choices=sorted(RESOURCE_MAP.keys()))
    status.add_argument("--root-dir", default=ROOT)
    status.add_argument("--poll-interval-seconds", default="30")
    status.add_argument("--limit", default="20")
    status.add_argument("--after-id", help="Cursor for list-results pagination")
    status.add_argument("--max-items", help="list-results cap; use -1 for the full result set")
    status.add_argument("--confirm-delete", action="store_true", help="Required to run delete-data (irreversible)")
    return parser


def main() -> int:
    ensure_boltz_cli()
    args = build_parser().parse_args()
    if args.mode == "status":
        if args.action == "status" and not args.run_name:
            raise SystemExit("--run-name is required for status action")
        if args.action in {"retrieve", "stop", "list-results", "delete-data"} and (not args.job_id or not args.resource):
            raise SystemExit(f"--job-id and --resource are required for {args.action} action")
        if args.action == "resume" and (not args.job_id or not args.run_name):
            raise SystemExit("--job-id and --run-name are required for resume action")
        if args.action == "recover" and not args.run_name:
            raise SystemExit("--run-name is required for recover action (add --job-id to skip API lookup)")
        return _status_mode(args)
    return _run_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
