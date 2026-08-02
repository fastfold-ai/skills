#!/usr/bin/env python3
"""Submit + wait one fold job per baseline case using fold skill scripts.

Usage:
  export FASTFOLD_API_KEY=...
  python3 evals/fold/scripts/run_api_baseline.py
  python3 evals/fold/scripts/run_api_baseline.py --only boltz-2,nesso,esmfold2-fast
  python3 evals/fold/scripts/run_api_baseline.py --submit-only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]  # skills repo root
FOLD = ROOT / "skills" / "fold"
MODELS = Path(__file__).resolve().parents[1] / "baselines" / "models.json"
CREATE = FOLD / "scripts" / "create_job.py"
WAIT = FOLD / "scripts" / "wait_for_completion.py"
WAIT_NESSO = FOLD / "scripts" / "wait_for_nesso_linked.py"
FETCH = FOLD / "scripts" / "fetch_results.py"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    if not env.get("FASTFOLD_API_KEY"):
        sys.exit("Error: FASTFOLD_API_KEY is required")
    return env


def _run(cmd: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(FOLD),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _payload_path(outdir: Path, case_id: str, payload: dict) -> Path:
    path = outdir / "payloads" / f"{case_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def submit_case(case: dict, outdir: Path) -> dict:
    case_id = case["id"]
    started = time.time()
    path = _payload_path(outdir, case_id, case["payload"])
    proc = _run(["python3", str(CREATE), "--payload", str(path), "--json"], timeout=120)
    row = {
        "id": case_id,
        "modelName": case.get("modelName"),
        "kind": case.get("kind"),
        "submit_ok": proc.returncode == 0,
        "submit_stderr": (proc.stderr or "")[-2000:],
        "submit_duration_s": round(time.time() - started, 2),
    }
    if proc.returncode != 0:
        row["error"] = "submit_failed"
        row["submit_stdout"] = (proc.stdout or "")[-2000:]
        return row
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        row["error"] = "submit_invalid_json"
        row["submit_stdout"] = (proc.stdout or "")[-2000:]
        return row
    row["jobId"] = data.get("jobId")
    row["jobStatus"] = data.get("jobStatus")
    row["submit_response"] = data
    return row


def _has_cif(results: dict) -> bool:
    payload = results.get("predictionPayload")
    if isinstance(payload, dict) and payload.get("cif_url"):
        return True
    for seq in results.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        p = seq.get("predictionPayload")
        if isinstance(p, dict) and p.get("cif_url"):
            return True
    return False


def _has_affinity(results: dict) -> bool:
    payload = results.get("predictionPayload")
    if isinstance(payload, dict) and payload.get("affinity_result_raw_json"):
        return True
    for seq in results.get("sequences") or []:
        if not isinstance(seq, dict):
            continue
        p = seq.get("predictionPayload")
        if isinstance(p, dict) and p.get("affinity_result_raw_json"):
            return True
    constraints = results.get("constraints") if isinstance(results.get("constraints"), dict) else {}
    webhooks = constraints.get("webhooks") if isinstance(constraints.get("webhooks"), dict) else {}
    nesso = webhooks.get("nesso") if isinstance(webhooks.get("nesso"), dict) else {}
    if nesso.get("affinity_result_raw_json"):
        return True
    return False


def wait_case(case: dict, job: dict, outdir: Path) -> dict:
    case_id = case["id"]
    job_id = job.get("jobId")
    if not job_id:
        return {**job, "pass": False, "error": job.get("error") or "no_job_id"}

    timeout = float(case.get("timeout_s") or os.environ.get("FOLD_EVAL_TIMEOUT") or 1800)
    started = time.time()
    results_dir = outdir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if case.get("waiter") == "nesso_linked":
        nesso_timeout = float(case.get("nesso_timeout_s") or timeout)
        proc = _run(
            [
                "python3",
                str(WAIT_NESSO),
                job_id,
                "--json",
                "--timeout",
                str(timeout),
                "--nesso-timeout",
                str(nesso_timeout),
            ],
            timeout=timeout + nesso_timeout + 120,
        )
    else:
        proc = _run(
            ["python3", str(WAIT), job_id, "--json", "--timeout", str(timeout)],
            timeout=timeout + 120,
        )

    wait_s = round(time.time() - started, 2)
    out = {
        **job,
        "wait_duration_s": wait_s,
        "wait_ok": proc.returncode == 0,
        "wait_stderr": (proc.stderr or "")[-2000:],
    }

    results = None
    if proc.returncode == 0 and (proc.stdout or "").strip():
        try:
            results = json.loads(proc.stdout)
        except json.JSONDecodeError:
            # wait_for_nesso_linked returns a wrapper; also fetch full results
            pass

    if results is None or case.get("waiter") == "nesso_linked":
        fetch = _run(["python3", str(FETCH), job_id, "--json"], timeout=60)
        if fetch.returncode == 0:
            try:
                results = json.loads(fetch.stdout)
            except json.JSONDecodeError:
                results = None
        out["fetch_ok"] = fetch.returncode == 0
        if fetch.returncode != 0:
            out["fetch_stderr"] = (fetch.stderr or "")[-1000:]

    if results is not None:
        (results_dir / f"{case_id}.json").write_text(json.dumps(results, indent=2) + "\n")
        status = ""
        job_blob = results.get("job") if isinstance(results.get("job"), dict) else {}
        status = str(results.get("jobStatus") or job_blob.get("status") or job_blob.get("jobStatus") or "").upper()
        out["final_status"] = status
        expect_structure = case.get("expect_structure", case.get("kind") != "affinity")
        expect_affinity = case.get("expect_affinity", case.get("kind") == "affinity")
        has_cif = _has_cif(results)
        has_aff = _has_affinity(results)
        out["has_cif"] = has_cif
        out["has_affinity"] = has_aff
        checks = []
        if expect_structure:
            checks.append(status == "COMPLETED" and has_cif)
        if expect_affinity:
            checks.append(has_aff or (case.get("waiter") == "nesso_linked" and proc.returncode == 0))
        if case.get("kind") == "affinity":
            # Native Nesso: completed + affinity; CIF must be absent (or ignored)
            checks = [status == "COMPLETED" and has_aff and not has_cif]
            out["affinity_only_ok"] = has_aff and not has_cif
        out["pass"] = all(checks) if checks else status == "COMPLETED"
        if case.get("kind") == "affinity" and has_cif:
            out["notes"] = "Unexpected CIF on native Nesso job"
    else:
        out["pass"] = False
        out["error"] = out.get("error") or "no_results"
        out["wait_stdout"] = (proc.stdout or "")[-2000:]

    return out


def write_metrics(outdir: Path, rows: list[dict]) -> None:
    passed = sum(1 for r in rows if r.get("pass"))
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "cases": rows,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    lines = [
        "# Fold API baseline metrics",
        "",
        f"- Generated: `{metrics['generated_at']}`",
        f"- Pass rate: **{metrics['passed']}/{metrics['total']}** ({metrics['pass_rate']:.0%})",
        "",
        "| Case | Model | Kind | Pass | Status | CIF | Affinity | Wait (s) | Job ID |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {id} | {model} | {kind} | {ok} | {status} | {cif} | {aff} | {wait} | `{jid}` |".format(
                id=r.get("id"),
                model=r.get("modelName"),
                kind=r.get("kind"),
                ok="✅" if r.get("pass") else "❌",
                status=r.get("final_status") or r.get("jobStatus") or r.get("error") or "",
                cif="Y" if r.get("has_cif") else "N",
                aff="Y" if r.get("has_affinity") else "N",
                wait=r.get("wait_duration_s", ""),
                jid=r.get("jobId") or "",
            )
        )
    (outdir / "metrics.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run fold API baseline smoke suite")
    ap.add_argument("--models", type=Path, default=MODELS)
    ap.add_argument("--only", type=str, default="", help="Comma-separated case ids")
    ap.add_argument("--submit-only", action="store_true")
    ap.add_argument("--max-workers", type=int, default=6)
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()

    catalog = json.loads(args.models.read_text())
    cases = catalog["cases"]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in want]
        missing = want - {c["id"] for c in cases}
        if missing:
            sys.exit(f"Unknown case ids: {sorted(missing)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = args.outdir or (Path(__file__).resolve().parents[1] / "workspace" / f"api-baseline-{stamp}")
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"[fold-eval] outdir={outdir}", file=sys.stderr)
    print(f"[fold-eval] submitting {len(cases)} cases...", file=sys.stderr)

    jobs: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futs = {pool.submit(submit_case, c, outdir): c for c in cases}
        for fut in concurrent.futures.as_completed(futs):
            row = fut.result()
            jobs.append(row)
            print(
                f"[fold-eval] submit {row['id']}: {'ok' if row.get('submit_ok') else 'FAIL'} "
                f"jobId={row.get('jobId')}",
                file=sys.stderr,
            )

    jobs.sort(key=lambda r: r["id"])
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=2) + "\n")

    if args.submit_only:
        write_metrics(outdir, [{**j, "pass": bool(j.get("submit_ok"))} for j in jobs])
        print(outdir)
        return

    print(f"[fold-eval] waiting for {sum(1 for j in jobs if j.get('jobId'))} jobs...", file=sys.stderr)
    case_by_id = {c["id"]: c for c in cases}
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futs = {
            pool.submit(wait_case, case_by_id[j["id"]], j, outdir): j["id"]
            for j in jobs
            if j.get("jobId")
        }
        for j in jobs:
            if not j.get("jobId"):
                results.append({**j, "pass": False})
        for fut in concurrent.futures.as_completed(futs):
            row = fut.result()
            results.append(row)
            print(
                f"[fold-eval] wait {row['id']}: {'PASS' if row.get('pass') else 'FAIL'} "
                f"status={row.get('final_status')} wait={row.get('wait_duration_s')}s",
                file=sys.stderr,
            )

    results.sort(key=lambda r: r["id"])
    write_metrics(outdir, results)
    print(f"[fold-eval] metrics -> {outdir / 'metrics.md'}", file=sys.stderr)
    print(outdir)


if __name__ == "__main__":
    main()
