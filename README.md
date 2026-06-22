# Fastfold AI Skills

A collection of skills for AI agents. Skills are packaged instructions and scripts that extend agent capabilities for the FastFold Cloud APIs (folding, protein design, molecular dynamics, reporting).

Skills follow the [Agent Skills](https://agentskills.io/) format. Each skill is self-contained and portable: its scripts use only the Python standard library and are invoked directly as `python scripts/<name>.py ...` from the skill directory, so they run consistently wherever the skill is installed.

Browse the skills catalog in Fastfold Cloud: [cloud.fastfold.ai/agents/skills](https://cloud.fastfold.ai/agents/skills).

## Install

Install all skills with the Skills CLI (Node/`npx`):

```bash
npx skills add fastfold-ai/skills
```

Or with the Fastfold Agent CLI (native, no Node required):

```bash
fastfold skills add fastfold-ai/skills                      # all skills
fastfold skills add fastfold-ai/skills@skills/fold          # a single skill
```

These are the same catalog skills used by the [Fastfold Agent CLI](https://github.com/fastfold-ai/fastfold-agent-cli). See:
- Skills docs: [docs.fastfold.ai/agents/skills](https://docs.fastfold.ai/agents/skills)
- Use skills with the Fastfold Agent CLI: [docs.fastfold.ai/agents/cli](https://docs.fastfold.ai/agents/cli)

## Usage

Once installed, the agent uses a skill when the task matches its description and “Use when” triggers.

**Example:**

With `.env` set up (or `FASTFOLD_API_KEY` exported), run scripts without passing the key each time. Your agent can help you set this up—see [Setting your FastFold API key](#setting-your-fastfold-api-key) below. 


Just Ask:

```
Use Boltz-2 in Fastfold with affinity property to the ligand. Fold this protein: PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIGCTLNF and this ligand: CC1CN(CC(C1)NC(=O)C2=CC=CC=C2N)C(=O)NC(C)(C)C
```


## Available Skills

Skills in this repo live in the **`skills/`** folder.

| Skill | Primary use |
|---|---|
| `boltz` | Direct Boltz API workflows (SAB, protein/small-molecule design/screen, ADME, status/recovery) |
| `fold` | FastFold Jobs API submission, waiting, and result retrieval |
| `protein_design_boltzgen` | BoltzGen protein design workflow orchestration |
| `md_openmm_calvados` | CALVADOS + OpenMM molecular dynamics workflows |
| `md_openmmdl` | OpenMMDL protein-ligand molecular dynamics workflows |
| `slack_report` | Post markdown reports to Slack and save library copies |
| `diagrams_mermaid` | Generate Mermaid diagrams for complex workflows and pipeline explanations |

Install a single skill with `fastfold skills add fastfold-ai/skills@skills/<skill>` (or `npx skills add fastfold-ai/skills`).

### boltz

Drives the official `boltz-api` CLI directly for:

- structure-and-binding
- protein design and protein library screen
- small-molecule design and library screen
- ADME
- status / retrieve / list / recovery flows

**Use when:**
- The user explicitly wants direct Boltz API execution (`boltz-api` flows)
- You need an estimate -> confirm -> submit -> wait/download flow
- You need run recovery and durable artifact persistence

**Key runtime behavior:**
- Always estimates cost and waits for explicit user approval before any billable submit
- Installs `boltz-api` via the official Boltz installer when missing (`curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`)
- Downloads into `/tmp/boltz-runs/<slug>` (the `/workspace` mount is S3-backed, not POSIX), then persists with `scripts/persist.sh`
- Recovers from the API by `idempotency_key` instead of re-submitting a billable job

**Scripts:**
- `persist.sh` – S3-safe copy of a finished run directory from `/tmp/boltz-runs/<slug>` to `/workspace/boltz-artifacts/boltz/<slug>/`

**Example prompts (small runnable examples):**
- "Run a simple ROR1-style Boltz-2 structure-and-binding smoke test with aspirin; estimate first, then execute."
- "Run a minimal AMBP-style protein design job with 10 proteins and return top metrics/artifact paths."
- "Screen aspirin, ibuprofen, and caffeine against a PknB-style target with small-molecule library screen and summarize top hits."
- "Run ADME quick triage for aspirin, ibuprofen, phenol, and caffeine."
- "Recover my earlier Boltz job by idempotency key, re-download results, and persist them to workspace."

Reference examples:
- [skills/boltz/references/examples.md](https://github.com/fastfold-ai/skills/blob/main/skills/boltz/references/examples.md)

**Requires:** `BOLTZ_API_KEY` in the sandbox/runtime environment.
If missing, configure provider access at [Fastfold Boltz Provider](https://cloud.fastfold.ai/integrations/providers?provider=boltz), create/get a key at [Boltz Console](https://api.boltz.bio/console), and restart the sandbox.

### fold

Submits and manages FastFold protein folding jobs via the Jobs API. Covers authentication, creating jobs, polling for completion, and fetching CIF/PDB URLs, metrics, and 3D viewer links.

**Use when:**
- Folding a protein sequence with FastFold (API or scripts)
- Mentioning FastFold API, fold job, CIF/PDB results, or viewer link
- Scripting: create job → wait for completion → download results / metrics / viewer URL

**Features:**
- Create Job (POST `/v1/jobs`) with sequences and params; optional constraints, library `from` ID
- Wait for completion with configurable polling and timeout
- Fetch results (JSON or summary), download CIF(s), get 3D viewer link
- Self-contained OpenAPI schema in `references/jobs.yaml`

**Scripts:**
- `wait_for_completion.py` – poll until COMPLETED/FAILED/STOPPED
- `fetch_results.py` – get job results summary (or `--json` for raw output)
- `download_cif.py` – download CIF file(s) for completed jobs
- `get_viewer_link.py` – print Mol* viewer URL: `https://cloud.fastfold.ai/mol/new?from=jobs&job_id=<id>`

**Requires:** `FASTFOLD_API_KEY` from `.env` or environment. Agent will ask the user to set it locally before continuing if missing.

### protein_design_boltzgen

BoltzGen protein design workflow automation (draft -> upsert -> execute -> ranked candidates).

**Use when:**
- Running BoltzGen design workflows from presets or custom specs
- Asking for example-first setup with bundled workflow examples
- Fetching ranked candidates, metrics, and Mol* links

**Key scripts:**
- `workflow_api.py` – create/upload/build/upsert/execute/wait/results
- `fetch_cif.py` – fetch candidate CIF artifacts

### md_openmm_calvados

CALVADOS + OpenMM workflow automation via the Workflows API (`calvados_openmm_v1`).

**Use when:**
- Running OpenMM simulations from completed fold jobs
- Submitting manual PDB + PAE simulation inputs
- Fetching workflow metrics, artifacts, and extracted frames

### md_openmmdl

OpenMMDL protein-ligand workflow automation via the Workflows API (`openmmdl_v1`).

**Use when:**
- Submitting topology + ligand based MD jobs
- Preparing/executing draft OpenMMDL scripts
- Fetching analysis artifacts and trajectory frames

### slack_report

Share markdown reports to Slack and save a copy to Fastfold library.

**Use when:**
- Sharing an agent/session report to a Slack channel
- Posting markdown summaries to team updates
- Saving the same report in library and Slack in one step

**Features:**
- Sends report via `POST /v1/slack/messages/agent-cli-report`
- Uses configured `agent_cli_report` channel in Slack integrations
- Returns friendly guidance when Slack is not configured
- Includes library open link when `library_item_id` is returned

**Scripts:**
- `send_agent_cli_report.py` – send markdown report to Slack report channel and save to library

**Requires:** `FASTFOLD_API_KEY` from environment or `.env`.

### diagrams_mermaid

Generate Mermaid diagrams on demand and proactively for multi-step workflows.

**Use when:**
- User explicitly asks for flowcharts, sequence diagrams, Mermaid output, or architecture maps
- You are explaining complex pipelines with branching/dependencies
- You need visual workflow summaries for computational biology runs (for example BoltzGen, fold -> MD chains)

**Features:**
- Diagram type selection guidance (flowchart, sequence, state, ER)
- Syntax guardrails for reliable Mermaid rendering
- Reusable templates for FastFold and general multi-step workflow explanations

**Requires:** No API key.

### Setting your FastFold API key

Scripts automatically read `FASTFOLD_API_KEY` from a **`.env`** file in the project (current directory or any parent), so you don't need to export it in the shell.

**Option A — Use a `.env` file (recommended)**

1. **Copy the template:** `cp skills/fold/references/.env.example .env`
2. **Open `.env`** and paste your API key after the `=`:  
   `FASTFOLD_API_KEY=sk-your-actual-key-here`
3. **Save.** Scripts will load the key when you run them from this repo or any subdirectory.

Get a key at [FastFold API Keys](https://cloud.fastfold.ai/api-keys). **Do not commit `.env`** (it's in `.gitignore`).
Do not paste API keys in chat; keep secrets in local `.env` only.

**Option B — Export in the shell:** `export FASTFOLD_API_KEY="sk-..."`  
Environment variables take precedence over `.env`.

## License

MIT
