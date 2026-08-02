#!/usr/bin/env python3
"""Grade fold instruction eval outputs against expectations in evals.json.

Looks for job_payload.json / notes.md / wait_command.sh under each run's outputs/.
Writes grading.json next to each run and a summary.md at workspace root.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EVALS = Path(__file__).resolve().parents[3] / "skills" / "fold" / "evals" / "evals.json"


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def find_payload(outputs: Path) -> dict | None:
    for name in ("job_payload.json", "payload.json", "job.json"):
        data = load_json(outputs / name)
        if isinstance(data, dict):
            return data
    # any json with sequences+params
    for path in sorted(outputs.glob("*.json")):
        data = load_json(path)
        if isinstance(data, dict) and "sequences" in data and "params" in data:
            return data
    return None


def text_files(outputs: Path) -> str:
    chunks = []
    for path in sorted(outputs.iterdir()) if outputs.is_dir() else []:
        if path.suffix.lower() in {".md", ".txt", ".sh"} and path.is_file():
            chunks.append(path.read_text(errors="replace"))
    return "\n".join(chunks).lower()


def grade_expectation(text: str, payload: dict | None, blob: str) -> tuple[bool, str]:
    t = text.lower()

    if "params.modelname equal to esmfold2-fast-2026-05" in t or "modelname equal to esmfold2-fast" in t:
        mn = (payload or {}).get("params", {}).get("modelName") if payload else None
        ok = mn == "esmfold2-fast-2026-05"
        return ok, f"params.modelName={mn!r}"

    if "does not use params.model (wrong field)" in t:
        ok = payload is not None and "model" not in (payload.get("params") or {}) and "model" not in payload
        # allow top-level name etc; flag if params.model exists
        has_wrong = isinstance(payload, dict) and (
            "model" in payload.get("params", {}) or payload.get("model")
        )
        return (not has_wrong and payload is not None), f"wrong_model_field={has_wrong}"

    if "proteinchain sequence" in t:
        seqs = (payload or {}).get("sequences") or []
        ok = any(isinstance(s, dict) and "proteinChain" in s for s in seqs)
        return ok, f"has_proteinChain={ok}"

    if "does not use modelname esm1b" in t:
        mn = (payload or {}).get("params", {}).get("modelName") if payload else None
        ok = mn != "esm1b" and mn is not None
        return ok, f"params.modelName={mn!r}"

    if "modelname is exactly nesso" in t:
        mn = (payload or {}).get("params", {}).get("modelName") if payload else None
        ok = mn == "nesso"
        return ok, f"params.modelName={mn!r}"

    if "ligand has property_type affinity" in t:
        seqs = (payload or {}).get("sequences") or []
        ok = False
        for s in seqs:
            lig = s.get("ligandSequence") if isinstance(s, dict) else None
            if isinstance(lig, dict) and lig.get("property_type") == "affinity":
                ok = True
        return ok, f"ligand_affinity={ok}"

    if "does not return cif/pdb" in t or "not return cif" in t:
        ok = ("cif" in blob and ("not" in blob or "no " in blob or "affinity-only" in blob or "affinity only" in blob)) or (
            "no structure" in blob or "affinity-only" in blob or "affinity only" in blob or "not a folded structure" in blob
        )
        return ok, "notes mention no structure/CIF"

    if "affinity metrics" in t or "affinity_result_raw_json" in t:
        ok = "affinity" in blob
        return ok, f"notes mention affinity={ok}"

    if "modelname is boltz-2" in t or "params.modelname is boltz-2" in t:
        mn = (payload or {}).get("params", {}).get("modelName") if payload else None
        ok = mn == "boltz-2"
        return ok, f"params.modelName={mn!r}"

    if "webhooks.nesso.enabled is true" in t:
        nesso = (
            ((payload or {}).get("constraints") or {}).get("webhooks") or {}
        ).get("nesso") or {}
        ok = bool(nesso.get("enabled") is True)
        return ok, f"nesso.enabled={nesso.get('enabled')!r}"

    if "event is on_start" in t:
        nesso = (
            ((payload or {}).get("constraints") or {}).get("webhooks") or {}
        ).get("nesso") or {}
        ok = nesso.get("event") == "on_start"
        return ok, f"nesso.event={nesso.get('event')!r}"

    if "protein_chain_id a and ligand_chain_id b" in t:
        nesso = (
            ((payload or {}).get("constraints") or {}).get("webhooks") or {}
        ).get("nesso") or {}
        ok = nesso.get("protein_chain_id") == "A" and nesso.get("ligand_chain_id") == "B"
        return ok, f"chains={nesso.get('protein_chain_id')!r}/{nesso.get('ligand_chain_id')!r}"

    if "wait_for_nesso_linked.py" in t:
        ok = "wait_for_nesso_linked.py" in blob
        return ok, f"waiter_script={ok}"

    if "modelname is exactly openfold3" in t:
        mn = (payload or {}).get("params", {}).get("modelName") if payload else None
        ok = mn == "openfold3"
        return ok, f"params.modelName={mn!r}"

    if "diffusionsample (singular)" in t:
        params = (payload or {}).get("params") or {}
        if "diffusionSamples" in params:
            return False, "found diffusionSamples (plural)"
        if "diffusionSample" in params:
            return True, f"diffusionSample={params.get('diffusionSample')!r}"
        # omitted is ok (defaults)
        return True, "diffusionSample omitted (defaults ok)"

    if "does not set computeaffinity" in t or "boltz affinity params" in t:
        params = (payload or {}).get("params") or {}
        bad = [k for k in ("computeAffinity", "samplingStepsAffinity", "diffusionSamplesAffinity", "affinityMwCorrection") if k in params]
        return len(bad) == 0, f"boltz_affinity_params={bad}"

    return False, "no grader rule matched"


def grade_run(run_dir: Path, expectations: list[str]) -> dict:
    outputs = run_dir / "outputs"
    payload = find_payload(outputs)
    blob = text_files(outputs)
    if payload:
        blob += "\n" + json.dumps(payload).lower()

    graded = []
    for exp in expectations:
        passed, evidence = grade_expectation(exp, payload, blob)
        graded.append({"text": exp, "passed": passed, "evidence": evidence})

    passed_n = sum(1 for g in graded if g["passed"])
    total = len(graded)
    return {
        "expectations": graded,
        "summary": {
            "passed": passed_n,
            "failed": total - passed_n,
            "total": total,
            "pass_rate": round(passed_n / total, 3) if total else 0.0,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--evals", type=Path, default=EVALS)
    args = ap.parse_args()

    catalog = json.loads(args.evals.read_text())
    by_name = {e["name"]: e for e in catalog["evals"]}
    by_id = {e["id"]: e for e in catalog["evals"]}

    rows = []
    for eval_dir in sorted(p for p in args.workspace.iterdir() if p.is_dir() and not p.name.startswith(".")):
        meta_path = eval_dir / "eval_metadata.json"
        meta = load_json(meta_path) if meta_path.exists() else {}
        name = (meta or {}).get("eval_name") or eval_dir.name
        eval_def = by_name.get(name) or by_id.get((meta or {}).get("eval_id"))
        if not eval_def:
            # try directory name
            eval_def = by_name.get(eval_dir.name)
        if not eval_def:
            continue
        expectations = eval_def.get("expectations") or eval_def.get("expectations") or []
        # also from meta
        if (meta or {}).get("assertions"):
            expectations = [a if isinstance(a, str) else a.get("text", "") for a in meta["assertions"]]

        for config in ("with_skill", "without_skill"):
            run_dir = eval_dir / config
            if not run_dir.is_dir():
                continue
            grading = grade_run(run_dir, expectations)
            (run_dir / "grading.json").write_text(json.dumps(grading, indent=2) + "\n")
            rows.append(
                {
                    "eval": name,
                    "configuration": config,
                    "pass_rate": grading["summary"]["pass_rate"],
                    "passed": grading["summary"]["passed"],
                    "total": grading["summary"]["total"],
                }
            )

    summary = {
        "rows": rows,
        "with_skill_mean": _mean([r["pass_rate"] for r in rows if r["configuration"] == "with_skill"]),
        "without_skill_mean": _mean([r["pass_rate"] for r in rows if r["configuration"] == "without_skill"]),
    }
    (args.workspace / "grading_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# Instruction grading summary",
        "",
        f"- with_skill mean pass_rate: **{summary['with_skill_mean']:.0%}**",
        f"- without_skill mean pass_rate: **{summary['without_skill_mean']:.0%}**",
        "",
        "| Eval | Config | Pass |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['eval']} | {r['configuration']} | {r['passed']}/{r['total']} ({r['pass_rate']:.0%}) |")
    (args.workspace / "grading_summary.md").write_text("\n".join(lines) + "\n")
    print(args.workspace / "grading_summary.md")


def _mean(vals: list[float]) -> float:
    return round(sum(vals) / len(vals), 3) if vals else 0.0


if __name__ == "__main__":
    main()
