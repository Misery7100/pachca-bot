# Pachca Integration Bot

A webhook-based integration bot that forwards notifications from GitHub and custom systems to [Pachca](https://pachca.com) channels.

## Features

- **GitHub Webhooks** — releases, failed CI checks/workflows, pull requests
- **Generic Webhooks** — alert / deploy / custom events from any system (VMs, monitoring, CI)
- **Structured Messages** — composable Pydantic models that render to Pachca markdown
- **Security** — HMAC-SHA256 verification for GitHub, Bearer token auth for generic endpoint

## Quick Start

```bash
uv sync
```

Set required environment variables:

```bash
export PACHCA_ACCESS_TOKEN="your-pachca-bot-token"
export PACHCA_CHAT_ID="12345"                       # target chat/channel ID

# Optional security (recommended for production)
export GITHUB_WEBHOOK_SECRET="your-github-secret"   # GitHub webhook HMAC secret
export GENERIC_WEBHOOK_SECRET="your-bearer-token"   # Bearer token for generic endpoint
```

Run the server:

```bash
uv run python -m pachca_bot
```

## Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | — | Health check |
| `/webhooks/github` | POST | HMAC-SHA256 (`X-Hub-Signature-256`) | GitHub webhook receiver |
| `/webhooks/generic` | POST | Bearer token (`Authorization`) | Generic webhook receiver |

## GitHub Webhook Setup

1. In your GitHub repository → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-host/webhooks/github`
3. **Content type**: `application/json`
4. **Secret**: same value as `GITHUB_WEBHOOK_SECRET`
5. **Events**: select *Releases*, *Check runs*, *Workflow runs*, *Pull requests*

## Generic Webhook

Send structured JSON to `/webhooks/generic` with a Bearer token:

```bash
# Alert
curl -X POST https://your-host/webhooks/generic \
  -H "Authorization: Bearer $GENERIC_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "alert",
    "source": "vm-prod-01",
    "title": "Disk usage critical",
    "severity": "error",
    "details": "95% used on /data",
    "fields": {"Host": "vm-prod-01", "Partition": "/data"},
    "url": "https://monitoring.example.com/alert/123"
  }'

# Deploy
curl -X POST https://your-host/webhooks/generic \
  -H "Authorization: Bearer $GENERIC_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "deploy",
    "source": "api-service",
    "title": "",
    "environment": "production",
    "version": "2.5.0",
    "status": "succeeded",
    "actor": "deployer",
    "changelog": ["Added caching", "Fixed login bug"]
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
| `changelog` | string[] | no | For deploys: list of changes |

## Message Models

Build custom messages programmatically using composable blocks:

```python
from pachca_bot.models.messages import (
    StructuredMessage, HeaderBlock, FieldsBlock,
    TextBlock, CodeBlock, LinkBlock, ListBlock,
)

msg = StructuredMessage()
msg.add(HeaderBlock(text="Deployment Report", level=2))
msg.add(FieldsBlock(fields={"Env": "prod", "Version": "1.2.3"}))
msg.add(ListBlock(items=["Fixed auth", "Added cache"]))
msg.add(LinkBlock(text="View details", url="https://example.com"))

print(msg.render())  # markdown ready for Pachca
```

## Testing

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
```

## Configuration

All settings are read from environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `PACHCA_ACCESS_TOKEN` | yes | — | Pachca API bot token |
| `PACHCA_CHAT_ID` | yes | — | Target chat/channel ID |
| `PACHCA_BOT_USER_ID` | no | — | Bot user ID (informational) |
| `GITHUB_WEBHOOK_SECRET` | no | `""` | GitHub HMAC secret (skips verification if empty) |
| `GENERIC_WEBHOOK_SECRET` | no | `""` | Bearer token (skips auth if empty) |
| `BOT_DISPLAY_NAME` | no | `"Integration Bot"` | Display name for bot messages |
| `BOT_DISPLAY_AVATAR_URL` | no | — | Avatar URL for bot messages |
| `HOST` | no | `0.0.0.0` | Server bind address |
| `PORT` | no | `8000` | Server bind port |
