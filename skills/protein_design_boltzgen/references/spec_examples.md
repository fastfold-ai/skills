# Design Spec Examples

Bundled Composer-aligned preset examples (7 presets):

- `references/examples/vanilla_target_binding_site/`
  - `beetletert.yaml`
  - `5cqg.cif`
- `references/examples/vanilla_protein/`
  - `1g13prot.yaml`
  - `1g13.cif`
- `references/examples/binding_disordered_peptides/`
  - `tpp4.yaml`
- `references/examples/protein_binding_small_molecule/`
  - `chorismite.yaml`
- `references/examples/small_molecule_from_file_and_smiles/`
  - `4g37.yaml`
  - `4g37.pdb`
- `references/examples/cyclic_against_hiv_antibody_site/`
  - `9d3d.yaml`
  - `9d3d.cif`
- `references/examples/nanobody_against_penguinpox_multi_spec/`
  - `penguinpox.yaml`
  - `9bkq-assembly2.cif`
  - uses scaffold specs in `references/examples/nanobody_scaffolds/`

When asked for a "preset example", prefer these files directly instead of crafting new YAML from scratch.

## Natural Prompt Mapping

Use this mapping before any external data fetch:

- "help me design a protein" / "simple peptide binder" -> `vanilla_target_binding_site`
- "let's do 5CQG" -> use:
  - `references/examples/vanilla_target_binding_site/beetletert.yaml`
  - `references/examples/vanilla_target_binding_site/5cqg.cif`
- "simple protein example" -> `vanilla_protein`

If a matching bundled example exists, do not fetch from RCSB/PDB first.
If a preset template exists, do not hand-write `workflow.yml` from scratch.

Resolve exact local file paths with:

- `python scripts/workflow_api.py example-files --list`
- `python scripts/workflow_api.py example-files --preset <preset_id> --json`

Build a valid upsert-ready workflow YAML from official templates:

- `python scripts/workflow_api.py build-spec --preset <preset_id> --out /tmp/boltzgen_workflow.yml`
- Templates used by `build-spec`: `references/workflow_specs/*.workflow.yml`

## Single-spec example (target binding site)

```yaml
entities:
  - protein:
      id: C
      sequence: 10..18
  - file:
      path: 5cqg.cif
      include:
        - chain:
            id: A
            res_index: 68,70,72..74
```

## Multi-spec example (main spec references scaffold specs)

`penguinpox.yaml`:

```yaml
entities:
  - file:
      path: 9bkq-assembly2.cif
      include:
        - chain:
            id: B
  - file:
      path:
        - ../nanobody_scaffolds/7eow.yaml
        - ../nanobody_scaffolds/7xl0.yaml
```

`nanobody_scaffolds/7eow.yaml`:

```yaml
entities:
  - file:
      path: 7eow.cif
      include:
        - chain:
            id: A
      design:
        - chain:
            id: A
            res_index: 26..32,52..57,99..108
      design_insertions:
        - insertion:
            id: A
            res_index: 26
            num_residues: 1..5
      reset_res_index:
        - chain:
            id: A
```

## Workflow graph reminder

For API graph upsert (`/v1/workflows/{id}/workflow.yml`):

- Add one `input` node (`subType: design_specification_yml`) per design YAML.
- Connect referenced scaffold design nodes upstream of the main design node.
- Keep exactly one `start` node and a connected path to `end`.

## Validation step

Before long runs:

1. Start with low cost (`numDesigns: 1`, `budget: 1`).
2. Execute and confirm task results populate.
3. Scale to larger `numDesigns` and `budget`.

## When building from scratch

- Collect user constraints first, then request CIF/PDB file upload.
- Keep YAML keys limited to `references/yaml_keys.md`.
- Cross-check shape against official BoltzGen reference:
  - <https://github.com/HannesStark/boltzgen/blob/main/README.md>
