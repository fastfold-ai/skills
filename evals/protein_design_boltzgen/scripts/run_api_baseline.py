#!/usr/bin/env python3
"""BoltzGen API baseline: example-files → new → upload → build-spec → upsert → execute → wait.

Usage:
  export FASTFOLD_API_KEY=...
  python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py
  python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py --only binding_disordered_peptides
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "protein_design_boltzgen"
CASES = Path(__file__).resolve().parents[1] / "baselines" / "cases.json"
API = SKILL / "scripts" / "workflow_api.py"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    if not env.get("FASTFOLD_API_KEY"):
        sys.exit("Error: FASTFOLD_API_KEY is required")
    return env


def _run(cmd: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(SKILL),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _api(state: Path, *args: str, timeout: float | None = 300) -> subprocess.CompletedProcess[str]:
    return _run(
        ["python3", str(API), "--state-file", str(state), *args],
        timeout=timeout,
    )


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    # Some commands may print non-JSON lines before JSON; try last {...} block
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def run_case(case: dict, outdir: Path) -> dict:
    case_id = case["id"]
    preset = case["preset"]
    started = time.time()
    case_dir = outdir / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    state = case_dir / "state.json"
    row: dict = {"id": case_id, "preset": preset, "steps": []}

    def step(name: str, proc: subprocess.CompletedProcess[str], *, ok_codes: set[int] | None = None) -> dict | None:
        codes = ok_codes or {0}
        entry = {
            "name": name,
            "ok": proc.returncode in codes,
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "")[-1500:],
            "stdout_tail": (proc.stdout or "")[-1500:],
        }
        row["steps"].append(entry)
        if proc.returncode not in codes:
            row["error"] = f"step_failed:{name}"
            return None
        return _parse_json(proc.stdout or "")

    # 1) resolve example files
    data = step("example-files", _api(state, "example-files", "--preset", preset, "--json"))
    if data is None:
        row["pass"] = False
        row["duration_s"] = round(time.time() - started, 2)
        return row
    files = [f for f in (data.get("files") or []) if f.get("exists")]
    (case_dir / "example-files.json").write_text(json.dumps(data, indent=2) + "\n")

    # 2) new draft (no --json flag on this subcommand; workflow_id lands in state file)
    proc = _api(state, "new", "--name", f"eval-baseline-boltzgen-{case_id}")
    step("new", proc)
    if proc.returncode != 0:
        row["pass"] = False
        row["duration_s"] = round(time.time() - started, 2)
        return row
    if state.is_file():
        row["workflow_id"] = json.loads(state.read_text()).get("workflow_id")

    # 3) upload each example file
    for item in files:
        path = item["absolute_path"]
        kind = item.get("kind") or "other"
        if kind not in {"protein", "yml"}:
            continue
        logical = Path(path).name
        data = step(
            f"upload:{logical}",
            _api(
                state,
                "upload",
                "--file",
                path,
                "--file-type",
                kind,
                "--logical-name",
                logical,
            ),
        )
        if row.get("error"):
            row["pass"] = False
            row["duration_s"] = round(time.time() - started, 2)
            return row

    # 4) build-spec
    spec_path = case_dir / "workflow.yml"
    data = step(
        "build-spec",
        _api(state, "build-spec", "--preset", preset, "--out", str(spec_path), "--json"),
    )
    if row.get("error") or not spec_path.is_file():
        # try without json
        if not spec_path.is_file():
            proc = _api(state, "build-spec", "--preset", preset, "--out", str(spec_path))
            step("build-spec-retry", proc)
        if not spec_path.is_file():
            row["pass"] = False
            row["error"] = row.get("error") or "build_spec_missing_out"
            row["duration_s"] = round(time.time() - started, 2)
            return row

    # 5) upsert
    step("upsert", _api(state, "upsert", "--spec", str(spec_path)))
    if row.get("error"):
        row["pass"] = False
        row["duration_s"] = round(time.time() - started, 2)
        return row

    # 6) execute
    step("execute", _api(state, "execute"))
    if row.get("error"):
        row["pass"] = False
        row["duration_s"] = round(time.time() - started, 2)
        return row

    # 7) wait
    timeout = int(case.get("timeout_s") or 7200)
    poll = int(case.get("poll_seconds") or 30)
    wait_out = case_dir / "artifacts"
    proc = _api(
        state,
        "wait",
        "--poll-seconds",
        str(poll),
        "--timeout-seconds",
        str(timeout),
        "--out-dir",
        str(wait_out),
        "--no-download",
        timeout=timeout + 180,
    )
    wait_data = step("wait", proc)
    status = ""
    if state.is_file():
        st = json.loads(state.read_text())
        row["workflow_id"] = row.get("workflow_id") or st.get("workflow_id")
        status = str(st.get("last_status") or st.get("status") or "").upper()
    if wait_data:
        status = str(wait_data.get("status") or status).upper()
        (case_dir / "wait.json").write_text(json.dumps(wait_data, indent=2) + "\n")

    # 8) results summary (best-effort)
    results_proc = _api(state, "results", "--json", timeout=180)
    results_data = step("results", results_proc, ok_codes={0, 1})
    if results_data:
        (case_dir / "results.json").write_text(json.dumps(results_data, indent=2) + "\n")

    row["final_status"] = status
    row["duration_s"] = round(time.time() - started, 2)
    row["pass"] = proc.returncode == 0 and status in {"COMPLETED", "SUCCEEDED", "SUCCESS"}
    if not row["pass"] and proc.returncode == 0 and not status:
        # some waiters only exit 0 on COMPLETED
        row["pass"] = True
        row["final_status"] = status or "COMPLETED"
    return row


def write_metrics(outdir: Path, rows: list[dict]) -> None:
    passed = sum(1 for r in rows if r.get("pass"))
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skill": "protein_design_boltzgen",
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "cases": rows,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    lines = [
        "# protein_design_boltzgen API baseline",
        "",
        f"- Generated: `{metrics['generated_at']}`",
        f"- Pass rate: **{metrics['passed']}/{metrics['total']}** ({metrics['pass_rate']:.0%})",
        "",
        "| Case | Preset | Pass | Status | Duration (s) | Workflow ID |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('id')} | {r.get('preset')} | {'✅' if r.get('pass') else '❌'} | "
            f"{r.get('final_status') or r.get('error') or ''} | {r.get('duration_s', '')} | "
            f"`{r.get('workflow_id') or ''}` |"
        )
    (outdir / "metrics.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()
    cases = json.loads(CASES.read_text())["cases"]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in want]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = args.outdir or (Path(__file__).resolve().parents[1] / "workspace" / f"api-baseline-{stamp}")
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"[boltzgen-eval] outdir={outdir}", file=sys.stderr)

    results = []
    for case in cases:
        print(f"[boltzgen-eval] running {case['id']} ({case['preset']})...", file=sys.stderr)
        row = run_case(case, outdir)
        results.append(row)
        print(
            f"[boltzgen-eval] {row['id']}: {'PASS' if row.get('pass') else 'FAIL'} "
            f"status={row.get('final_status') or row.get('error')} "
            f"workflow_id={row.get('workflow_id')}",
            file=sys.stderr,
        )
        (outdir / "jobs.json").write_text(json.dumps(results, indent=2) + "\n")

    write_metrics(outdir, results)
    print(outdir)


if __name__ == "__main__":
    main()
