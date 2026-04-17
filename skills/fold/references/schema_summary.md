# FastFold Jobs API – Schema Summary

The full OpenAPI 3.1 schema is in this skill (self-contained): **[jobs.yaml](jobs.yaml)** (in `references/`).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/jobs` | Create Job – body: JobInput (name, sequences, params required) |
| GET | `/v1/jobs/{jobId}/results` | Get Job Results – returns JobResultsOutput |
| PATCH | `/v1/jobs/{jobId}/public` | Update Job Public Visibility – body: { isPublic: boolean } |

## Key Schemas

- **JobInput:** `name`, `sequences` (array of SequenceInput), `params` (ParamsInput with `modelName`), optional `isPublic`, `constraints`, `chatId`, `from` (library UUID).
- **SequenceInput:** Exactly one of `proteinChain`, `rnaSequence`, `dnaSequence`, `ligandSequence`.
- **ParamsInput:** `modelName` (see ModelName: `boltz-2`, `openfold3`, `chai1`, `monomer`, ...), optional `relaxPrediction`, `seed`, `recyclingSteps` / `samplingSteps` / `stepScale` / affinity fields (**Boltz**), `diffusionSample` and `numModelSeeds` (**OpenFold 3**), `numDiffnSamples` / `numTrunkSamples` / `numTrunkRecycles` / `numDiffnTimesteps` (**Chai-1**).
- **ModificationInput:** `res_idx` (1-based), `ccd` — on protein, RNA, or DNA chains for non-canonical residues.
- **JobResponse:** `jobId`, `jobRunId`, `jobName`, `jobStatus`, `sequencesIds`.
- **JobStatus:** PENDING | INITIALIZED | RUNNING | COMPLETED | FAILED | STOPPED.
- **JobResultsOutput:** `job` (JobInfoOutput), `parameters`, `sequences` (each may have `predictionPayload`), optional top-level `predictionPayload` for complex jobs.
- **PredictionPayload:** `cif_url`, `pdb_url`, `meanPLLDT`, `pae_plot_url`, `plddt_plot_url`, `ptm_score`, `iptm_score`, `metrics_json_url`, `affinity_result_raw_json`, etc.

Use [jobs.yaml](jobs.yaml) in this skill for exact field names, types, and examples.
