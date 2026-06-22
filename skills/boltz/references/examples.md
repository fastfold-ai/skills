# Boltz Quick Examples (Small Runs)

These examples are intentionally small so users can quickly learn input/output flow.
All payloads are API-body shaped and run through the unified script:

- Estimate (never billable): `python scripts/run.py <mode> --payload <file>.yaml --run-name <slug> --estimate-only`
- Execute (billable — only after the user explicitly approves the estimate): `python scripts/run.py <mode> --payload <file>.yaml --run-name <slug> --yes`

Always run the estimate, show the cost to the user, and wait for explicit approval before the `--yes` execute step. Do not run both in the same turn.

Named targets in prompts/run names are aligned with BoltzMol/BoltzProt public materials
(for example: ROR1, MRGPRX2, GLP2R, PknB, AMBP, IDI2, MZB1, PMVK).
To keep runs fast and cheap, payloads use real UniProt-backed target sequence fragments
(accession + residue range noted inline). For production campaigns, switch to full-length
sequences or structure-template inputs.

Target accession map used in this file:

- ROR1: `Q01973`
- MRGPRX2: `Q96LB1`
- GLP2R: `O95838`
- PknB (Mtb H37Rv): `P9WI81`
- LC3B: `Q9GZQ8`
- GABARAP: `O95166`
- AMBP: `P02760`
- IDI2: `Q9BXS1`
- MZB1: `Q8WU39`
- PMVK: `Q15126`

## 1) Structure and Binding (`sab`)

### Example A — ROR1-style protein + aspirin

User prompt:
- "Run a simple ROR1-style protein-ligand Boltz-2 smoke test with aspirin."

`payload.sab.ror1_aspirin.yaml`
```yaml
# target context: ROR1 pseudokinase, UniProt Q01973, residues 1-90
entities:
  - type: protein
    value: MHRPRRRGTRPPLLALLAALLLAARGAAAQETELSVSAELVPTSSWNISSELNKDSYLTLDEPMNNITTSLGQTAELHCKVSGNPPPTIR
    chain_ids: ["A"]
  - type: ligand_smiles
    value: CC(=O)OC1=CC=CC=C1C(=O)O
    chain_ids: ["B"]
binding:
  type: ligand_protein_binding
  binder_chain_id: B
num_samples: 1
```

Commands:
- `python scripts/run.py sab --payload payload.sab.ror1_aspirin.yaml --run-name sab-ror1-aspirin-demo --estimate-only`
- `python scripts/run.py sab --payload payload.sab.ror1_aspirin.yaml --run-name sab-ror1-aspirin-demo --yes`

### Example B — LC3B/GABARAP-style protein-protein check

User prompt:
- "Run a tiny LC3B/GABARAP-style protein-protein structure+binding example."

`payload.sab.lc3b_gabarap.yaml`
```yaml
# target context: LC3B (Q9GZQ8, full 125 aa) + GABARAP (O95166, full 117 aa)
entities:
  - type: protein
    value: MPSEKTFKQRRTFEQRVEDVRLIREQHPTKIPVIIERYKGEKQLPVLDKTKFLVPDHVNMSELIKIIRRRLQLNANQAFFLLVNGHSMVSVSTPISEVYESEKDEDGFLYMVYASQETFGMKLSV
    chain_ids: ["A"]
  - type: protein
    value: MKFVYKEEHPFEKRRSEGEKIRKKYPDRVPVIVEKAPKARIGDLDKKKYLVPSDLTVGQFYFLIRKRIHLRAEDALFFFVNNVIPPTSATMGQLYQEHHEEDFFLYIAYSDESVYGL
    chain_ids: ["B"]
binding:
  type: protein_protein_binding
  binder_chain_ids: ["B"]
num_samples: 1
```

Commands:
- `python scripts/run.py sab --payload payload.sab.lc3b_gabarap.yaml --run-name sab-lc3b-gabarap-demo --estimate-only`
- `python scripts/run.py sab --payload payload.sab.lc3b_gabarap.yaml --run-name sab-lc3b-gabarap-demo --yes`

