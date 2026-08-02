#!/usr/bin/env python3
"""Helpers to reuse completed fold baseline jobs as MD inputs."""

from __future__ import annotations

import json
from pathlib import Path


EVALS = Path(__file__).resolve().parents[1]


def latest_fold_baseline_dir() -> Path | None:
    root = EVALS / "fold" / "workspace"
    if not root.is_dir():
        return None
    dirs = sorted(
        (p for p in root.iterdir() if p.is_dir() and p.name.startswith("api-baseline-")),
        key=lambda p: p.name,
        reverse=True,
    )
    for d in dirs:
        if (d / "metrics.json").is_file():
            return d
    return None


def fold_job_id_for_case(case_id: str) -> str:
    base = latest_fold_baseline_dir()
    if base is None:
        raise SystemExit(
            "Error: no fold api-baseline metrics found under evals/fold/workspace/. "
            "Run evals/fold/scripts/run_api_baseline.py first."
        )
    metrics = json.loads((base / "metrics.json").read_text())
    for row in metrics.get("cases") or []:
        if row.get("id") == case_id and row.get("pass") and row.get("jobId"):
            return str(row["jobId"])
    raise SystemExit(
        f"Error: fold baseline case '{case_id}' not found/passed in {base / 'metrics.json'}"
    )
