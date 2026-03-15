"""Tests for GitHub and generic webhook handlers."""

from unittest.mock import MagicMock

from pachca_bot.handlers.generic import handle_generic_event
from pachca_bot.handlers.github import handle_github_event
from pachca_bot.models.messages import PRStatus, Severity, StructuredMessage
from pachca_bot.models.webhooks import GenericWebhookPayload, GitHubWebhookPayload
from pachca_bot.pr_tracker import PRTracker


def _make_mock_tracker() -> PRTracker:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return PRTracker(client)


class TestGitHubHandler:
    def test_release(self):
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "published",
                "repository": {"full_name": "org/repo"},
                "release": {
                    "tag_name": "v1.0",
                    "name": "v1.0",
                    "body": "### Notes\n- Fix",
                    "html_url": "https://github.com/org/repo/releases/tag/v1.0",
                    "author": {"login": "alice"},
                },
            }
        )
        result = handle_github_event("release", payload)
        assert isinstance(result, StructuredMessage)
        rendered = result.render()
        assert "🔖" in rendered
        assert "###" not in rendered
        assert "[View release](" in rendered

    def test_pr_reopened_always_new(self):
        tracker = _make_mock_tracker()
        tracker._store[("org/repo", 7)] = MagicMock(
            message_id=100, status=PRStatus.CLOSED, content=""
        )
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "reopened",
                "repository": {"full_name": "org/repo"},
                "pull_request": {
                    "number": 7,
                    "title": "Feat",
                    "html_url": "https://github.com/org/repo/pull/7",
                    "user": {"login": "alice"},
                    "head": {"ref": "feat"},
                    "base": {"ref": "main"},
                },
            }
        )
        result = handle_github_event("pull_request", payload, pr_tracker=tracker)
        assert isinstance(result, dict)
        tracker._client.send_message.assert_called_once()
        content = tracker._client.send_message.call_args[0][0]
        assert "🔄" in content
        assert "Reopened" in content

    def test_deployment_tracked(self):
        from pachca_bot.gh_deploy_tracker import GHDeployTracker

        client = MagicMock()
        client.send_message.return_value = {"id": 300}
        client.get_messages.return_value = []
        gh_tracker = GHDeployTracker(client)

        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "created",
                "repository": {
                    "full_name": "org/repo",
                    "html_url": "https://github.com/org/repo",
                },
                "deployment": {
                    "id": 1,
                    "sha": "abc123",
                    "ref": "main",
                    "environment": "production",
                    "creator": {"login": "alice"},
                },
            }
        )
        result = handle_github_event("deployment", payload, gh_deploy_tracker=gh_tracker)
        assert isinstance(result, dict)
        assert result["id"] == 300

    def test_ping(self):
        payload = GitHubWebhookPayload.model_validate(
            {"zen": "...", "repository": {"full_name": "org/repo"}}
        )
        result = handle_github_event("ping", payload)
        assert isinstance(result, StructuredMessage)


class TestGenericHandler:
    def test_alert_source_as_field(self):
        payload = GenericWebhookPayload(
            event_type="alert",
            source="monitor",
            title="CPU spike",
            severity=Severity.WARNING,
            fields={"Host": "vm-01"},
        )
        result = handle_generic_event(payload)
        assert isinstance(result, StructuredMessage)
        assert "**Source:** monitor" in result.render()

    def test_deploy_without_id(self):
        payload = GenericWebhookPayload(
            event_type="deploy",
            source="api",
            title="",
            environment="staging",
            version="1.2.3",
            status="succeeded",
        )
        result = handle_generic_event(payload)
        assert isinstance(result, StructuredMessage)