## 2) Protein Design (`protein-design`, BoltzProt-1 pipeline)

### Example A — AMBP-style custom binder generation

User prompt:
- "Show me a minimal BoltzProt-style de novo binder design run for an AMBP-like target."

`payload.protein.design.ambp.min.yaml`
```yaml
# target context: AMBP, UniProt P02760, residues 1-90
target:
  type: no_template
  entities:
    - type: protein
      value: MRSLGALLLLLSACLAVSAGPVPTPPDNIQVQENFNISRIYGKWYNLAIGSTCPWLKKIMDRMTVSTLVLGEGATEAEISMTSTRWRKGV
      chain_ids: ["A"]
  epitope_residues:
    A: [10, 11, 12]
binder_specification:
  type: no_template
  modality: custom_protein
  entities:
    - type: designed_protein
      chain_ids: ["B"]
      value: "10..14"
num_proteins: 10
```

Commands:
- `python scripts/run.py protein-design --payload payload.protein.design.ambp.min.yaml --run-name pd-ambp-demo --estimate-only`
- `python scripts/run.py protein-design --payload payload.protein.design.ambp.min.yaml --run-name pd-ambp-demo --yes`

### Example B — MZB1-style curated nanobody flow

User prompt:
- "Give me a tiny MZB1-style nanobody-focused design example."

`payload.protein.design.mzb1.nanobody.yaml`
```yaml
# target context: MZB1, UniProt Q8WU39, residues 1-90
target:
  type: no_template
  entities:
    - type: protein
      value: MRLSLPLLLLLLGAWAIPGGLGDRAPLTATAPQLDDEEMYSAHMPAHLRCDACRAVAYQMWQNLAKAETKLHTSNSGGRRELSELVYTDV
      chain_ids: ["A"]
  epitope_residues:
    A: [10, 11, 12]
binder_specification:
  type: boltz_curated
  modality: nanobody
  binder: boltz_nanobody
num_proteins: 10
```

Commands:
- `python scripts/run.py protein-design --payload payload.protein.design.mzb1.nanobody.yaml --run-name pd-mzb1-nb-demo --estimate-only`
- `python scripts/run.py protein-design --payload payload.protein.design.mzb1.nanobody.yaml --run-name pd-mzb1-nb-demo --yes`

## 3) Protein Library Screen (`protein-screen`, BoltzProt-1 pipeline)

### Example A — IDI2-style protein library screen

User prompt:
- "Screen my two protein binders against an IDI2-style target."

`payload.protein.screen.idi2.min.yaml`
```yaml
# target context: IDI2, UniProt Q9BXS1, residues 1-90
target:
  type: no_template
  entities:
    - type: protein
      value: MSDINLDWVDRRQLQRLEEMLIVVDENDKVIGADTKRNCHLNENIEKGLLHRAFSVVLFNTKNRILIQQRSDTKVTFPGYFTDSCSSHPL
      chain_ids: ["A"]
  epitope_residues:
    A: [10, 11, 12]
proteins:
  - id: binder-001
    entities:
      - type: protein
        value: MKTAYIVKSHFSRQ
        chain_ids: ["B"]
  - id: binder-002
    entities:
      - type: protein
        value: ACDEFGHIKLMNPQRSTVWY
        chain_ids: ["B"]
```

Commands:
- `python scripts/run.py protein-screen --payload payload.protein.screen.idi2.min.yaml --run-name ps-idi2-demo --estimate-only`
- `python scripts/run.py protein-screen --payload payload.protein.screen.idi2.min.yaml --run-name ps-idi2-demo --yes`

### Example B — PMVK-style non-binding patch guardrail

User prompt:
- "Screen a small binder set for PMVK and avoid one specific target patch."

