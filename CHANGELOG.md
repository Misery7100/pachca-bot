# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ...

### Changed

- ...

### Removed

- ...

### Fixed

- ...

## [0.1.3] - 2026-03-15

### Changed

- **GitHub event handling** — Only published releases and completed workflow runs are now processed; release link displayed before pre-release indicator in `GitHubReleaseMessage`; improved user link handling for bots
- **Deployment messages** — Environment included in deployment URL when specified
- **Webhook payload** — `_GitHubRelease` model refactored to include `action` field

### Removed

- **README** — Corrected GitHub Actions references

## [0.1.2] - 2026-03-15

### Added

- **Namespaced chat IDs** — `GITHUB_PACHCA_CHAT_ID` and `GENERIC_PACHCA_CHAT_ID` for per-integration target chats; `PACHCA_CHAT_ID` remains as fallback when integration-specific ID not set
- **Per-integration bot display name** — `GITHUB_BOT_DISPLAY_NAME` (default: "GitHub Bot") and `GENERIC_BOT_DISPLAY_NAME` (default: "Events Bot")
- **Per-integration bot avatar URL** — `GITHUB_BOT_DISPLAY_AVATAR_URL` and `GENERIC_BOT_DISPLAY_AVATAR_URL` with built-in defaults for GitHub and generic avatars

### Changed

- **Configuration** — Replaced single `PACHCA_CHAT_ID` + `BOT_DISPLAY_AVATAR_URL` with namespaced settings to support future integrations and separate chat routing
- **Security** — `GITHUB_WEBHOOK_SECRET` and `GENERIC_WEBHOOK_SECRET` are now required; endpoints return 403 with a descriptive message when the corresponding secret is not configured

## [0.1.1] - 2026-03-15

### Changed

- **Generic webhook auth** — Bearer token now read from `X-Authorization` header instead of `Authorization`

### Fixed

- **Docker** — build wheel and install instead of editable install so `pachca_bot` module is available in the final image

## [0.1.0] - 2026-03-15

### Added

- **GitHub webhook integration** — `/webhooks/github` endpoint for GitHub events
  - `release` (published) — release notifications with changelog
  - `pull_request` — full lifecycle (opened, closed, reopened, ready_for_review, converted_to_draft)
  - `check_suite` — marks associated PRs as "Ready to merge" when all checks pass
  - `workflow_run` — CI failure notifications (to PR thread when associated, otherwise to channel)
  - `check_run` — individual check failure notifications
  - `deployment` — deployment creation notifications
  - `deployment_status` — deployment status updates
- **Thread-based PR tracking** — each PR gets one parent message; status changes post thread replies and patch the parent
- **Generic webhook integration** — `/webhooks/generic` endpoint for alert and deploy events from any system
- **Thread-based deploy tracking** — generic deploys with `deploy_id` get parent messages; status changes post thread updates
- **Structured message models** — Pydantic models that render to Pachca markdown with hyperlinks
- **Security** — HMAC-SHA256 verification for GitHub webhooks; Bearer token auth for generic endpoint
- **Configuration** — environment-based settings via pydantic-settings (`PACHCA_ACCESS_TOKEN`, `PACHCA_CHAT_ID`, `GITHUB_WEBHOOK_SECRET`, `GENERIC_WEBHOOK_SECRET`, etc.)
- **Health endpoint** — `/health` for liveness checks
- **Docker support** — multi-stage Dockerfile with uv, healthcheck, slim runtime
- **CI workflow** — lint (ruff) and format check on push/PR to main
- **Build and push workflow** — Docker image build and push to ghcr.io on version tags
- **Reusable GitHub Actions**
  - `actions/generic-alert` — send alert notifications to Pachca
  - `actions/generic-deployment` — send deployment notifications with thread-based status tracking
- **Development tooling** — justfile (`just check`, `just run`, `just format`, `just test`, `just docker-build`, `just docker-run`)
- **Test suite** — pytest tests for app, handlers, models, security, PR tracker, deploy trackers
- **Project scaffolding** — pyproject.toml (uv, FastAPI, pydantic, pachca), .gitignore, LICENSE (MIT), README with setup and usage docs

[unreleased]: https://github.com/Misery7100/pachca-bot/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Misery7100/pachca-bot/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Misery7100/pachca-bot/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Misery7100/pachca-bot/releases/tag/v0.1.0