#!/usr/bin/env python3
"""OpenMMDL API baseline via skill scripts.

Usage:
  export FASTFOLD_API_KEY=...
  python3 evals/md_openmmdl/scripts/run_api_baseline.py
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
SKILL = ROOT / "skills" / "md_openmmdl"
FOLD = ROOT / "skills" / "fold"
CASES = Path(__file__).resolve().parents[1] / "baselines" / "cases.json"
sys.path.insert(0, str(ROOT / "evals" / "_shared"))
from fold_job import fold_job_id_for_case  # noqa: E402


def _env() -> dict[str, str]:
    env = os.environ.copy()
    if not env.get("FASTFOLD_API_KEY"):
        sys.exit("Error: FASTFOLD_API_KEY is required")
    return env


def _run(cmd: list[str], *, cwd: Path, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_json(proc: subprocess.CompletedProcess[str]) -> dict | None:
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _download_fold_cif(job_id: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    proc = _run(
        ["python3", "scripts/download_cif.py", job_id, "--dir", str(dest_dir)],
        cwd=FOLD,
        timeout=180,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"Error: download_cif failed for {job_id}: {(proc.stderr or proc.stdout)[-1000:]}"
        )
    cifs = sorted(dest_dir.rglob("*.cif"))
    if not cifs:
        # some models emit pdb
        pdbs = sorted(dest_dir.rglob("*.pdb"))
        if pdbs:
            return pdbs[0]
        raise SystemExit(f"Error: no CIF/PDB downloaded for fold job {job_id} into {dest_dir}")
    return cifs[0]


def submit_case(case: dict, outdir: Path) -> dict:
    case_id = case["id"]
    started = time.time()
    job_id = fold_job_id_for_case(case["fold_case_id"])
    fixtures = outdir / "fixtures" / case_id
    try:
        topology = _download_fold_cif(job_id, fixtures)
    except SystemExit as exc:
        return {
            "id": case_id,
            "kind": case.get("kind"),
            "submit_ok": False,
            "error": str(exc),
            "fold_job_id": job_id,
        }

    name = f"eval-baseline-openmmdl-{case_id}"
    cmd = [
        "python3",
        "scripts/submit_manual_topology_ligands.py",
        "--topology",
        str(topology),
        "--name",
        name,
        "--simulation-name",
        name,
        "--sim-length-ns",
        str(case.get("sim_length_ns", 0.1)),
        "--json",
    ]
    if case.get("run_analysis") is False:
        cmd.append("--no-run-analysis")
    elif case.get("run_analysis") is True:
        cmd.append("--run-analysis")

    proc = _run(cmd, cwd=SKILL, timeout=300)
    row = {
        "id": case_id,
        "kind": case.get("kind"),
        "fold_job_id": job_id,
        "topology": str(topology),
        "submit_ok": proc.returncode == 0,
        "submit_stderr": (proc.stderr or "")[-2000:],
        "submit_duration_s": round(time.time() - started, 2),
    }
    data = _parse_json(proc)
    if proc.returncode != 0 or not data:
        row["error"] = "submit_failed"
        row["submit_stdout"] = (proc.stdout or "")[-2000:]
        return row
    row["workflow_id"] = data.get("workflow_id") or data.get("workflowId")
    row["submit_response"] = data
    return row


def wait_case(case: dict, job: dict, outdir: Path) -> dict:
    wid = job.get("workflow_id")
    if not wid:
        return {**job, "pass": False, "error": job.get("error") or "no_workflow_id"}
    timeout = float(case.get("timeout_s") or 3600)
    results_timeout = float(case.get("results_timeout_s") or 1200)
    started = time.time()
    proc = _run(
        [
            "python3",
            "scripts/wait_for_workflow.py",
            wid,
            "--timeout",
            str(timeout),
            "--results-timeout",
            str(results_timeout),
            "--json",
        ],
        cwd=SKILL,
        timeout=timeout + results_timeout + 120,
    )
    data = _parse_json(proc) or {}
    (outdir / "results").mkdir(parents=True, exist_ok=True)
    if data:
        (outdir / "results" / f"{case['id']}.json").write_text(json.dumps(data, indent=2) + "\n")
    status = str(data.get("status") or data.get("workflow_status") or "").upper()
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    ok = (
        proc.returncode == 0
        and status == "COMPLETED"
        and bool(data.get("success"))
        and bool(data.get("results_ready") or summary.get("artifact_count") or summary.get("has_metrics"))
    )
    return {
        **job,
        "wait_ok": proc.returncode == 0,
        "wait_duration_s": round(time.time() - started, 2),
        "wait_stderr": (proc.stderr or "")[-2000:],
        "final_status": status,
        "results_ready": bool(data.get("results_ready")),
        "artifact_count": summary.get("artifact_count") if isinstance(summary, dict) else None,
        "pass": ok,
        "wait_response": data,
    }


def write_metrics(outdir: Path, rows: list[dict]) -> None:
    passed = sum(1 for r in rows if r.get("pass"))
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skill": "md_openmmdl",
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "cases": rows,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    lines = [
        "# md_openmmdl API baseline",
        "",
        f"- Generated: `{metrics['generated_at']}`",
        f"- Pass rate: **{metrics['passed']}/{metrics['total']}** ({metrics['pass_rate']:.0%})",
        "",
        "| Case | Pass | Status | Wait (s) | Workflow ID |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('id')} | {'✅' if r.get('pass') else '❌'} | "
            f"{r.get('final_status') or r.get('error') or ''} | {r.get('wait_duration_s', '')} | "
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
    print(f"[openmmdl-eval] outdir={outdir}", file=sys.stderr)

    jobs = [submit_case(c, outdir) for c in cases]
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=2) + "\n")
    for j in jobs:
        print(
            f"[openmmdl-eval] submit {j['id']}: {'ok' if j.get('submit_ok') else 'FAIL'} "
            f"workflow_id={j.get('workflow_id')}",
            file=sys.stderr,
        )

    by_id = {c["id"]: c for c in cases}
    results = [wait_case(by_id[j["id"]], j, outdir) for j in jobs]
    for r in results:
        print(
            f"[openmmdl-eval] wait {r['id']}: {'PASS' if r.get('pass') else 'FAIL'} "
            f"status={r.get('final_status')}",
            file=sys.stderr,
        )
    write_metrics(outdir, results)
    print(outdir)


if __name__ == "__main__":
    main()
