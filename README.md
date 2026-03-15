# Pachca Integration Bot

A webhook-based integration bot that forwards notifications from GitHub and custom systems to [Pachca](https://pachca.com) channels with rich, hyperlinked markdown formatting.

## Features

- **GitHub Webhooks** — releases, failed CI checks/workflows, pull requests (full lifecycle with threads), deployments
- **Thread-based PR Tracking** — each PR gets one parent message; status changes are posted as thread replies and the parent is updated
- **Generic Webhooks** — alert / deploy / custom events from any system (VMs, monitoring, CI)
- **Structured Messages** — composable Pydantic models that render to Pachca markdown with hyperlinks
- **Security** — HMAC-SHA256 verification for GitHub, Bearer token auth for generic endpoint

## Quick Start

```bash
uv sync
uv run python -m pachca_bot
```

## Configuration

All settings are read from environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `PACHCA_ACCESS_TOKEN` | yes | — | Pachca API bot token |
| `PACHCA_CHAT_ID` | no* | — | Fallback chat ID when integration-specific ID not set |
| `GITHUB__PACHCA_CHAT_ID` | no* | — | Target chat for GitHub integration |
| `GENERIC__PACHCA_CHAT_ID` | no* | — | Target chat for generic integration |
| `GITHUB__WEBHOOK_SECRET` | yes* | — | GitHub HMAC secret (required for `/webhooks/github`) |
| `GENERIC__WEBHOOK_SECRET` | yes* | — | Bearer token for generic endpoint (required for `/webhooks/generic`) |
| `GITHUB__BOT_DISPLAY_NAME` | no | `"GitHub Bot"` | Display name for GitHub messages |
| `GENERIC__BOT_DISPLAY_NAME` | no | `"Events Bot"` | Display name for generic messages |
| `GITHUB__BOT_DISPLAY_AVATAR_URL` | no | [default](https://raw.githubusercontent.com/Misery7100/pachca-bot/main/images/github-bot.png) | Avatar URL for GitHub messages |
| `GENERIC__BOT_DISPLAY_AVATAR_URL` | no | [default](https://raw.githubusercontent.com/Misery7100/pachca-bot/main/images/events-bot.png) | Avatar URL for generic messages |
| `HOST` | no | `0.0.0.0` | Server bind address |
| `PORT` | no | `8000` | Server bind port |

\* At least one of `PACHCA_CHAT_ID`, `GITHUB__PACHCA_CHAT_ID`, or `GENERIC__PACHCA_CHAT_ID` must be set. Use `PACHCA_CHAT_ID` alone for both integrations, or set integration-specific IDs to route GitHub and generic events to different chats. `GITHUB__WEBHOOK_SECRET` and `GENERIC__WEBHOOK_SECRET` are required for their respective endpoints — requests are rejected with 403 if the secret is not configured.

**Backward compatibility:** Flat env vars (`GITHUB_WEBHOOK_SECRET`, `GITHUB_PACHCA_CHAT_ID`, etc.) are still supported and mapped to the nested format.

## Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | — | Health check |
| `/webhooks/github` | POST | HMAC-SHA256 (`X-Hub-Signature-256`) | GitHub webhook receiver |
| `/webhooks/generic` | POST | Bearer token (`X-Authorization`) | Generic webhook receiver |

---

## GitHub Integration Setup

### Step 1: Deploy the bot

Deploy the bot somewhere publicly accessible (e.g. a VPS, cloud VM, or container platform). The bot listens on port `8000` by default.

```bash
# Using Docker (single chat for both integrations)
docker build -t pachca-bot .
docker run -d --name pachca-bot -p 8000:8000 \
    -e PACHCA_ACCESS_TOKEN="your-pachca-bot-token" \
    -e PACHCA_CHAT_ID="your-chat-id" \
    -e GITHUB_WEBHOOK_SECRET="your-secret-here" \
    pachca-bot

# Or use separate chats per integration
docker run -d --name pachca-bot -p 8000:8000 \
    -e PACHCA_ACCESS_TOKEN="your-pachca-bot-token" \
    -e GITHUB__PACHCA_CHAT_ID="github-chat-id" \
    -e GENERIC__PACHCA_CHAT_ID="generic-chat-id" \
    -e GITHUB__WEBHOOK_SECRET="your-secret-here" \
    -e GENERIC__WEBHOOK_SECRET="your-generic-secret" \
    pachca-bot
```

### Step 2: Generate a webhook secret

Generate a random secret string. This will be shared between GitHub and the bot to verify webhook authenticity.

```bash
openssl rand -hex 32
```

Set this as the `GITHUB__WEBHOOK_SECRET` environment variable for the bot.

### Step 3: Configure the GitHub webhook

1. Go to your GitHub repository → **Settings** → **Webhooks** → **Add webhook**
2. Fill in the fields:
   - **Payload URL**: `https://your-bot-host/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: paste the secret from Step 2
3. Under **"Which events would you like to trigger this webhook?"**, select **"Let me select individual events"** and check:
   - ✅ **Check suites** — for PR check status tracking (marks PRs as "Ready to merge")
   - ✅ **Deployments** — for deployment notifications
   - ✅ **Deployment statuses** — for deployment status updates
   - ✅ **Pull requests** — for PR lifecycle (draft, opened, ready for review, merged, closed)
   - ✅ **Releases** — for release notifications
   - ✅ **Workflow runs** — for CI failure notifications
4. Optionally also check:
   - ✅ **Check runs** — for individual check run failure notifications
5. Make sure **Active** is checked
6. Click **Add webhook**

GitHub will send a `ping` event to verify the webhook is working. You should see a confirmation message in your Pachca channel.

### Supported GitHub Events

| Event | Actions | What it does |
|---|---|---|
| `release` | `published` | Posts release notification with changelog |
| `pull_request` | `opened`, `closed`, `reopened`, `ready_for_review`, `converted_to_draft` | Creates/updates PR message with thread-based status tracking |
| `check_suite` | `completed` (success) | Marks associated PRs as "Ready to merge" |
| `workflow_run` | `completed` (failure/cancelled) | Posts CI failure — to PR thread if associated, otherwise to channel |
| `check_run` | `completed` (failure) | Posts individual check failure notification |
| `deployment` | `created` | Posts deployment notification |
| `deployment_status` | `created` | Posts deployment status update |

### PR Lifecycle

The bot tracks pull requests through their full lifecycle using **thread-based messaging**:

| Status | Emoji | Trigger |
|---|---|---|
| Draft | 📝 | PR opened with `draft: true` |
| Open | 🆕 | PR opened (non-draft) or reopened |
| Ready for review | 👀 | PR marked as ready for review |
| Ready to merge | ✅ | All check suites passed |
| Merged | 🟣 | PR closed with `merged: true` |
| Closed | 🚫 | PR closed without merge |

**How it works:**
1. When a new PR is created (draft or regular), the bot posts a parent message to the channel
2. On each subsequent status change, the bot:
   - Creates a thread on the parent message (if not already created)
   - Posts a structured status transition reply in the thread ("Status updated: Before: ... / After: ...")
   - Patches the parent message header/status (preserving body, author, branches)
3. If the parent message was deleted, the bot creates a new one on the next update

---

## Generic Integration Setup

The generic webhook endpoint accepts structured JSON payloads from any system. It uses Bearer token authentication.

### Step 1: Generate a secret

```bash
openssl rand -hex 32
```

Set this as the `GENERIC__WEBHOOK_SECRET` environment variable for the bot.

### Step 2: Send webhooks

Include the secret as a Bearer token in the `X-Authorization` header.

#### Alert events

```bash
curl -X POST https://your-bot-host/webhooks/generic \
    -H "X-Authorization: Bearer YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{
        "event_type": "alert",
        "source": "vm-prod-01",
        "title": "Disk usage critical",
        "severity": "error",
        "details": "95% used on /data partition",
        "fields": {"Host": "vm-prod-01", "Partition": "/data"},
        "url": "https://monitoring.example.com/alert/123"
    }'
```

#### Deploy events

When a `deploy_id` is provided, the bot tracks deploys like PRs — the first event creates a parent message, and subsequent status changes for the same ID post thread updates and patch the parent.

```bash
# Start deploy (creates parent message)
curl -X POST https://your-bot-host/webhooks/generic \
    -H "X-Authorization: Bearer YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{
        "event_type": "deploy",
        "source": "api-service",
        "title": "",
        "environment": "production",
        "version": "2.5.0",
        "status": "started",
        "deploy_id": "deploy-42",
        "actor": "deployer",
        "body": "Added caching\nFixed login bug"
    }'

# Update status (posts thread update, patches parent)
curl -X POST https://your-bot-host/webhooks/generic \
    -H "X-Authorization: Bearer YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{
        "event_type": "deploy",
        "source": "api-service",
        "title": "",
        "environment": "production",
        "version": "2.5.0",
        "status": "succeeded",
        "deploy_id": "deploy-42"
    }'
