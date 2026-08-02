# Fold skill evals

Re-runnable baselines for the FastFold `fold` skill:

1. **API baseline** — submit one short job per catalog model via bundled scripts; wait; collect metrics.
2. **Instruction evals** — with-skill vs without-skill payload construction (skill-creator style); graded assertions + HTML report.

## Setup

```bash
export FASTFOLD_API_KEY='sk-...'   # never commit
cd /path/to/skills
```

Optional:

```bash
export FASTFOLD_BASE_URL='https://api.fastfold.ai'
export FOLD_EVAL_TIMEOUT=1800      # seconds per job wait (default 1800)
```

## Run API baseline (models smoke)

```bash
python3 evals/fold/scripts/run_api_baseline.py
# or only some cases:
python3 evals/fold/scripts/run_api_baseline.py --only boltz-2,nesso,esmfold2-fast
# skip waiting (submit only):
python3 evals/fold/scripts/run_api_baseline.py --submit-only
```

Writes under `evals/fold/workspace/api-baseline-<timestamp>/`:

- `jobs.json` — job ids + submit status
- `results/<case>.json` — final results (or error)
- `metrics.json` — pass/fail, durations, structure vs affinity checks
- `metrics.md` — human summary

## Run instruction evals (agent harness)

Prompts live in `skills/fold/evals/evals.json`.

After with/without-skill runs are populated under
`evals/fold/workspace/iteration-N/<eval-name>/{with_skill,without_skill}/`:

```bash
python3 evals/fold/scripts/grade_instruction_evals.py \
  evals/fold/workspace/iteration-1

python3 evals/fold/scripts/build_benchmark.py \
  evals/fold/workspace/iteration-1 --skill-name fold

python3 evals/fold/vendor/skill-creator/generate_review.py \
  evals/fold/workspace/iteration-1 \
  --skill-name fold \
  --benchmark evals/fold/workspace/iteration-1/benchmark.json \
  --static evals/fold/reports/fold-eval-report.html
```

Open `evals/fold/reports/fold-eval-report.html` in a browser.

## Security

- Do **not** put API keys in this tree.
- Rotate any key that was pasted into chat or logs.
- `workspace/` and `reports/` may contain job ids / signed URLs — treat as private.

## Cases

See `baselines/models.json` for the current model matrix (one payload per model + Nesso webhook).
