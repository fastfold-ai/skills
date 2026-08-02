# FastFold skills evals

Re-runnable API baselines for skill scripts.

| Skill | Runner |
|---|---|
| `fold` | `python3 evals/fold/scripts/run_api_baseline.py` |
| `md_openmm_calvados` | `python3 evals/md_openmm_calvados/scripts/run_api_baseline.py` |
| `md_openmmdl` | `python3 evals/md_openmmdl/scripts/run_api_baseline.py` |
| `protein_design_boltzgen` | `python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py` |

```bash
export FASTFOLD_API_KEY=...
# fold first (MD baselines reuse a completed boltz-2 job id)
python3 evals/fold/scripts/run_api_baseline.py --only boltz-2
python3 evals/md_openmm_calvados/scripts/run_api_baseline.py
python3 evals/md_openmmdl/scripts/run_api_baseline.py
python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py --only binding_disordered_peptides
```

Metrics land in each skill’s `workspace/api-baseline-*/metrics.md` (gitignored). Copy shareable summaries into `reports/` if needed.
