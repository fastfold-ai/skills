#!/usr/bin/env python3
"""Build skill-creator-compatible benchmark.json from graded instruction runs."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def _stat(vals: list[float]) -> dict:
    if not vals:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}
    mean = statistics.mean(vals)
    stddev = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    return {
        "mean": round(mean, 3),
        "stddev": round(stddev, 3),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--skill-name", default="fold")
    args = ap.parse_args()

    runs = []
    for eval_dir in sorted(p for p in args.workspace.iterdir() if p.is_dir()):
        meta_path = eval_dir / "eval_metadata.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        eval_id = meta.get("eval_id")
        eval_name = meta.get("eval_name") or eval_dir.name
        for config in ("with_skill", "without_skill"):
            run_dir = eval_dir / config
            grading_path = run_dir / "grading.json"
            if not grading_path.exists():
                continue
            grading = json.loads(grading_path.read_text())
            summary = grading.get("summary") or {}
            timing = {}
            if (run_dir / "timing.json").exists():
                timing = json.loads((run_dir / "timing.json").read_text())
            runs.append(
                {
                    "eval_id": eval_id if eval_id is not None else len(runs) + 1,
                    "eval_name": eval_name,
                    "configuration": config,
                    "run_number": 1,
                    "result": {
                        "pass_rate": summary.get("pass_rate", 0.0),
                        "passed": summary.get("passed", 0),
                        "failed": summary.get("failed", 0),
                        "total": summary.get("total", 0),
                        "time_seconds": timing.get("total_duration_seconds")
                        or timing.get("executor_duration_seconds")
                        or 0.0,
                        "tokens": timing.get("total_tokens") or 0,
                        "tool_calls": 0,
                        "errors": 0,
                    },
                    "expectations": grading.get("expectations") or [],
                    "notes": [],
                }
            )

    def rates(config: str) -> list[float]:
        return [r["result"]["pass_rate"] for r in runs if r["configuration"] == config]

    def times(config: str) -> list[float]:
        return [r["result"]["time_seconds"] for r in runs if r["configuration"] == config]

    def tokens(config: str) -> list[float]:
        return [float(r["result"]["tokens"]) for r in runs if r["configuration"] == config]

    ws = _stat(rates("with_skill"))
    wos = _stat(rates("without_skill"))
    delta_pr = ws["mean"] - wos["mean"]
    delta_t = _stat(times("with_skill"))["mean"] - _stat(times("without_skill"))["mean"]
    delta_tok = _stat(tokens("with_skill"))["mean"] - _stat(tokens("without_skill"))["mean"]

    benchmark = {
        "metadata": {
            "skill_name": args.skill_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evals_run": sorted({r["eval_name"] for r in runs}),
            "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": {
            "with_skill": {
                "pass_rate": ws,
                "time_seconds": _stat(times("with_skill")),
                "tokens": _stat(tokens("with_skill")),
            },
            "without_skill": {
                "pass_rate": wos,
                "time_seconds": _stat(times("without_skill")),
                "tokens": _stat(tokens("without_skill")),
            },
            "delta": {
                "pass_rate": f"{delta_pr:+.2f}",
                "time_seconds": f"{delta_t:+.1f}",
                "tokens": f"{delta_tok:+.0f}",
            },
        },
        "notes": [
            "Instruction evals grade payload construction / skill following, not live GPU accuracy.",
            "API baseline metrics live under workspace/api-baseline-*/metrics.md.",
        ],
    }
    out = args.workspace / "benchmark.json"
    out.write_text(json.dumps(benchmark, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
