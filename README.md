# Fastfold AI Skills

A collection of skills for AI agents. Skills are packaged instructions and scripts that extend agent capabilities.

Skills follow the [Agent Skills](https://agentskills.io/) format.

## Install

```bash
npx skills add fastfold-ai/skills
```

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
| `fold` | FastFold Jobs API submission, waiting, and result retrieval |
| `protein_design_boltzgen` | BoltzGen protein design workflow orchestration |
| `md-openmm-calvados` | CALVADOS + OpenMM molecular dynamics workflows |
| `md-openmmdl` | OpenMMDL protein-ligand molecular dynamics workflows |
| `slack_report` | Post markdown reports to Slack and save library copies |

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

### md-openmm-calvados

CALVADOS + OpenMM workflow automation via the Workflows API (`calvados_openmm_v1`).

**Use when:**
- Running OpenMM simulations from completed fold jobs
- Submitting manual PDB + PAE simulation inputs
- Fetching workflow metrics, artifacts, and extracted frames

### md-openmmdl

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
