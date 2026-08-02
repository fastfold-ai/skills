# Fold payload examples

Read this when constructing a Jobs API body. Field-name traps stay in `SKILL.md`.

## Contents

- Boltz-2 affinity (CCD / SMILES) and single protein
- OpenFold 3 protein–ligand and modifications
- Boltz-2 pocket constraint
- AlphaFold2 monomer / multimer
- ESMFold (`esm1b`) vs ESMFold2 (Biohub)
- Native Nesso-1 (affinity only)
- Structure parent + Nesso webhook (`on_start`)

### Boltz-2 with affinity prediction (CCD ligand)

```json
{
  "name": "Boltz-2 Affinity Job",
  "isPublic": false,
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQGVDDAFYTLVREIRKHKE",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "U4U",
        "is_ccd": true,
        "property_type": "affinity",
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "boltz-2"
  }
}
```

Key points:
- `property_type: "affinity"` goes on the **ligandSequence**, not in params
- `is_ccd: true` marks a CCD code; omit for SMILES strings
- `modelName` is the correct field name (not `model`)

### Boltz-2 with affinity prediction (SMILES ligand)

```json
{
  "name": "Boltz-2 Affinity SMILES",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIGCTLNF",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "CC1CN(CC(C1)NC(=O)C2=CC=CC=C2N)C(=O)NC(C)(C)C",
        "property_type": "affinity",
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "boltz-2"
  }
}
```

### Boltz-2 single protein (no ligand)

```json
{
  "name": "Simple Boltz-2 Fold",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPK",
        "chain_id": "A"
      }
    }
  ],
  "params": {
    "modelName": "boltz-2"
  }
}
```

### OpenFold 3 — protein and CCD ligand

Use `modelName` **`openfold3`** (all lowercase). Tune diffusion sampling and seeds; do **not** use Boltz-only affinity params here.

```json
{
  "name": "OpenFold 3 protein–ligand",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQGVDDAFYTLVREIRKHKE",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "ATP",
        "is_ccd": true,
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "openfold3",
    "diffusionSample": 5,
    "numModelSeeds": 1
  }
}
```

### OpenFold 3 — non-canonical residue (modification)

`modifications` is an array of `{ "res_idx": <1-based index>, "ccd": "<CCD code>" }` on **protein**, **RNA**, or **DNA** chains.

```json
{
  "name": "OpenFold 3 PTM example",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
        "chain_id": "A",
        "modifications": [{ "res_idx": 5, "ccd": "SEP" }]
      }
    }
  ],
  "params": {
    "modelName": "openfold3",
    "diffusionSample": 5,
    "numModelSeeds": 2
  }
}
```

### Boltz-2 with pocket constraint

```json
{
  "name": "Streptococcal protein G with Pocket",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MTYKLILNGKTLKGETTTEAVDAATAEKVFKQYANDNGVDGEWTYDDATKTFTVTE",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "ATP",
        "is_ccd": true,
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "boltz-2"
  },
  "constraints": {
    "pocket": [
      {
        "binder": { "chain_id": "B" },
        "contacts": [
          { "chain_id": "A", "res_idx": 12 },
          { "chain_id": "A", "res_idx": 15 },
          { "chain_id": "A", "res_idx": 18 }
        ]
      }
    ]
  }
}
```

### Monomer (AlphaFold2)

```json
{
  "name": "Monomer fold",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MGLSDGEWQLVLNVWGKVEADIPGHGQEVLIRLFKGHPETLERFDKFKHLK",
        "chain_id": "A"
      }
    }
  ],
  "params": {
    "modelName": "monomer"
  }
}
```

### Multimer (AlphaFold2)

```json
{
  "name": "Multimer fold",
  "sequences": [
    { "proteinChain": { "sequence": "MCNTNMSVSTEGAASTSQIP...", "chain_id": "A" } },
    { "proteinChain": { "sequence": "SQETFSGLWKLLPPE", "chain_id": "B" } }
  ],
  "params": {
    "modelName": "multimer"
  }
}
```

### ESMFold (`esm1b`)

Legacy Meta ESMFold (ESM-1b embeddings). Whenever the user says **"ESM-1b"** specifically, use `modelName: "esm1b"`. For **"ESMFold2"** / Biohub, use the ESMFold2 section below — do not silently substitute `esm1b`.

```json
{
  "name": "ESMFold monomer",
  "sequences": [
    { "proteinChain": { "sequence": "MGLSDGEWQLVLNVWGKVEADIPGHGQEVLIRLFKGHPETLERFDKFKHLK...", "chain_id": "A" } }
  ],
  "params": {
    "modelName": "esm1b"
  }
}
```

### ESMFold2 (Biohub)

ESMFold2 is Biohub’s all-atom structure predictor (proteins, DNA, RNA, ligands). Use exact weight-set strings:

| User says | `modelName` |
|---|---|
| ESMFold2 fast / default | `esmfold2-fast-2026-05` |
| ESMFold2 full | `esmfold2-2026-05` |

UI defaults map to `recyclingSteps` (loops, default 10), `samplingSteps` (100), `diffusionSample` (1).

```json
{
  "name": "ESMFold2 complex",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQGVDDAFYTLVREIRKHKE",
        "chain_id": "A"
      }
    },
    {
      "rnaSequence": {
        "sequence": "GGGGGCATGCAGATCCCACAGGCGCG",
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "esmfold2-fast-2026-05",
    "recyclingSteps": 10,
    "samplingSteps": 100,
    "diffusionSample": 1
  }
}
```

### Nesso-1 (native affinity job)

Nesso-1 (Recursion) is an **affinity-only** model: it returns binding metrics (`affinity_result_raw_json`), **not** a folded structure. Do **not** expect CIF/PDB, PAE/pLDDT plots, or a structure viewer from a native `nesso` job.

Submit as a fold job with `modelName: "nesso"`, one protein + one ligand (`property_type: "affinity"`), and optional `recyclingSteps` (default 5). If the user also needs a structure, use a structure model (Boltz-2 / OpenFold 3 / ESMFold2 / …) and attach the Nesso webhook (below) — or run a separate structure job.

```json
{
  "name": "Nesso-1 affinity",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIGCTLNF",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "CC1CN(CC(C1)NC(=O)C2=CC=CC=C2N)C(=O)NC(C)(C)C",
        "property_type": "affinity",
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "nesso",
    "recyclingSteps": 5
  }
}
```

### Boltz-2 / OpenFold 3 / ESMFold2 with Nesso affinity webhook (`on_start`)

Attach Nesso to a structure fold that already has protein + ligand. Structure stays on the parent model; affinity merges from the Nesso child.

```json
{
  "name": "Boltz-2 + Nesso affinity webhook",
  "sequences": [
    {
      "proteinChain": {
        "sequence": "PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIGCTLNF",
        "chain_id": "A"
      }
    },
    {
      "ligandSequence": {
        "sequence": "U4U",
        "is_ccd": true,
        "chain_id": "B"
      }
    }
  ],
  "params": {
    "modelName": "boltz-2"
  },
  "constraints": {
    "webhooks": {
      "nesso": {
        "enabled": true,
        "event": "on_start",
        "protein_chain_id": "A",
        "ligand_chain_id": "B",
        "recycling_steps": 5
      }
    }
  }
}
```

Then: `python scripts/wait_for_nesso_linked.py <job_id> --json`
