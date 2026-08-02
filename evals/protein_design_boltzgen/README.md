# protein_design_boltzgen evals

```bash
export FASTFOLD_API_KEY=...
python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py
python3 evals/protein_design_boltzgen/scripts/run_api_baseline.py --only binding_disordered_peptides
```

End-to-end: example-files → new → upload → build-spec → upsert → execute → wait.
