# FastFold Jobs API – Schema Summary

The full OpenAPI 3.1 schema is in this skill (self-contained): **[jobs.yaml](jobs.yaml)** (in `references/`).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/jobs` | Create Job – body: JobInput (name, sequences, params required) |
| GET | `/v1/jobs/{jobId}/results` | Get Job Results – returns JobResultsOutput |
| PATCH | `/v1/jobs/{jobId}/public` | Update Job Public Visibility – body: { isPublic: boolean } |

## Key Schemas

- **JobInput:** `name`, `sequences` (array of SequenceInput), `params` (ParamsInput with `modelName`), optional `isPublic`, `constraints` (including `constraints.webhooks`), `chatId`, `from` (library UUID).
- **SequenceInput:** Exactly one of `proteinChain`, `rnaSequence`, `dnaSequence`, `ligandSequence`.
- **ParamsInput:** `modelName` (see ModelName: `boltz-2`, `openfold3`, `chai1`, `intellifold`, `monomer`, `multimer`, `esm1b`, `boltz`, `simplefold_100M`/`360M`/`700M`/`1.1B`/`1.6B`/`3B`), optional `relaxPrediction`, `seed`, `recyclingSteps` / `samplingSteps` / `stepScale` / affinity fields (**Boltz**), `diffusionSample` and `numModelSeeds` (**OpenFold 3**), `numDiffnSamples` / `numTrunkSamples` / `numTrunkRecycles` / `numDiffnTimesteps` (**Chai-1**), and Boltz-overlapping optional params for **IntelliFold** (`recyclingSteps`, `samplingSteps`, `diffusionSample`). Use `esm1b` when the user says "ESM", "ESMFold", or "ESM-1b".
- **ModificationInput:** `res_idx` (1-based), `ccd` — on protein, RNA, or DNA chains for non-canonical residues.
- **JobResponse:** `jobId`, `jobRunId`, `jobName`, `jobStatus`, `sequencesIds`.
- **JobStatus:** PENDING | INITIALIZED | RUNNING | COMPLETED | FAILED | STOPPED.
- **JobResultsOutput:** `job` (JobInfoOutput), `parameters`, `sequences` (each may have `predictionPayload`), optional top-level `predictionPayload` for complex jobs.
- **PredictionPayload:** `cif_url`, `pdb_url`, `meanPLLDT`, `pae_plot_url`, `plddt_plot_url`, `ptm_score`, `iptm_score`, `metrics_json_url`, `affinity_result_raw_json`, etc.
- **Affinity output shape:** `affinity_result_raw_json` is an embedded JSON object in `PredictionPayload` (for example `affinity_pred_value*`, `affinity_probability_binary*`) and may not be exposed as a downloadable `*_url` artifact.
- **Webhook metadata (current catalog):**
  - Evolla: `constraints.webhooks.evolla.enabled` + optional `constraints.webhooks.evolla.initial_question`
  - OpenMM: `constraints.webhooks.openmm.enabled` + optional OpenMM overrides (`preset`, `residue_profile`, `temp`, `ionic`, `pH`, `step_size_ns`, `sim_length_ns`, `box_mode`, `box_length`, etc.)
  - The object remains extensible for future webhook options.
  Read fold output via `/v1/jobs/{jobId}/results`, then:
  - Evolla linked history: `/v1/workflows/evolla/linked-history` (`workflowStatus`, `lastAnswer`, `lastQuestion`)
  - OpenMM linkage/status via fold/OpenMM linked helper flows.

Use [jobs.yaml](jobs.yaml) in this skill for exact field names, types, and examples.
