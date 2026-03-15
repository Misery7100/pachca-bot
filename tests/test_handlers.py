"""Tests for GitHub and generic webhook handlers."""

from pachca_bot.handlers.generic import handle_generic_event
from pachca_bot.handlers.github import handle_github_event
from pachca_bot.models.messages import Severity
from pachca_bot.models.webhooks import GenericWebhookPayload, GitHubWebhookPayload


class TestGitHubHandler:
    def test_release_published(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "published",
                "repository": {
                    "full_name": "org/repo",
                    "html_url": "https://github.com/org/repo",
                },
                "sender": {"login": "alice"},
                "release": {
                    "tag_name": "v1.0.0",
                    "name": "Version 1.0",
                    "body": "Changelog",
                    "html_url": "https://github.com/org/repo/releases/tag/v1.0.0",
                    "prerelease": False,
                    "author": {"login": "alice"},
                },
            }
        )
        result = handle_github_event("release", payload)
        assert result is not None
        rendered = result.render()
        assert "v1.0.0" in rendered
        assert "[org/repo](" in rendered
        assert "[alice](" in rendered

    def test_workflow_run_failure(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "sender": {"login": "ci-bot"},
                "workflow_run": {
                    "name": "CI Pipeline",
                    "head_branch": "main",
                    "head_sha": "abc1234567890",
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/actions/runs/123",
                    "actor": {"login": "alice"},
                },
            }
        )
        result = handle_github_event("workflow_run", payload)
        assert result is not None
        rendered = result.render()
        assert "CI Pipeline" in rendered
        assert "failure" in rendered
        assert "[alice](" in rendered

    def test_workflow_run_success_ignored(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "workflow_run": {
                    "name": "CI",
                    "head_branch": "main",
                    "head_sha": "abc123",
                    "conclusion": "success",
                    "html_url": "https://github.com/org/repo/actions/runs/1",
                },
            }
        )
        assert handle_github_event("workflow_run", payload) is None

    def test_check_run_failure(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "check_run": {
                    "name": "lint",
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/runs/1",
                    "check_suite": {
                        "head_branch": "feat",
                        "head_sha": "def456789",
                    },
                },
            }
        )
        result = handle_github_event("check_run", payload)
        assert result is not None
        assert "lint" in result.render()

    def test_pr_opened(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "opened",
                "repository": {"full_name": "org/repo"},
                "sender": {"login": "alice"},
                "pull_request": {
                    "number": 7,
                    "title": "Add feature X",
                    "body": "Description",
                    "html_url": "https://github.com/org/repo/pull/7",
                    "user": {"login": "alice"},
                    "head": {"ref": "feature-x"},
                    "base": {"ref": "main"},
                    "merged": False,
                    "draft": False,
                },
            }
        )
        result = handle_github_event("pull_request", payload)
        assert result is not None
        rendered = result.render()
        assert "#7" in rendered
        assert "Add feature X" in rendered

    def test_pr_labeled_ignored(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "labeled",
                "repository": {"full_name": "org/repo"},
                "pull_request": {
                    "number": 1,
                    "title": "PR",
                    "html_url": "https://github.com/org/repo/pull/1",
                    "user": {"login": "x"},
                    "head": {"ref": "a"},
                    "base": {"ref": "main"},
                },
            }
        )
        assert handle_github_event("pull_request", payload) is None

    def test_deployment_created(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "created",
                "repository": {
                    "full_name": "org/repo",
                    "html_url": "https://github.com/org/repo",
                },
                "sender": {"login": "alice"},
                "deployment": {
                    "id": 1,
                    "sha": "abc123def456",
                    "ref": "main",
                    "environment": "production",
                    "description": "Deploying v1.0",
                    "creator": {"login": "alice"},
                },
            }
        )
        result = handle_github_event("deployment", payload)
        assert result is not None
        rendered = result.render()
        assert "production" in rendered
        assert "[alice](" in rendered
        assert "[main](" in rendered

    def test_deployment_status_failure(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "created",
                "repository": {
                    "full_name": "org/repo",
                    "html_url": "https://github.com/org/repo",
                },
                "sender": {"login": "bot"},
                "deployment": {
                    "id": 1,
                    "sha": "abc123",
                    "ref": "v2.0",
                    "environment": "staging",
                    "creator": {"login": "alice"},
                },
                "deployment_status": {
                    "state": "failure",
                    "description": "Deploy failed",
                    "target_url": "https://github.com/org/repo/deployments/1",
                },
            }
        )
        result = handle_github_event("deployment_status", payload)
        assert result is not None
        rendered = result.render()
        assert "failure" in rendered
        assert "staging" in rendered

    def test_ping(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "zen": "Keep it logically awesome.",
                "repository": {"full_name": "org/repo"},
            }
        )
        result = handle_github_event("ping", payload)
        assert result is not None
        rendered = result.render()
        assert "connected" in rendered
        assert "[org/repo](" in rendered

    def test_unsupported_event_ignored(self):
        payload = GitHubWebhookPayload.model_validate(
            {"action": "created", "repository": {"full_name": "org/repo"}}
        )
        assert handle_github_event("star", payload) is None


class TestGenericHandler:
    def test_alert_event(self):
        payload = GenericWebhookPayload(
            event_type="alert",
            source="monitor",
            title="CPU spike",
            severity=Severity.WARNING,
            details="CPU at 95%",
            fields={"Host": "vm-01"},
        )
        result = handle_generic_event(payload)
        rendered = result.render()
        assert "CPU spike" in rendered
        assert "monitor" in rendered

    def test_deploy_event(self):
        payload = GenericWebhookPayload(
            event_type="deploy",
            source="api",
            title="",
            environment="staging",
            version="1.2.3",
            status="succeeded",
            actor="deployer",
            changelog=["Fixed login"],
        )
        result = handle_generic_event(payload)
        rendered = result.render()
        assert "1.2.3" in rendered
        assert "staging" in rendered
        assert "Fixed login" in rendered

    def test_custom_event(self):
        payload = GenericWebhookPayload(
            event_type="custom",
            source="scheduler",
            title="Backup completed",
        )
        result = handle_generic_event(payload)
        assert "Backup completed" in result.render()
