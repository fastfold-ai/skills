# BoltzGen Design-Spec YAML Keys

This list is for practical authoring guidance in FastFold BoltzGen workflows.

## Top-level keys

- `entities` (required)
- `constraints` (optional)

## `entities` variants

### `protein`

- `id`
- `sequence`
  - fixed length (`17`)
  - range (`80..140`)
  - mixed fixed+designed segments (`15..20AAAA5`)

### `file`

- `path` (relative to YAML location)
- `include`
  - `chain.id`
  - `chain.res_index`
  - `chain.symmetric_group` (for symmetric inverse-folding setups)
- `exclude`
  - `chain.id`
  - `chain.res_index`
- `include_proximity` (binding-site neighborhood selection)
- `binding_types`
  - `chain.binding`
  - `chain.not_binding`
- `structure_groups`
  - `group.visibility`
  - `group.id`
  - `group.res_index`
- `design`
  - `chain.id`
  - `chain.res_index`
- `design_insertions`
  - `insertion.id`
  - `insertion.res_index`
  - `insertion.num_residues`
- `reset_res_index`
  - `chain.id`
- `secondary_structure`
  - `chain.loop`
  - `chain.helix`
  - `chain.sheet`

### `ligand`

- `id`
- `ccd` or other supported ligand definitions

## `constraints`

- `bond`
  - `atom1: [chain, residue_index, atom_name]`
  - `atom2: [chain, residue_index, atom_name]`

## Important warnings

- Use 1-based residue indices and canonical mmCIF chain/index semantics.
- File paths in YAML are resolved relative to the YAML file path.
- For FastFold API workflow node payloads, use logical file names in
  `inputPayload.files[].fileName` (not hashed storage names).
- Keep one design-spec YAML per Design Spec node in graph-based multi-spec flows.

## From-scratch authoring checklist

When drafting YAML from user requirements (instead of preset files):

1. Ask for target structure input first (`.cif` preferred; `.pdb` accepted).
2. Confirm chain ids and residue ranges before writing `include` / `design` / `exclude`.
3. Map user constraints only to keys documented in this file.
4. If user asks for unsupported keys, do not invent fields; propose a supported alternative.
5. Validate generated YAML against official reference patterns before upload.

## Source references

- Upstream README: <https://github.com/HannesStark/boltzgen/blob/main/README.md>
- Examples in upstream repo: `example/`
