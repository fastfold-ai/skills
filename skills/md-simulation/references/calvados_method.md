# CALVADOS method reference

Use this file when a user asks about the **method** behind the MD simulation (what CALVADOS is, residue-level model, force field choices, parameter families like CALVADOS2 vs CALVADOS3, use-cases like IDPs / multi-domain proteins / slabs).

## What CALVADOS is

- **CALVADOS** (**C**oarse-grained **A**pproach to **L**iquid-liquid phase separation **V**ia an **A**miono acid-specific **DO**wnscaled **S**imulator) is a coarse-grained, one-bead-per-residue implicit-solvent protein model designed for intrinsically disordered proteins (IDPs) and multi-domain proteins, including phase-behavior / slab simulations.
- In this skill, CALVADOS is used as the **force field** for MD runs executed in the **OpenMM** framework, wrapped behind the FastFold `calvados_openmm_v1` workflow.

## Primary references

- **Paper (software package, 2025):** S. von Bülow, Y. Yasuda, F. Cao, T. K. Schulze, A. I. Trolle, A. S. Rauh, R. Crehuet, K. Lindorff-Larsen, G. Tesei. *Software package for simulations using the coarse-grained CALVADOS model*. arXiv:2504.10408 (2025).
  - HTML: https://arxiv.org/html/2504.10408v1
  - PDF / abstract: https://arxiv.org/abs/2504.10408
- **Upstream source code (KULL-Centre/CALVADOS):** https://github.com/KULL-Centre/CALVADOS/tree/main
- **Original CALVADOS (2021):** G. Tesei, T. K. Schulze, R. Crehuet, K. Lindorff-Larsen. *Accurate model of liquid-liquid phase behavior of intrinsically disordered proteins from optimization of single-chain properties.* PNAS 118(44):e2111696118. https://doi.org/10.1073/pnas.2111696118
- **CALVADOS 2 (2022):** G. Tesei, K. Lindorff-Larsen. *Improved predictions of phase behaviour of intrinsically disordered proteins by tuning the interaction range.* Open Research Europe 2:94. https://doi.org/10.12688/openreseurope.14967.2
- **CALVADOS 3 / multi-domain (2024):** F. Cao, S. von Bülow, G. Tesei, K. Lindorff-Larsen. *A coarse-grained model for disordered and multi-domain proteins.* Protein Science 33(11):e5172. https://doi.org/10.1002/pro.5172

## Residue profiles in this skill

The `workflow_input.residue_profile` field maps to a residue parameter set from the CALVADOS family:

- `calvados2` — CALVADOS 2 parameters (Tesei & Lindorff-Larsen, 2022).
- `calvados3` — CALVADOS 3 parameters, improved for multi-domain proteins (Cao et al., 2024). Default in this skill.
- `c2rna` — CALVADOS-compatible parameters for RNA.

Pick `calvados3` unless the user has a specific reason to use `calvados2` or work with RNA (`c2rna`).

## Citation guidance for the agent

- When the user asks "what model is this?" / "what force field is this?" / "how does CALVADOS work?", answer briefly (coarse-grained, 1 bead/residue, implicit solvent, residue-type-specific interactions) and **link to arXiv 2504.10408 and the GitHub repo**.
- When the user plans to publish, tell them the correct citation set is:
  - the 2025 software paper (arXiv:2504.10408),
  - plus the CALVADOS version they used (`calvados2` → Tesei 2022; `calvados3` → Cao 2024).
- Do not claim implementation details that are not in these references or in the FastFold workflow code.

## Not covered by this skill

- Training/fitting new CALVADOS parameters.
- Slab / multi-chain / phase-behavior setups beyond the `single_af_go` AF+PAE preset.
- Non-CALVADOS force fields.

If a user wants those, tell them to contact the Fastfold team for support at [hello@fastfold.ai](mailto:hello@fastfold.ai).
