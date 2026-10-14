# Unified Boltz API Reference

Primary sources:

- API docs root: `https://api.boltz.bio/docs/`
- API reference: `https://api.boltz.bio/docs/api/`
- CLI repo: `https://github.com/boltz-bio/boltz-api-cli`

## Contents

- [Mode to CLI Resource Mapping](#mode-to-cli-resource-mapping)
- [BoltzMol / BoltzProt Feature Coverage](#boltzmol--boltzprot-feature-coverage)
- [Per-Resource Action Matrix](#per-resource-action-matrix)
- [Payload rules that apply to every mode](#payload-rules-that-apply-to-every-mode)
- [`sab` — structure and binding](#sab--structure-and-binding)
- [`adme`](#adme)
- [`protein-design`](#protein-design)
- [`protein-screen`](#protein-screen)
- [`sm-design` and `sm-screen`](#sm-design-and-sm-screen)
- [Cost](#cost)
- [Raw HTTP Endpoints](#raw-http-endpoints-reference-contract)
- [CLI Usage Pattern](#cli-usage-pattern)

## Mode to CLI Resource Mapping

- `sab` -> `predictions:structure-and-binding`
- `protein-design` -> `protein:design`
- `protein-screen` -> `protein:library-screen`
- `sm-design` -> `small-molecule:design`
- `sm-screen` -> `small-molecule:library-screen`
- `adme` -> `predictions:adme`

## BoltzMol / BoltzProt Feature Coverage

This skill covers the API-visible features exposed for BoltzMol/BoltzProt/Boltz-2 workflows:

- **BoltzMol-1 small-molecule hit discovery**
  - **Generate** candidates -> `sm-design` (`small-molecule:design`)
  - **Screen** provided molecule libraries -> `sm-screen` (`small-molecule:library-screen`)
  - **Tier-1 ADME** support -> `adme` (`predictions:adme`) and ADME fields in design/screen results when present
  - **Property steering/filtering** -> pass `molecule_filters` and `chemical_space` in mode payload
- **BoltzProt-1 protein binder design**
  - **De novo binder generation** -> `protein-design` (`protein:design`)
  - **Protein library scoring/screening** -> `protein-screen` (`protein:library-screen`)
  - **Ranking metrics exposure** -> `binding_confidence`, `structure_confidence`, `iptm`, `min_interaction_pae`, etc. returned by API/CLI output
- **Boltz-2 structure + binding**
  - `sab` mode (`predictions:structure-and-binding`, model `boltz-2.1`)
- **Operational API features**
  - Cost estimate before submission (`estimate-cost`)
  - Idempotent run naming (`--idempotency-key`/`--name` reused per experiment)
  - Download recovery (`download-results --id <id>`)
  - Post-eviction recovery from the API without re-submitting (`list` + `download-results`)
  - Paginated per-item results for design/screen (`list-results`)
  - Early stop for design/screen (`stop`)
  - Permanent data deletion (`delete-data`, irreversible)

## Per-Resource Action Matrix

CLI subcommands available per resource (verified against `boltz-api <resource> --help`):

| Subcommand | sab | adme | protein-design | protein-screen | sm-design | sm-screen |
| --- | --- | --- | --- | --- | --- | --- |
| `estimate-cost` | yes | yes | yes | yes | yes | yes |
| `start` / `run` | yes | yes | yes | yes | yes | yes |
| `retrieve` | yes | yes | yes | yes | yes | yes |
| `list` | yes | yes | yes | yes | yes | yes |
| `list-results` | no | no | yes | yes | yes | yes |
| `stop` | no | no | yes | yes | yes | yes |
| `delete-data` | yes | yes | yes | yes | yes | yes |

Notes:

- There is no `pause`/`unpause` on any resource. Lifecycle controls are `start`, `stop`
  (design/screen only), and `delete-data`. `download-results` resumes the result *download*, not compute.
- `sab` and `adme` are short synchronous predictions: results come back via `retrieve` (no
  `list-results`), and they cannot be stopped.
- `delete-data` permanently deletes input/output/result data (the run record is kept with a
  `data_deleted_at` timestamp). It is irreversible; the runner gates it behind `--confirm-delete`.

## Payload rules that apply to every mode

These are the field-level mistakes that produce unhelpful `400 VALIDATION_ERROR`
responses. Read this section before authoring a first payload for any mode.

### Entity shape

An entity is `{type, chain_ids, value}`:

```yaml
entities:
  - type: protein          # protein | rna | dna | ligand_smiles | ligand_ccd
    chain_ids: ["A"]       # ALWAYS an array, even for one chain
    value: MKTAYIAKQRQISFVKSHFSRQ
```

- The field is **`value`**, not `sequence`.
- The field is **`chain_ids`** (plural, array), not `chain_id`.
- Chain IDs follow entity order (`A`, `B`, `C`, …) unless the user specifies otherwise.

### Residue indices are 0-based

Everywhere a payload takes a residue position — `epitope_residues`,
`non_binding_residues`, `pocket_residues`, `crop_residues`, `flexible_residues`,
`design_motifs.start_index` / `end_index`, `after_residue_index`, constraints,
modifications, bonds — the index is **0-based**.

When mapping from a structure: `API index = canonical label_seq_id − 1`. Use
`label_seq`, never author numbering (`auth_seq_id`).

### Passing payloads and files

- Object-typed payloads: `--input @yaml:///absolute/path/payload.yaml` or
  `@json:///absolute/path/payload.json`. Never `@./payload.yaml`, never `@file://`.
- Embedded CIF/PDB bytes (inside `structure.data`, `--target`): `@data:///absolute/path/file.cif`
  — it detects binary and base64-encodes. A bare `@path` does not work for binary data.
- Use absolute paths for payloads, structure files, and the output root.
- `--idempotency-key` and `--workspace-id` stay top-level flags. If they also appear
  inside `--input`, the top-level flags win.
- `--workspace-id <id>` is accepted on submit for admin keys only.

### Permission-gated runtimes

Keep each Boltz call a top-level command starting with `boltz-api`. Prefer concrete
arguments over `sh -c`, inline env assignments, aliases, wrapper scripts, loops, or
pipelines around the invocation — those defeat per-command approval rules. To capture
a job id, use `--raw-output --transform id`, read the printed id, then paste that
literal id into the next command.

## `sab` — structure and binding

Resource `predictions:structure-and-binding`, always with `--model boltz-2.1`.

Top-level: `entities` (required), `binding` (optional), `num_samples`,
plus optional `constraints`, `bonds`, `modifications`, `model_options`.

The `binding` block is **flat**, with an explicit `type` discriminator. Do not nest
the variant name as an object under `binding`.

```yaml
binding:
  type: ligand_protein_binding
  binder_chain_id: B            # singular for ligand-protein
```

```yaml
binding:
  type: protein_protein_binding
  binder_chain_ids: ["B"]       # plural array for protein-protein
```

Only add `constraints`, `bonds`, `modifications`, or `model_options` when the user asks.

**Validation quirk:** this endpoint rejects bad payloads with only
`{"code":"VALIDATION_ERROR","message":"Request validation failed"}` and no field path
more often than the others. When that happens, inspect `entities`, `binding`, and
`constraints` first — in practice it is usually `sequence` instead of `value`, a
singular `chain_id`, or a nested `binding` variant.

## `adme`

Resource `predictions:adme`, always with `--model adme-v1`.

Payload is just `molecules: [{smiles, id?}]` — no target. Priced at **$0.01 per
molecule**, size-independent; `estimate-cost` still returns the authoritative total
and is what you quote.

ADME values are approximate estimates for triage and ranking, not measurements. Say so
when reporting them.

## `protein-design`

Resource `protein:design`. Top-level: `num_proteins`, `target`, `binder_specification`.

### `num_proteins`

Valid range is **10 to 1,000,000** — the server rejects anything outside it. 10 is a
smoke-test size, not a campaign. See Run sizing in SKILL.md for tiers.

### `target` variants

- `type: structure_template` — a CIF/PDB via `structure.data` (`@data:///abs/path`),
  optionally with `chain_selection`, `crop_residues`, `flexible_residues`.
- `type: no_template` — `entities` only (sequence-based).

Both accept `epitope_residues` (a map of chain id → 0-based index list) to condition
generation on a site. Omit it to let the model find its own site.

### `binder_specification` variants

**1. `boltz_curated`** — recommended default for antibody and nanobody design. Boltz
picks from maintained scaffold/template lists.

```yaml
binder_specification:
  type: boltz_curated
  binder: boltz_nanobody        # or boltz_antibody
```

Use `boltz_antibody` for antibody/Fab requests, `boltz_nanobody` for nanobody/VHH.
Do **not** include `modality`, `entities`, `structure`, or `chain_selection` in this
variant — `binder` carries that information.

**2. `structure_template`** — redesign motifs inside an existing binder scaffold. Takes
a CIF plus `design_motifs` with `replacement` / `insertion` segments
(`start_index` / `end_index` / `after_residue_index`, all 0-based).

**3. `no_template`** — generate from the sequence DSL.

```yaml
binder_specification:
  type: no_template
  modality: custom_protein      # peptide | antibody | nanobody | custom_protein
  entities:
    - type: designed_protein
      chain_ids: ["B"]
      value: "10..14"
```

`modality` applies to `structure_template` and `no_template` only. Use
`custom_protein` for a "miniprotein" or a generic "protein binder".

### Sequence DSL (`designed_protein.value`)

- Uppercase letters — fixed residues.
- Integer `N` — exactly `N` designed residues.
- `MIN..MAX` — a variable-length designed segment.

Examples: `"20"`, `"5..10"`, `"ACDE8GHI"`, `"MKTAYI5..10VKSHFSRQ"`.

### `rules`

Optional generation constraints — excluded amino acids, excluded sequence motifs with
`X` wildcards, `max_hydrophobic_fraction`. Add them **only** on explicit user request.

## `protein-screen`

Resource `protein:library-screen`. Top-level: `target`, `proteins`.

`target` takes the same variants as design, plus `epitope_residues` and
`non_binding_residues` (chain id → 0-based index list) to steer or forbid a patch.

`proteins` is a list of `{id?, entities}`. Set `id` — it comes back as `external_id`
on each result, which is the only reliable way to map results to inputs and to spot
entries that were dropped.

## `sm-design` and `sm-screen`

Resources `small-molecule:design` and `small-molecule:library-screen`.

- `sm-design`: `target` (+ `pocket_residues`, 0-based), `num_molecules`, optional
  `molecule_filters`, optional `chemical_space`.
- `sm-screen`: `target`, `molecules: [{smiles, id?}]`, optional `molecule_filters`.

Payload keys are the API body names `molecules` / `target` / `molecule_filters` — not
the direct CLI flags `--molecule` / `--target` / `--molecule-filters`.

Both return free Tier-1 ADME fields per molecule when available, so a screen usually
does not need a separate `adme` run.

### Library input formats

A user's library arrives as raw SMILES, a CSV, a `.smi`, or a `.txt`. Normalize it into
the `molecules` list yourself: auto-detect the SMILES column in a CSV, carry any
identifier column into `id`, and report how many molecules you parsed before estimating.

### `molecule_filters`

```yaml
molecule_filters:
  boltz_smarts_catalog_filter_level: recommended   # or: extra
  custom_filters:
    - type: lipinski_filter
      max_mw: 500
      max_logp: 5
      max_hbd: 5
      max_hba: 10
```

Filtered-out molecules do not appear in results — reconcile counts afterwards.

## Cost

`estimate-cost` is the only source of a dollar figure. Never quote, extrapolate, or
infer one. The cost model is tiered by total complex length for structure-based modes
and per-molecule for ADME ($0.01/molecule), but the tier boundaries are not published —
run the estimate and state what it returns.

An estimate for one configuration says nothing about another: re-estimate when the
payload, the library size, or `num_proteins` / `num_molecules` changes.

## Raw HTTP Endpoints (Reference Contract)

- `sab` (`predictions:structure-and-binding`)
  - `POST /compute/v1/predictions/structure-and-binding`
  - `GET /compute/v1/predictions/structure-and-binding`
  - `GET /compute/v1/predictions/structure-and-binding/{id}`
  - `POST /compute/v1/predictions/structure-and-binding/{id}/delete-data`
  - `POST /compute/v1/predictions/structure-and-binding/estimate-cost`
- `adme` (`predictions:adme`)
  - `POST /compute/v1/predictions/adme`
  - `GET /compute/v1/predictions/adme`
  - `GET /compute/v1/predictions/adme/{id}`
  - `POST /compute/v1/predictions/adme/{id}/delete-data`
  - `POST /compute/v1/predictions/adme/estimate-cost`
- `sm-design` (`small-molecule:design`)
  - `POST /compute/v1/small-molecule/design`
  - `GET /compute/v1/small-molecule/design`
  - `GET /compute/v1/small-molecule/design/{id}`
  - `GET /compute/v1/small-molecule/design/{id}/results`
  - `POST /compute/v1/small-molecule/design/{id}/stop`
  - `POST /compute/v1/small-molecule/design/{id}/delete-data`
  - `POST /compute/v1/small-molecule/design/estimate-cost`
- `sm-screen` (`small-molecule:library-screen`)
  - `POST /compute/v1/small-molecule/library-screen`
  - `GET /compute/v1/small-molecule/library-screen`
  - `GET /compute/v1/small-molecule/library-screen/{id}`
  - `GET /compute/v1/small-molecule/library-screen/{id}/results`
  - `POST /compute/v1/small-molecule/library-screen/{id}/stop`
  - `POST /compute/v1/small-molecule/library-screen/{id}/delete-data`
  - `POST /compute/v1/small-molecule/library-screen/estimate-cost`
- `protein-design` (`protein:design`)
  - `POST /compute/v1/protein/design`
  - `GET /compute/v1/protein/design`
  - `GET /compute/v1/protein/design/{id}`
  - `GET /compute/v1/protein/design/{id}/results`
  - `POST /compute/v1/protein/design/{id}/stop`
  - `POST /compute/v1/protein/design/{id}/delete-data`
  - `POST /compute/v1/protein/design/estimate-cost`
- `protein-screen` (`protein:library-screen`)
  - `POST /compute/v1/protein/library-screen`
  - `GET /compute/v1/protein/library-screen`
  - `GET /compute/v1/protein/library-screen/{id}`
  - `GET /compute/v1/protein/library-screen/{id}/results`
  - `POST /compute/v1/protein/library-screen/{id}/stop`
  - `POST /compute/v1/protein/library-screen/{id}/delete-data`
  - `POST /compute/v1/protein/library-screen/estimate-cost`

## CLI Usage Pattern

Pick `<resource>` from the mapping above; reuse one `<slug>` as `--idempotency-key` and `--name`.
Set `<root>` by runtime — local agent (sandwalk): `"${OUTPUT_DIR:-./outputs}/boltz"`;
hosted sandbox with S3-backed `/workspace`: `/tmp/boltz-runs` (then `persist.sh`). See
[results.md](results.md) for the full rule.

```bash
# Estimate (never bills), then submit after approval
boltz-api <resource> estimate-cost --input @yaml:///absolute/path/payload.yaml   # + --model for sab/adme
boltz-api <resource> run --input @yaml:///absolute/path/payload.yaml \
  --idempotency-key <slug> --name <slug> --root-dir <root>
# hosted sandbox only: scripts/persist.sh /tmp/boltz-runs/<slug>     # copy to S3-backed /workspace

# Async alternative: submit, then poll + download later
boltz-api <resource> start --input @yaml:///absolute/path/payload.yaml \
  --idempotency-key <slug> --raw-output --transform id               # prints the job id
boltz-api download-results --id <id> --name <slug> --root-dir <root> \
  --poll-interval-seconds <10 sab/adme | 30 screens | 60 design>
boltz-api --format json download-status --name <slug> --root-dir <root>

# Inspect / lifecycle
boltz-api <resource> retrieve --id <id> --format json
boltz-api <resource> list --limit 20 --format jsonl
boltz-api <resource> list-results --id <id> --format jsonl          # design/screen only
boltz-api <resource> stop --id <id>                                 # design/screen only
boltz-api <resource> delete-data --id <id>                         # irreversible — confirm first
```

Recovery (recover from the API, never by re-submitting — needed on a hosted sandbox after eviction or
any time the local run dir is gone): find the id with `list` (match `idempotency_key`), then
`download-results --id <id> --name <slug> --root-dir <root>` (and `persist.sh` only on a hosted sandbox).

## Escape hatch

For a field not covered here:

- Payload shapes: <https://api.boltz.bio/docs/guides/concepts/>
- API reference: <https://api.boltz.bio/docs/api/>
- CLI flag names: `boltz-api <resource> start --help` (flag names and types only — not a schema source)
