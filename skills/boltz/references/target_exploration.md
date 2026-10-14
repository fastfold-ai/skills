# Target Exploration — scouting before a full design run

Read this when the user opts into a target-exploration pass from the protein
design flow (`protein:design`). It scouts a few cheap framings of the *target*,
picks the one that actually yields binders, and hands back a chosen
configuration (crop + optional epitope) plus a recommended `num_proteins` for
the full campaign.

Skip it entirely when the user already knows their binding site and crop — go
straight to authoring the payload.

The axes frame the **target**, so they apply to every binder modality
(peptide, miniprotein, nanobody, antibody) alike.

## Why bother

De novo design is generate-and-filter: a full campaign costs real money, and
the yield of good binders depends heavily on what the model is shown. Unmodeled
terminal residues add floppy overhang that hurts designs. Binders frequently
dock somewhere other than the site you intended. Crop and epitope indices are
easy to misread by one. A handful of 50-design scouting runs surfaces all three
problems for a small fraction of the full-run cost.

## Mental model: sample the axes, don't cross-product them

Each axis changes which target residues the model sees, or whether generation is
conditioned on a specified site. Treat the pass as an interactive discussion —
the user often has domain knowledge about their target.

Do **not** run the full Cartesian product; that blows up combinatorially.

- **Categorical axes** (domain, site-specified-or-not): scout the whole axis.
- **Multi-valued axes** (crop radius): pick two values, not five, unless the
  user asks for more.
- Trim the termini **before** any other axis — that one is not optional.

| Axis | What it varies | How to vary it |
|---|---|---|
| **Termini** (always) | Drops unresolved N/C overhang | First/last resolved residue |
| **Disorder cutout** | Removes internal disordered stretches | Drop low-confidence / unresolved internal loops |
| **Crop radius** | Keeps only residues near the site | Sample ~2 of 10/15/25/30/35 Å |
| **Site specified or not** | Conditions on the epitope, or lets the binder find its own | Include / omit `epitope_residues` |
| **Domain** | Full target vs. one domain at a time | CATH / Pfam domain boundaries |
| **Scan** (>300 aa **and** unknown site) | Discovers where binders actually land | Unconditioned runs, then cluster where binders docked |

## Indexing contract — read before cropping

Every residue index in the payload (`crop_residues`, `epitope_residues`,
`flexible_residues`, `non_binding_residues`, constraints, modifications, bonds)
is **0-based**.

Map from the structure with `API index = canonical label_seq_id − 1`. Read
`label_seq` from the CIF, **not** author numbering (`auth_seq_id`) — author
numbering carries arbitrary offsets and gaps, and mixing the two is the most
common source of a run that silently designs against the wrong patch.

Spot-check one or two mapped indices against the target sequence before
submitting.

## Step 0 — what is the binder for?

Establish briefly what the user wants the binder to *do*: block a specific
interaction, serve as a research or diagnostic reagent, or just be any tractable
binder. This shapes which sites and domains are worth scouting, whether to
specify a site at all, and how to weigh the winner later — a highly designable
but off-purpose site may not be what they want. Carry the answer through to the
winner discussion in step 4.

## Step 1 — trim unresolved termini (always)

Never include leading or trailing residues that are unresolved in the structure.
Start the crop at the first resolved `label_seq` and end it at the last, then
express that range as 0-based indices in `crop_residues`. This applies to the
baseline and to every crop variant below.

Internal unresolved residues are a separate axis (disorder cutout), not part of
this step.

## Step 2 — choose the axes to scout

Cover each axis that applies to this target; don't pre-judge the winner. Typical
selections:

- Unknown site, single compact domain → termini + site-vs-no-site + 2 crop radii.
- Multi-domain target → termini + one config per domain.
- Large target (>300 aa) with no known site → add a scan pass first, then crop
  around whatever patch the scan favours.
- Known, well-characterized site → often just two configs: epitope-conditioned
  vs. unconditioned.

## Step 3 — scout with 50 designs per config

Run each config as its own `protein:design` job with `num_proteins: 50`.

- Reuse one slug family so the runs stay traceable, e.g.
  `pd-<target>-explore-<axis><value>`.
- `estimate-cost` each config and show the user the total across all configs
  before submitting any of them. The spending gate applies here exactly as it
  does to a full run.
- Keep every other payload field identical across configs — the whole point is
  that only the framing varies.

## Step 4 — pick the winner

Rank each config by its **maximum** `binding_confidence`, not its mean: a
campaign keeps the rare good binders, so the best design a framing can produce
matters more than its average.

Use `iptm` (higher better) and `min_interaction_pae` (lower better) as
tiebreakers. Present the comparison to the user alongside the goal from step 0
before committing — a config that wins numerically but binds the wrong face is
not the winner.

## Step 5 — size and submit the full run

Scouting yield informs the tier. Roughly:

- Several strong hits in 50 designs → the standard tier works (see Run sizing in
  SKILL.md; default 50,000).
- Weak or borderline yield across every config → raise the tier, revisit the
  framing, or discuss whether the target is tractable before spending more.

Re-run `estimate-cost` on the chosen tier and take a fresh approval. An earlier
approval for scouting is **not** approval for the full run.

## Step 6 — post-run readout

After the campaign downloads, report the yield honestly: how many designs
cleared a useful `binding_confidence` threshold, and how that compares to the
scouting run that predicted it. That number is what calibrates the next campaign
against this target.

---

Adapted from the target-exploration guidance in
[boltz-bio/boltz-api-skills](https://github.com/boltz-bio/boltz-api-skills)
(MIT). Upstream ships `gemmi`/`numpy` helper scripts for the geometry steps;
this catalog keeps references dependency-free, so the steps above are performed
inline or with the user's own tooling.
