# Fastfold Slack Report API

## Endpoint

- `POST https://api.fastfold.ai/v1/slack/messages/agent-cli-report`

## Auth

- Header: `Authorization: Bearer <FASTFOLD_API_KEY>`
- Also supports `X-API-Key: <FASTFOLD_API_KEY>`

## Request Body

```json
{
  "markdown": "# Report title\n\nSummary...",
  "report_name": "session_20260225_210000.md",
  "save_to_library": true
}
```

## Success Response (example)

```json
{
  "ok": true,
  "message": "Report sent to Slack agent_cli_report channel.",
  "channel_id": "C0123456789",
  "ts": "1740506400.123456",
  "library_item_id": "2f5b9e7c-2de4-47db-9fcf-846532d3cbf5",
  "library_file_name": "session_20260225_210000.md"
}
```

## Slack Not Configured Response (example)

```json
{
  "ok": false,
  "message": "No Slack channel configured for agent_cli_report.",
  "needs_slack_setup": true,
  "setup_instructions": "Slack is not configured for Agent CLI reports. Open https://cloud.fastfold.ai/integrations/slack, connect your workspace, then set a channel for the agent_cli_report mode."
}
```