`payload.protein.screen.pmvk.nonbinding.yaml`
```yaml
# target context: PMVK, UniProt Q15126, residues 1-90
target:
  type: no_template
  entities:
    - type: protein
      value: MAPLGGAPRLVLLFSGKRKSGKDFVTEALQSRLGADVCAVLRLSGPLKEQYAQEHGLNFQRLLDTSTYKEAFRKDMIRWGEEKRQADPGF
      chain_ids: ["A"]
  epitope_residues:
    A: [10, 11, 12]
  non_binding_residues:
    A: [0, 1, 2]
proteins:
  - id: binder-001
    entities:
      - type: protein
        value: MKTAYIVKSHFSRQ
        chain_ids: ["B"]
```

Commands:
- `python scripts/run.py protein-screen --payload payload.protein.screen.pmvk.nonbinding.yaml --run-name ps-pmvk-nonbinding-demo --estimate-only`
- `python scripts/run.py protein-screen --payload payload.protein.screen.pmvk.nonbinding.yaml --run-name ps-pmvk-nonbinding-demo --yes`

## 4) Small-Molecule Design (`sm-design`, BoltzMol-1 pipeline)

### Example A — ROR1-style small-molecule design starter

User prompt:
- "Generate a tiny ROR1-style molecule set for this pocket."

`payload.sm.design.ror1.min.yaml`
```yaml
# target context: ROR1, UniProt Q01973, residues 1-90
target:
  entities:
    - type: protein
      value: MHRPRRRGTRPPLLALLAALLLAARGAAAQETELSVSAELVPTSSWNISSELNKDSYLTLDEPMNNITTSLGQTAELHCKVSGNPPPTIR
      chain_ids: ["A"]
  pocket_residues:
    A: [2, 3, 4, 7, 8, 9]
num_molecules: 10
```

Commands:
- `python scripts/run.py sm-design --payload payload.sm.design.ror1.min.yaml --run-name smd-ror1-demo --estimate-only`
- `python scripts/run.py sm-design --payload payload.sm.design.ror1.min.yaml --run-name smd-ror1-demo --yes`

### Example B — MRGPRX2-style filtered generation

User prompt:
- "Generate MRGPRX2-style starter molecules with simple drug-like filters."

`payload.sm.design.mrgprx2.filters.yaml`
```yaml
# target context: MRGPRX2, UniProt Q96LB1, residues 1-101
target:
  entities:
    - type: protein
      value: MDPTTPAWGTESTTVNGNDQALLLLCGKETLIPVFLILFIALVGLVGNGFVLWLLGFRMRRNAFSVYVLSLAGADFLFLCFQIINCLVYLSNFFCSISINF
      chain_ids: ["A"]
  pocket_residues:
    A: [2, 3, 4, 7, 8, 9]
molecule_filters:
  boltz_smarts_catalog_filter_level: recommended
  custom_filters:
    - type: lipinski_filter
      max_mw: 500
      max_logp: 5
      max_hbd: 5
      max_hba: 10
num_molecules: 10
```

Commands:
- `python scripts/run.py sm-design --payload payload.sm.design.mrgprx2.filters.yaml --run-name smd-mrgprx2-filters-demo --estimate-only`
- `python scripts/run.py sm-design --payload payload.sm.design.mrgprx2.filters.yaml --run-name smd-mrgprx2-filters-demo --yes`

## 5) Small-Molecule Library Screen (`sm-screen`, BoltzMol-1 pipeline)

### Example A — PknB-style screen with known molecules

User prompt:
- "Screen aspirin, ibuprofen, and caffeine against a PknB-style target."

`payload.sm.screen.pknb.min.yaml`
```yaml
# target context: PknB (M. tuberculosis H37Rv), UniProt P9WI81, residues 1-90
target:
  entities:
    - type: protein
      value: MTTPSHLSDRYELGEILGFGGMSEVHLARDLRLHRDVAVKVLRADLARDPSFYLRFRREAQNAAALNHPAIVAVYDTGEAETPAGPLPYI
      chain_ids: ["A"]
molecules:
  - smiles: CC(=O)OC1=CC=CC=C1C(=O)O
    id: aspirin
  - smiles: CC(C)Cc1ccc(cc1)C(C)C(=O)O
    id: ibuprofen
  - smiles: CN1C=NC2=C1C(=O)N(C(=O)N2C)C
    id: caffeine
```

