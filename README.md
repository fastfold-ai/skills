# Fastfold Agent Skills

A collection of skills for AI coding agents. Skills are packaged instructions and scripts that extend agent capabilities.

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