```

### Generic Payload Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `event_type` | string | yes | `"alert"`, `"deploy"`, or any custom type |
| `source` | string | yes | Origin system identifier |
| `title` | string | yes | Short summary |
| `severity` | string | no | `info` / `success` / `warning` / `error` / `critical` |
| `details` | string | no | Extended description |
| `fields` | object | no | Key-value pairs rendered as labeled fields |
| `url` | string | no | Link for details |
| `environment` | string | no | For deploys: target environment |
| `version` | string | no | For deploys: version being deployed |
| `status` | string | no | For deploys: `started` / `succeeded` / `failed` / `rolled_back` |
| `actor` | string | no | Who triggered the event |
| `body` | string | no | For deploys: plain text body (similar to GitHub release notes) |
| `deploy_id` | string | no | For deploys: unique ID for thread-based status tracking |
| `display_name` | string | no | Override bot display name for this request (e.g. unsupported integration) |
| `display_avatar_url` | string | no | Override bot avatar URL for this request |

### Severity Levels

| Severity | Emoji | Use case |
|---|---|---|
| `info` | ℹ️ | Informational events (backups, scheduled tasks) |
| `success` | ✅ | Health checks passing, successful operations |
| `warning` | ⚠️ | High resource usage, degraded performance |
| `error` | ❌ | Service errors, failed operations |
| `critical` | 🔥 | System down, data loss, immediate action needed |

---

## Reusable GitHub Actions

Pre-built composite actions in `actions/` for easy integration in any workflow.

### Alert Action

```yaml
- uses: misery7100/pachca-bot/actions/generic-alert@main
  with:
    host: ${{ secrets.PACHCA_BOT_HOST }}
    secret: ${{ secrets.PACHCA_WEBHOOK_SECRET }}
    source: "my-service"
    title: "Build failed"
    severity: "error"
    details: "Build failed on commit ${{ github.sha }}"
    fields: '{"Branch": "${{ github.ref_name }}", "Actor": "${{ github.actor }}"}'
    url: "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

### Deployment Action

```yaml
# At the start of deploy
- uses: misery7100/pachca-bot/actions/generic-deployment@main
  with:
    host: ${{ secrets.PACHCA_BOT_HOST }}
    secret: ${{ secrets.PACHCA_WEBHOOK_SECRET }}
    source: "my-service"
    environment: "production"
    version: "1.2.3"
    status: "started"
    deploy_id: "deploy-${{ github.run_id }}"
    actor: "${{ github.actor }}"
    changelog: '["Added feature X", "Fixed bug Y"]'

# After deploy completes
- uses: misery7100/pachca-bot/actions/generic-deployment@main
  if: success()
  with:
    host: ${{ secrets.PACHCA_BOT_HOST }}
    secret: ${{ secrets.PACHCA_WEBHOOK_SECRET }}
    source: "my-service"
    environment: "production"
    version: "1.2.3"
    status: "succeeded"
    deploy_id: "deploy-${{ github.run_id }}"
```

---

## Development

```bash
uv sync
just check     # lint + test
just run       # start server
just format    # auto-format
```

### Testing

```bash
just test            # run all tests
just lint            # lint check
uv run pytest -v -k "test_pr"  # run specific tests
```

### Docker

```bash
just docker-build
just docker-run
```
