# md_openmm_calvados evals

```bash
export FASTFOLD_API_KEY=...
# requires a recent fold api-baseline with a passed boltz-2 job
python3 evals/md_openmm_calvados/scripts/run_api_baseline.py
```

Cases: fold-job source + UniProt manual PDB/PAE. Short `sim_length_ns=0.05`.
