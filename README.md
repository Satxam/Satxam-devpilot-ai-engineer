# DevPilot

DevPilot is a minimal local web UI for an autonomous AI Software Engineer. It accepts a repository, optional Jira and Slack destinations, and a natural-language engineering request. Hermes makes the agentic decisions; Swytchcode performs the real provider API execution.

## Architecture

- `index.html` is a dependency-free single-page demo UI.
- `app.py` is a Python standard-library HTTP server. It invokes Hermes in non-executing planning mode and delegates provider execution to Swytchcode.
- All provider actions are delegated to the installed Swytchcode CLI/kernel; DevPilot never calls GitHub, Jira, or Slack HTTP endpoints directly.
- Hermes is the reasoning layer. Its first strict-JSON decision chooses whether GitHub is needed. After GitHub runs, a second strict-JSON decision examines the actual result and chooses Jira and/or Slack. Hermes planning calls run with safe mode and never execute integrations.

Configured execution tools:

- `github.issue.list1` — GitHub issue search (`q` query parameter)
- `jira.api.issue.create` — Jira issue creation (`body` JSON)
- `slack.chat.postmessage.create` — Slack message posting (`body` JSON)

## Agent behavior

The request flow is:

1. It validates `OWNER/REPO` and accepts the natural-language request.
2. Hermes returns strict JSON: intent, selected tools, reason, and confirmation requirement.
3. Swytchcode executes `github.issue.list1` only when Hermes selected GitHub.
4. Hermes receives the GitHub result and makes a second decision about Jira and Slack.
5. Jira and Slack require an explicit UI confirmation before Swytchcode executes their writes.
6. Results and statuses are shown in the Request → Hermes planning → GitHub → Hermes post-result decision → Jira → Slack → Final result timeline.

No credentials or secrets are stored in the application. OAuth credentials remain managed by Swytchcode.

## Run

From this directory:

```bash
python3 app.py
```

Open http://127.0.0.1:8765.

Optional environment variables:

```bash
DEVPILOT_HOST=127.0.0.1 DEVPILOT_PORT=8765 python3 app.py
```

The project must have Swytchcode configured and authenticated for the providers you intend to use. The server invokes `swytchcode exec` with the exact canonical IDs and schemas inspected for this project.

## Demo prompts

The exact follow-up tools are decided by Hermes from the natural-language request and the returned GitHub data; these prompts are not keyword-routed.

Jira creation uses the supplied project key and a Task issue type. Slack posting uses the supplied channel. Review the confirmation panel before allowing either write. <img width="9483" height="3618" alt="Swytchcode-ai-agent-engineer" src="https://github.com/user-attachments/assets/a63847aa-db02-4228-b818-3832679fabe6" />

