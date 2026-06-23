# Changelog

All notable changes to the Fastfold AI Skills catalog are documented here.

This catalog is versioned as a whole (one release tag per catalog version).
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the catalog adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-06-22

### Changed

- Made `skills/boltz` runtime-aware: results go to a project-relative output dir
  (`${OUTPUT_DIR:-./outputs}/boltz`) on local agents (Fastfold Agent CLI, Claude Code, Codex, Cursor),
  and to the S3-backed `/workspace` via `scripts/persist.sh` only on hosted sandboxes. Updated
  `SKILL.md` and references (`api.md`, `results.md`, `examples.md`); `persist.sh` is now marked
  hosted-sandbox-only.
- Rewrote `README.md`: clearer positioning, a compute-providers/API-keys inventory
  (`FASTFOLD_API_KEY` for Fastfold Cloud, `BOLTZ_API_KEY` for the Boltz API), `BOLTZ_API_KEY` setup,
  and links to the skills and Agent CLI docs.

## [1.1.0] - 2026-06-22

### Changed
- Reworked `skills/boltz` to drive the official `boltz-api` CLI directly instead of a bundled runner.
  Rewrote `SKILL.md` around a mode→resource table, three guardrails (estimate→confirm before billing;
  persist to the S3-backed `/workspace`; recover from the API without re-submitting), and a raw-CLI cheat-sheet.
- Simplified `skills/boltz/references` (`api.md`, `results.md`, `examples.md`) to use raw `boltz-api` commands.

### Added
- `skills/boltz/scripts/persist.sh`: S3-safe copy of a finished run directory from
  `/tmp/boltz-runs/<slug>` to `/workspace/boltz-artifacts/boltz/<slug>/` (the `/workspace` mount is not
  a full POSIX filesystem, so the CLI cannot download into it directly).

### Removed
- `skills/boltz/scripts/run.py` (the end-to-end runner wrapper). Workflows now use the `boltz-api` CLI
  directly plus `persist.sh`.

## [1.0.6] - 2026-06-22

### Changed

- Generalized `skills/boltz/SKILL.md` CLI bootstrap wording to be runtime-agnostic (no product-specific install references).

## [1.0.5] - 2026-06-22

### Changed

- `skills/boltz/scripts/run.py` now auto-installs `boltz-api` with the official Boltz
  installer (`curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`) when
  the CLI is missing, matching Modal sandbox and Fastfold Agent CLI bootstrap behavior.
- Updated `skills/boltz/SKILL.md` and catalog README to require bundled-runner bootstrap
  instead of manual/pip CLI installation.

## [1.0.4] - 2026-06-20

### Added
- Added `skills/boltz/references/examples.md` with 1-2 small, copy-paste examples per Boltz mode (`sab`, protein design/screen, small-molecule design/screen, `adme`, status/recovery/stop), including user prompt phrasing and runnable commands.
- Added Boltz quick example prompts and examples-reference links to the catalog `README.md`.

### Changed
- Upgraded Boltz examples to use real UniProt-backed target sequence fragments (with accession and residue ranges) and known small molecules for auditable quick runs.
- Extended unified Boltz runner with `status --action stop` support for design/screen jobs.
- Simplified `skills/boltz/references/api.md` to focus on API contract/mapping (removed non-contract launch/report links).

## [1.0.3] - 2026-06-20

### Changed
- Updated `skills/boltz/SKILL.md` authentication guidance to be runtime-agnostic: accepts env injection or local `.env`/shell env usage for `BOLTZ_API_KEY`, with Fastfold Cloud setup as an optional path.

## [1.0.2] - 2026-06-20

### Added
- New unified skill: `boltz` for direct Boltz API workflows (structure-and-binding, protein/small-molecule design and screen, ADME, status/recovery) with one end-to-end runner.

### Changed
- Standardized Boltz skill runtime behavior for deterministic execution on Modal sandboxes: tmp-first downloads/checkpoints (`/tmp/boltz-runs`) with persistence mirror to `/workspace/boltz-artifacts/boltz/<run_dir_name>/`.
- Added first-party Boltz API endpoint reference mapping and updated skill guidance for `BOLTZ_API_KEY` setup + sandbox restart flow.

## [1.0.1] - 2026-06-18

### Added
- New skill: `diagrams_mermaid` for on-demand and proactive Mermaid diagram generation, including workflow templates for computational biology pipelines.

## [1.0.0] - 2026-06-18

### Added
- Initial versioned release of the Fastfold AI Skills catalog.
- Skills: `fold`, `protein_design_boltzgen`, `md_openmm_calvados`, `md_openmmdl`, `slack_report`.

[Unreleased]: https://github.com/fastfold-ai/skills/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/fastfold-ai/skills/releases/tag/v1.1.1
[1.1.0]: https://github.com/fastfold-ai/skills/releases/tag/v1.1.0
[1.0.6]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.6
[1.0.5]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.5
[1.0.4]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.4
[1.0.3]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.3
[1.0.2]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.2
[1.0.1]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/fastfold-ai/skills/releases/tag/v1.0.0
