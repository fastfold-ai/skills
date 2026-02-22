# AGENTS.md

This file provides guidance to AI coding agents (Claude, Cursor, Copilot, etc.) when working with code in this repository.

## Repository Overview

A collection of agent skills for working with the **FastFold Jobs API** (protein folding). Skills are packaged instructions and scripts that extend the agent’s capabilities—e.g. creating fold jobs, waiting for completion, fetching CIF/PDB results, metrics, and viewer links.

- Skills live in the **`skills/`** folder.
- Each skill is self-contained: `SKILL.md`, optional `scripts/`, `references/`, and `assets/`.
- Install for users: `npx skills add fastfold-ai/skills`.

## Creating a New Skill

### Directory Structure

```
skills/
  {skill-name}/              # kebab-case directory name
    SKILL.md                 # Required: skill definition and instructions
    scripts/                 # Optional: executable helpers (Python preferred)
      {script-name}.py
    references/              # Optional: API refs, OpenAPI schemas, guides
      api_ref.md
      jobs.yaml              # e.g. OpenAPI spec for FastFold Jobs API
    assets/                  # Optional: templates, images (not loaded into context)
```

### Naming Conventions

- **Skill directory:** `kebab-case` (e.g. `fold`, `my-api-skill`)
- **SKILL.md:** Always this exact filename (uppercase, `.md`)
- **Scripts:** `snake_case.py` or `kebab-case.sh` (e.g. `wait_for_completion.py`, `fetch_results.py`)
- **References:** Place API schemas (e.g. OpenAPI YAML) and long docs in `references/` so SKILL.md stays short

### SKILL.md Format

```markdown
---
name: {skill-name}
description: {One sentence: what the skill does and when to use it. Include trigger phrases so the agent knows when to activate.}
---

# {Skill Title}

## Overview
{Brief description. Mention API/schema location if relevant (e.g. references/jobs.yaml).}

## Authentication
{If the skill calls an API: how to get and set the key (e.g. dashboard link), env var name, and that the agent must not continue without the key until the user confirms it is set.}

## When to Use This Skill
- User wants to …
- User mentions …
- User needs to script: …

## Workflow
0. Ensure API key is set (if required) — ask user if missing; do not proceed until confirmed.
1. Step one (e.g. Create job)
2. Step two (e.g. Wait for completion)
3. Step three (e.g. Fetch results)

**Scripts:** Prefer bundled scripts. Document each with a one-line purpose and example:
- `python scripts/script_name.py <args> [--base-url URL]`

## Complex vs Simple Cases
{If the API has different result shapes (e.g. complex vs non-complex jobs), explain how to read results and which script handles each.}

## Resources
- [references/foo.md](references/foo.md)
- [references/schema.yaml](references/schema.yaml)
```

### Best Practices for Context Efficiency

Skills are loaded on-demand: name and description first; full `SKILL.md` when the skill is relevant. To minimize context usage:

- **Keep SKILL.md under 500 lines** — put detailed API docs, schemas, and long guides in `references/`
- **Write specific descriptions** — include trigger phrases (e.g. “FastFold API”, “fold job”, “CIF results”) so the agent activates the skill only when appropriate
- **Use progressive disclosure** — link from SKILL.md to `references/` files; the agent reads those only when needed
- **Prefer scripts over inline code** — script execution doesn’t consume context (only output does); use Python or bash in `scripts/`
- **File references one level deep** — link directly from SKILL.md to files in `references/` or `scripts/`; avoid deep nesting
- **Self-contained skills** — bundle the OpenAPI/schema in the skill (e.g. `references/jobs.yaml`) so the skill does not depend on the project root

### Script Requirements

- **Python:** Use `#!/usr/bin/env python3`; prefer `argparse` for CLI args; read API key from env (e.g. `os.environ.get("FASTFOLD_API_KEY")`) and avoid CLI secret flags.
- **Output:** Write status/progress to stderr (e.g. `print("...", file=sys.stderr)`); write machine-readable result (e.g. JSON or URLs) to stdout so the agent can use it.
- **Errors:** Exit non-zero on failure; print a clear message to stderr (e.g. “Error: Unauthorized. Check FASTFOLD_API_KEY.”).
- **Paths:** Scripts are run from the skill directory or project root; use paths relative to the skill (e.g. `scripts/script_name.py` or `references/jobs.yaml` when documenting).

### Packaging (Optional)

For distribution as a single artifact:

- **Zip:** From repo root: `zip -r skills/{skill-name}.zip skills/{skill-name}/`
- **Skill packager:** If using the skill-creator tooling (e.g. in `.agents/skills/skill-creator/`), run `package_skill.py` on the skill folder to produce a `.skill` file.

### End-User Installation

Document these installation methods for users:

**Via Skills CLI (recommended):**
```bash
npx skills add fastfold-ai/skills
```

**Cursor (project or user scope):**
```bash
cp -r skills/{skill-name} .cursor/skills/
# or
cp -r skills/{skill-name} ~/.cursor/skills/
```

**API key (for skills that call FastFold):**  
Users must set `FASTFOLD_API_KEY` (preferably in a local `.env`). The agent should ask the user to create/set the key before continuing if it is missing.
