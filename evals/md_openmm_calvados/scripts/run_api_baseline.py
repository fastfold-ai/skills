#!/usr/bin/env python3
"""CALVADOS/OpenMM API baseline via skill scripts.

Usage:
  export FASTFOLD_API_KEY=...
  python3 evals/md_openmm_calvados/scripts/run_api_baseline.py
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
SKILL = ROOT / "skills" / "md_openmm_calvados"
CASES = Path(__file__).resolve().parents[1] / "baselines" / "cases.json"
sys.path.insert(0, str(ROOT / "evals" / "_shared"))
from fold_job import fold_job_id_for_case  # noqa: E402


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


def _parse_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict | None:
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def submit_case(case: dict, outdir: Path) -> dict:
    case_id = case["id"]
    started = time.time()
    kind = case["kind"]
    sim = str(case.get("sim_length_ns", 0.05))
    step = str(case.get("step_size_ns", 0.01))
    name = f"eval-baseline-calvados-{case_id}"

    if kind == "fold_job":
        job_id = fold_job_id_for_case(case["fold_case_id"])
        cmd = [
            "python3",
            "scripts/submit_from_fold_job.py",
            job_id,
            "--name",
            name,
            "--simulation-name",
            name,
            "--sim-length-ns",
            sim,
            "--step-size-ns",
            step,
            "--json",
        ]
        meta = {"fold_job_id": job_id}
    elif kind == "uniprot_manual":
        fixtures = outdir / "fixtures" / case_id
        fixtures.mkdir(parents=True, exist_ok=True)
        fetch = _run(
            [
                "python3",
                "scripts/fetch_uniprot.py",
                case["uniprot_id"],
                "--out-dir",
                str(fixtures),
                "--json",
            ],
            timeout=180,
        )
        if fetch.returncode != 0:
            return {
                "id": case_id,
                "kind": kind,
                "submit_ok": False,
                "error": "fetch_uniprot_failed",
                "submit_stderr": (fetch.stderr or "")[-2000:],
            }
        fetch_data = _parse_json_stdout(fetch) or {}
        pdb = fetch_data.get("pdb_path") or str(fixtures / f"AF-{case['uniprot_id']}.pdb")
        pae = fetch_data.get("pae_path") or str(fixtures / f"AF-{case['uniprot_id']}.json")
        # fetch_uniprot may print paths differently — resolve from fixtures
        pdbs = list(fixtures.glob("*.pdb"))
        paes = list(fixtures.glob("*.json"))
        if pdbs:
            pdb = str(pdbs[0])
        if paes:
            pae = str(paes[0])
        cmd = [
            "python3",
            "scripts/submit_manual_af_pae.py",
            "--pdb",
            pdb,
            "--pae",
            pae,
            "--name",
            name,
            "--simulation-name",
            name,
            "--sim-length-ns",
            sim,
            "--step-size-ns",
            step,
            "--json",
        ]
        meta = {"uniprot_id": case["uniprot_id"], "pdb": pdb, "pae": pae}
    else:
        return {"id": case_id, "submit_ok": False, "error": f"unknown_kind:{kind}"}

    proc = _run(cmd, timeout=180)
    row = {
        "id": case_id,
        "kind": kind,
        "submit_ok": proc.returncode == 0,
        "submit_stderr": (proc.stderr or "")[-2000:],
        "submit_duration_s": round(time.time() - started, 2),
        **meta,
    }
    data = _parse_json_stdout(proc)
    if proc.returncode != 0 or not data:
        row["error"] = row.get("error") or "submit_failed"
        row["submit_stdout"] = (proc.stdout or "")[-2000:]
        return row
    row["workflow_id"] = data.get("workflow_id") or data.get("workflowId")
    row["submit_response"] = data
    return row


def wait_case(case: dict, job: dict, outdir: Path) -> dict:
    wid = job.get("workflow_id")
    if not wid:
        return {**job, "pass": False, "error": job.get("error") or "no_workflow_id"}
    timeout = float(case.get("timeout_s") or 2400)
    metrics_timeout = float(case.get("metrics_timeout_s") or 900)
    started = time.time()
    proc = _run(
        [
            "python3",
            "scripts/wait_for_workflow.py",
            wid,
            "--timeout",
            str(timeout),
            "--metrics-timeout",
            str(metrics_timeout),
            "--json",
        ],
        timeout=timeout + metrics_timeout + 120,
    )
    wait_s = round(time.time() - started, 2)
    data = _parse_json_stdout(proc) or {}
    (outdir / "results").mkdir(parents=True, exist_ok=True)
    if data:
        (outdir / "results" / f"{case['id']}.json").write_text(json.dumps(data, indent=2) + "\n")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    status = str(data.get("status") or "").upper()
    artifacts = int(summary.get("artifact_count") or 0)
    metrics_ready = bool(data.get("metrics_ready") or summary.get("has_metrics"))
    # wait_for_workflow exits 3 when COMPLETED but metrics never settle; artifacts alone
    # are enough for a smoke pass (some UniProt/manual runs omit metrics blobs).
    ok = status == "COMPLETED" and (
        (proc.returncode == 0 and bool(data.get("success")) and (metrics_ready or artifacts > 0))
        or (proc.returncode == 3 and artifacts > 0)
    )
    return {
        **job,
        "wait_ok": proc.returncode in (0, 3) and status == "COMPLETED",
        "wait_duration_s": wait_s,
        "wait_stderr": (proc.stderr or "")[-2000:],
        "final_status": status,
        "metrics_ready": metrics_ready,
        "artifact_count": artifacts,
        "pass": ok,
        "notes": (
            "COMPLETED with artifacts; metrics settle timed out"
            if proc.returncode == 3 and ok
            else None
        ),
        "wait_response": data,
    }


def write_metrics(outdir: Path, rows: list[dict]) -> None:
    passed = sum(1 for r in rows if r.get("pass"))
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skill": "md_openmm_calvados",
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "cases": rows,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    lines = [
        "# md_openmm_calvados API baseline",
        "",
        f"- Generated: `{metrics['generated_at']}`",
        f"- Pass rate: **{metrics['passed']}/{metrics['total']}** ({metrics['pass_rate']:.0%})",
        "",
        "| Case | Kind | Pass | Status | Metrics | Wait (s) | Workflow ID |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {id} | {kind} | {ok} | {st} | {m} | {w} | `{wid}` |".format(
                id=r.get("id"),
                kind=r.get("kind"),
                ok="✅" if r.get("pass") else "❌",
                st=r.get("final_status") or r.get("error") or "",
                m="Y" if r.get("metrics_ready") else "N",
                w=r.get("wait_duration_s", ""),
                wid=r.get("workflow_id") or "",
            )
        )
    (outdir / "metrics.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()
    catalog = json.loads(CASES.read_text())
    cases = catalog["cases"]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in want]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = args.outdir or (Path(__file__).resolve().parents[1] / "workspace" / f"api-baseline-{stamp}")
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"[calvados-eval] outdir={outdir}", file=sys.stderr)

    jobs = []
    for case in cases:
        row = submit_case(case, outdir)
        jobs.append(row)
        print(
            f"[calvados-eval] submit {row['id']}: {'ok' if row.get('submit_ok') else 'FAIL'} "
            f"workflow_id={row.get('workflow_id')}",
            file=sys.stderr,
        )
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=2) + "\n")

    results = []
    by_id = {c["id"]: c for c in cases}
    for job in jobs:
        results.append(wait_case(by_id[job["id"]], job, outdir))
        print(
            f"[calvados-eval] wait {results[-1]['id']}: "
            f"{'PASS' if results[-1].get('pass') else 'FAIL'} "
            f"status={results[-1].get('final_status')}",
            file=sys.stderr,
        )
    write_metrics(outdir, results)
    print(outdir)
    failed = sum(1 for r in results if not r.get("pass"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
