# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ...

### Changed

- ...

### Fixed

- ...

### Removed

- ...

## [0.1.9] - 2026-03-26

### Added

- **Workflow vs check-run dedupe** — Failed `workflow_run` and `check_run` notifications share the same `check_suite_id` when GitHub sends it; only the first delivered event for a given repo + commit + suite is posted.
- **`GITHUB__PR_TRACKER_STATELESS_SAFE`** — Optional GitHub integration flag: reload PR state from Pachca on each webhook, infer checks/approval from thread text, and dedupe check-pass posts using an HTML comment suffix (often invisible; verify in your Pachca clients). In-memory workflow/check_run failure dedupe is off in this mode.

### Changed

- **Workflow failure formatting** — Failure messages use `GitHubWorkflowMessage` with a header `{workflow or check name} — {conclusion}` (no hardcoded `CI:` prefix).

### Fixed

- **Check suite success line** — Real webhooks rarely include `check_runs`; the thread line is now **All checks passed** (or the GitHub App name when present) instead of **Check passed:** ✅ Checks.

## [0.1.8] - 2026-03-18

### Changed

- **Check passed format** — Check suite success messages now use `**Check passed:** ✅ {name}` with a "View run" link instead of `**Status updated:** ✅ {name} passed — {commit}`

## [0.1.7] - 2026-03-16

### Changed

- **Status update format** — Thread status updates use `**Status updated:** <emoji> Status`; checks use `**Status updated:** ✅ {name} passed`; reviews use `**Review submitted:** <emoji> Approved — [user](link)`

### Fixed

- **Duplicate check messages** — Post per-check with workflow name (`**Status updated:** ✅ {name} passed`); dedupe by (commit, check name) so each workflow posts once

## [0.1.6] - 2026-03-16

### Added

- **pull_request_review events** — Reviews (submitted, edited, dismissed) are posted to the PR thread: approved, changes requested, commented, or dismissed
- **Ready to merge only when checks + approval** — "Ready to merge" is now set only when both (a) all checks passed and (b) at least one approval. Check suite pass alone posts "All checks passed" to the thread and keeps parent at "Ready for review". Approval promotes to "Ready to merge"; changes_requested or dismissed downgrades back to "Ready for review"

### Changed

- **check_suite behavior** — No longer promotes to "Ready to merge" on checks pass alone; posts "All checks passed" to thread instead. Promotes only when approval exists (or when approval arrives after checks pass)

## [0.1.5] - 2026-03-16

### Fixed

- **PR status vs CI failures** — When a CI failure (workflow_run or check_run) is posted to a PR thread, status is downgraded from "Ready to merge" to "Ready for review" so the parent message no longer contradicts thread content
- **check_run CI failures** — Now posted to PR thread when `check_suite.pull_requests` is available (same as workflow_run), instead of always posting to channel
- **PR thread lookup** — `get_thread_id_for_pr` now falls back to chat search when the in-memory store is empty (e.g. after serverless restart)
- **synchronize events** — New commits pushed to a PR now reset status to "Ready for review" (checks need to re-run), preventing stale "Ready to merge" when the head has changed
- **Message corruption (blank Author/Branch)** — When `check_suite` fired but the PR message was not found, the code could create a new message with minimal data. Now `check_suite` only updates existing messages. When stored content is empty and `pr_msg` is minimal: try `get_message(id)` to fetch content, then retry chat scan; only skip update if both fail
- **Content recovery** — Added `get_message(message_id)` to fetch a single message by ID. When entry content is empty, trackers now try direct fetch before giving up. Deploy trackers also fetch content when empty before patching
- **API retry with backoff** — All Pachca API calls (get_message, get_messages, send_message, update_message, create_thread, post_to_thread) retry up to 2 times on failure with exponential backoff (1s, 2s) to handle rate limits and transient errors
- **Scan depth** — Default increased from 300 to 500 messages; configurable via `MESSAGES_MAX_SCAN` env var
- **PR body stripped when closed/merged** — When a PR is closed or merged, the body is removed from the message (new or updated) to reduce visual noise; only title, fields, and link are kept

## [0.1.4] - 2026-03-16

### Added

- **Generic webhook display override** — `display_name` and `display_avatar_url` in payload to override bot identity per request (useful when source integration is unsupported)
- **Project restructuring** — `core/` (models, client, config, security), `api/` (FastAPI routes), `integrations/github/` (PR tracker, deploy tracker, handler), `integrations/generic/` (deploy tracker, handler); handlers as dataclass-based classes
- **Cursor-based message pagination** — `get_messages` uses limit=50 and cursor to scan up to 300 messages for serverless deployments

### Changed

- **Generic deploy body** — Replaced `changelog` (JSON array) with `body` (plain text) for deploy events, similar to GitHub release notes
- **Generic deployment action** — `body` input instead of `changelog`

### Fixed

- **GitHub deploy tracker** — Keys now include repo, environment, and commit SHA so each deployment is tracked separately; chat search matches all three to avoid posting updates into wrong threads

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

[unreleased]: https://github.com/Misery7100/pachca-bot/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/Misery7100/pachca-bot/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/Misery7100/pachca-bot/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Misery7100/pachca-bot/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Misery7100/pachca-bot/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Misery7100/pachca-bot/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Misery7100/pachca-bot/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Misery7100/pachca-bot/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Misery7100/pachca-bot/releases/tag/v0.1.0