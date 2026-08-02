# Fold skill eval — findings & improvements

## What we measured

1. **API baseline** (`scripts/run_api_baseline.py`) — live submit/wait via fold skill scripts for each catalog model + Nesso webhook.
2. **Instruction evals** (`skills/fold/evals/evals.json`) — with-skill vs without-skill payload construction (skill-creator style), graded + HTML report.

## Instruction-eval caveat (contamination)

In iteration-1, without-skill agents still produced near-perfect FastFold-specific payloads (`esmfold2-fast-2026-05`, `webhooks.nesso.on_start`, `wait_for_nesso_linked.py`). That almost certainly means they could still see this repo / skill files from the shared workspace, so **pass-rate delta understates skill value**.

**Next iteration hardening:**

- Run without-skill agents in an isolated worktree/tmpdir that excludes `skills/fold/`.
- Or replace without-skill with a frozen “wrong common mistakes” fixture set for regression of the grader.
- Prefer prompts that require skill-only knowledge (exact waiter script names, Sandwalk env vars, webhook event `on_start` vs `on_complete`).

## Skill improvements

1. **SKILL.md progressive disclosure** — done: examples → `references/payload_examples.md`, params → `references/params_by_model.md`.
2. **Model catalog table** — done at top of `SKILL.md` (structure vs affinity-only).
3. **Wrong-name traps for webhooks** — done (`on_complete` vs `on_start` for Nesso).
4. **Without-skill isolation** — skipped for now (API baseline is the trusted smoke; skill content looks solid).
5. **Eval automation** — keep `evals/fold/scripts/run_api_baseline.py` as the GPU smoke; instruction evals for agent regressions after SKILL edits.
6. **simplefold sizes** — baseline uses `simplefold_100M` only; optionally rotate other sizes in a weekly long run.

## Re-run

```bash
export FASTFOLD_API_KEY=...
python3 evals/fold/scripts/run_api_baseline.py
# after agent runs into workspace/iteration-N:
python3 evals/fold/scripts/grade_instruction_evals.py evals/fold/workspace/iteration-N
python3 evals/fold/scripts/build_benchmark.py evals/fold/workspace/iteration-N --skill-name fold
python3 evals/fold/vendor/skill-creator/generate_review.py \
  evals/fold/workspace/iteration-N \
  --skill-name fold \
  --benchmark evals/fold/workspace/iteration-N/benchmark.json \
  --static evals/fold/reports/fold-eval-report.html
```
