---
name: slack_report
description: Share markdown reports to the user's configured Slack agent_cli_report channel via Fastfold API, and persist the markdown as a library item.
---

# Slack Report Share

## Overview

Use this skill to send markdown reports to Slack through the Fastfold Cloud backend endpoint:

- `POST /v1/slack/messages/agent-cli-report`

The endpoint posts to the configured `agent_cli_report` Slack channel and stores the same markdown as a library markdown item.

## Authentication

**Preferred (Sandwalk agent):** Integrations → Fastfold AI Cloud, exposed as
`FASTFOLD_API_KEY`. Use env vars — do not hardcode or search home config paths.

Do **not** ask users to paste secrets into chat. Do **not** ask for `.env` / export
until the helper script fails with a clear auth error. Prefer
`printenv FASTFOLD_API_KEY` or run the script.

**Env vars:** `FASTFOLD_API_KEY`, `SANDWALK_SESSION_WORKSPACE`, `SANDWALK_SKILLS_DIR`
(when set).

**If the key is still missing after a script failure:** point the user at Sandwalk
Integrations (or `.env` / export).

## When to Use

- User asks to share/export a session report to Slack.
- User asks to send markdown summary to the team's report channel.
- User asks to save a report in the library and Slack in one step.

## Agent Workflow

1. Export or prepare markdown report content.
2. Call the helper script (Sandwalk: use host skill dir / `SANDWALK_SKILLS_DIR/slack_report`
   when available):
   - `python3 scripts/send_agent_cli_report.py --markdown-file <path>`
   - Do not replace this with ad-hoc Python `requests` code.
3. If response has `ok: false` and `needs_slack_setup: true`, tell user:
   - Configure Slack at [https://cloud.fastfold.ai/integrations/slack](https://cloud.fastfold.ai/integrations/slack)
   - Set a channel for `agent_cli_report`.
4. If response includes `library_item_id`, include this open link in the reply:
   - `https://cloud.fastfold.ai/code/<library_item_id>?from=library`

## Friendly Failure Message

If Slack is not configured, return a user-friendly instruction and include:

- [https://cloud.fastfold.ai/integrations/slack](https://cloud.fastfold.ai/integrations/slack)

## Resources

- API details: [references/api.md](references/api.md)
