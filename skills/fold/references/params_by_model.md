# Params by model

Optional `params` fields. Omit keys to use server defaults.

### Boltz / Boltz-2

Optional fields — omit to use defaults. **Affinity-related** keys apply only when a ligand has `property_type: "affinity"`.

```json
{
  "params": {
    "modelName": "boltz-2",
    "recyclingSteps": 3,
    "samplingSteps": 200,
    "diffusionSample": 1,
    "stepScale": 1.638,
    "relaxPrediction": true,
    "affinityMwCorrection": false,
    "samplingStepsAffinity": 200,
    "diffusionSamplesAffinity": 5
  }
}
```

### OpenFold 3 (`openfold3`)

- **`diffusionSample`** — diffusion sample count for the OpenFold 3 run (server defaults apply if omitted).
- **`numModelSeeds`** — number of model seeds (integer ≥ 1).
- **`relaxPrediction`** — omit for OpenFold 3 (defaults to `false`); the runner does not apply structure relaxation like Boltz/AF2.
- Do **not** expect **`recyclingSteps`**, **`samplingSteps`**, **`stepScale`**, or **affinity** fields (`samplingStepsAffinity`, `diffusionSamplesAffinity`, `affinityMwCorrection`) to affect OpenFold 3; those are for Boltz models.

```json
{
  "params": {
    "modelName": "openfold3",
    "diffusionSample": 5,
    "numModelSeeds": 1
  }
}
```

### Chai-1 (`chai1`)

- **`numDiffnSamples`** - number of diffusion samples.
- **`numTrunkSamples`** - number of trunk samples.
- **`numTrunkRecycles`** - trunk recycles per sample.
- **`numDiffnTimesteps`** - diffusion timesteps.
- Chai-1 accepts **protein / RNA / DNA / ligand** inputs and supports `constraints.contact`, `constraints.pocket`, and `constraints.bond`.

```json
{
  "params": {
    "modelName": "chai1",
    "numDiffnSamples": 5,
    "numTrunkSamples": 1,
    "numTrunkRecycles": 3,
    "numDiffnTimesteps": 200
  }
}
```

### IntelliFold (`intellifold`)

- Use **`recyclingSteps`**, **`samplingSteps`**, and **`diffusionSample`** for optional runtime tuning (maps to IntelliFold CLI flags).
- Input is **Boltz-compatible YAML** generated server-side; supports **protein / RNA / DNA / ligand** chains.
- Omit **`relaxPrediction`** (same as OpenFold 3 / Boltz-style complex runs).

```json
{
  "params": {
    "modelName": "intellifold",
    "recyclingSteps": 10,
    "samplingSteps": 200,
    "diffusionSample": 5
  }
}
```

### ESMFold2 (`esmfold2-fast-2026-05` / `esmfold2-2026-05`)

- **`recyclingSteps`** — Biohub “loops” (default 10, typical max 20).
- **`samplingSteps`** — diffusion sampling steps (default 100).
- **`diffusionSample`** — number of diffusion samples (default 1).
- Supports protein / DNA / RNA / ligand complexes. Prefer exact weight-set `modelName` strings above.

### Nesso-1 (`nesso`)

- **Affinity metrics only** — no structure output (no CIF/PDB / viewer from Nesso itself).
- **`recyclingSteps`** — optional (default 5, clamp 1–20).
- Requires protein + ligand with `"property_type": "affinity"` on the ligand.
- For **structure + affinity**, use a parent structure model + `constraints.webhooks.nesso` (parent CIF + merged Nesso metrics).
