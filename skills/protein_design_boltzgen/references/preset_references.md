# Preset Reference Sources

This skill now bundles local reference files for the same 7 Composer presets under:

- `references/examples/vanilla_target_binding_site/`
- `references/examples/vanilla_protein/`
- `references/examples/binding_disordered_peptides/`
- `references/examples/protein_binding_small_molecule/`
- `references/examples/small_molecule_from_file_and_smiles/`
- `references/examples/cyclic_against_hiv_antibody_site/`
- `references/examples/nanobody_against_penguinpox_multi_spec/`
- shared scaffold files for the multi-spec preset:
  - `references/examples/nanobody_scaffolds/`
- official workflow YAML templates:
  - `references/workflow_specs/*.workflow.yml`

Preferred behavior:

1. Use these bundled local files first when users ask for preset examples.
2. Use `references/spec_examples.md` for structure/pattern guidance.
3. Use `references/yaml_keys.md` when validating supported keys.
4. Resolve exact file paths with:
   - `python scripts/workflow_api.py example-files --preset <preset_id> --json`
5. Build workflow YAML from official template (no manual authoring):
   - `python scripts/workflow_api.py build-spec --preset <preset_id> --out /tmp/boltzgen_workflow.yml`

If a bundled preset exists for the requested example, do not fetch external CIF/PDB first.