Commands:
- `python scripts/run.py sm-screen --payload payload.sm.screen.pknb.min.yaml --run-name sms-pknb-demo --estimate-only`
- `python scripts/run.py sm-screen --payload payload.sm.screen.pknb.min.yaml --run-name sms-pknb-demo --yes`

### Example B — GLP2R-style screening with extra filters

User prompt:
- "Screen a small GLP2R-style library and apply stricter alert filtering."

`payload.sm.screen.glp2r.filters.yaml`
```yaml
# target context: GLP2R, UniProt O95838, residues 1-90
target:
  entities:
    - type: protein
      value: MKLGSSRAGPGRGSAGLLPGVHELPMGIPAPWGTSPLSFHRKCSLWAPGRPFLTLVLLVSIKQVTGSLLEETTRKWAQYKQACLRDLLKE
      chain_ids: ["A"]
molecules:
  - smiles: CC(=O)OC1=CC=CC=C1C(=O)O
    id: aspirin
  - smiles: C1=CC=C(C=C1)O
    id: phenol
molecule_filters:
  boltz_smarts_catalog_filter_level: extra
```

Commands:
- `python scripts/run.py sm-screen --payload payload.sm.screen.glp2r.filters.yaml --run-name sms-glp2r-filters-demo --estimate-only`
- `python scripts/run.py sm-screen --payload payload.sm.screen.glp2r.filters.yaml --run-name sms-glp2r-filters-demo --yes`

## 6) ADME (`adme`)

### Example A — ADME triage for known oral drugs

User prompt:
- "Predict ADME for aspirin and ibuprofen (quick triage)."

`payload.adme.min.yaml`
```yaml
molecules:
  - smiles: CC(=O)OC1=CC=CC=C1C(=O)O
    id: aspirin
  - smiles: CC(C)Cc1ccc(cc1)C(C)C(=O)O
    id: ibuprofen
```

Commands:
- `python scripts/run.py adme --payload payload.adme.min.yaml --run-name adme-min-demo --estimate-only`
- `python scripts/run.py adme --payload payload.adme.min.yaml --run-name adme-min-demo --yes`

### Example B — four-molecule ADME triage panel

User prompt:
- "Run a tiny ADME triage batch for aspirin, ibuprofen, phenol, and caffeine."

`payload.adme.batch.yaml`
```yaml
molecules:
  - smiles: CC(=O)OC1=CC=CC=C1C(=O)O
    id: aspirin
  - smiles: CC(C)Cc1ccc(cc1)C(C)C(=O)O
    id: ibuprofen
  - smiles: C1=CC=C(C=C1)O
    id: phenol
  - smiles: CN1C=NC2=C1C(=O)N(C(=O)N2C)C
    id: caffeine
```

Commands:
- `python scripts/run.py adme --payload payload.adme.batch.yaml --run-name adme-batch-demo --estimate-only`
- `python scripts/run.py adme --payload payload.adme.batch.yaml --run-name adme-batch-demo --yes`

## 7) Status / Recovery / Stop (`status`)

### Example A — retrieve + resume by job ID

User prompt:
- "Recover results for this existing job id."

Commands:
- `python scripts/run.py status --action retrieve --resource sm_screen --job-id <job-id>`
- `python scripts/run.py status --action resume --job-id <job-id> --run-name sms-pknb-demo`

### Example B — stop a running design/screen

User prompt:
- "Stop this running screen now and keep partial outputs."

Commands:
- `python scripts/run.py status --action stop --resource sm_design --job-id <job-id>`
- `python scripts/run.py status --action stop --resource protein_screen --job-id <job-id>`
