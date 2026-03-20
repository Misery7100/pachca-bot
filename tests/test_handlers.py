"""Tests for GitHub and generic webhook handlers."""

from unittest.mock import MagicMock

from pachca_bot.core.blocks import StructuredMessage
from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.generic.handler import GenericHandler
from pachca_bot.integrations.generic.models import GenericWebhookPayload, Severity
from pachca_bot.integrations.github.gh_deploy_tracker import GHDeployTracker
from pachca_bot.integrations.github.handler import GitHubHandler
from pachca_bot.integrations.github.models import GitHubWebhookPayload, PRStatus
from pachca_bot.integrations.github.pr_tracker import PRTracker, _PREntry

_GH_INTEGRATION = IntegrationConfig(
    chat_id=12345,
    display_name="GitHub Bot",
    display_avatar_url="https://example.com/gh.png",
)


def _make_github_handler(pr_tracker=None, gh_deploy_tracker=None) -> GitHubHandler:
    client = MagicMock()
    return GitHubHandler(
        client=client,
        integration=_GH_INTEGRATION,
        pr_tracker=pr_tracker,
        gh_deploy_tracker=gh_deploy_tracker,
        webhook_secret="gh-secret",
    )


def _make_mock_pr_tracker() -> PRTracker:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return PRTracker(client, _GH_INTEGRATION)


class TestGitHubHandler:
    def test_release(self):
        handler = _make_github_handler()
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
        result = handler._process("release", payload)
        assert isinstance(result, StructuredMessage)
        rendered = result.render()
        assert "🔖" in rendered
        assert "###" not in rendered
        assert "[View release](" in rendered

    def test_pr_reopened_always_new(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 7)] = MagicMock(
            message_id=100, status=PRStatus.CLOSED, content=""
        )
        handler = _make_github_handler(pr_tracker=tracker)
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
        result = handler._process("pull_request", payload)
        assert isinstance(result, dict)
        tracker._client.send_message.assert_called_once()
        content = tracker._client.send_message.call_args[0][0]
        assert "🔄" in content
        assert "Reopened" in content

    def test_deployment_tracked(self):
        client = MagicMock()
        client.send_message.return_value = {"id": 300}
        client.get_messages.return_value = []
        gh_tracker = GHDeployTracker(client, _GH_INTEGRATION)
        handler = _make_github_handler(gh_deploy_tracker=gh_tracker)

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
        result = handler._process("deployment", payload)
        assert isinstance(result, dict)
        assert result["id"] == 300

    def test_ping(self):
        handler = _make_github_handler()
        payload = GitHubWebhookPayload.model_validate(
            {"zen": "...", "repository": {"full_name": "org/repo"}}
        )
        result = handler._process("ping", payload)
        assert isinstance(result, StructuredMessage)

    def test_pull_request_review_posted_to_thread(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 12)] = MagicMock(
            message_id=100, status=PRStatus.OPEN, content=""
        )
        tracker._client.create_thread.return_value = {"id": 200}
        handler = _make_github_handler(pr_tracker=tracker)
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "submitted",
                "repository": {"full_name": "org/repo"},
                "pull_request": {
                    "number": 12,
                    "html_url": "https://github.com/org/repo/pull/12",
                },
                "review": {
                    "state": "approved",
                    "body": "LGTM!",
                    "html_url": "https://github.com/org/repo/pull/12#pullrequestreview-1",
                    "user": {"login": "bob"},
                },
            }
        )
        result = handler._process("pull_request_review", payload)
        assert result == {"id": None, "posted_to_pr_thread": True}
        tracker._client.post_to_thread.assert_called_once()
        content = tracker._client.post_to_thread.call_args[0][1]
        assert "approved" in content.lower() or "Approved" in content
        assert "bob" in content
        assert "LGTM!" in content

    def test_pull_request_review_dismissed(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 5)] = MagicMock(
            message_id=100, status=PRStatus.OPEN, content=""
        )
        tracker._client.create_thread.return_value = {"id": 200}
        handler = _make_github_handler(pr_tracker=tracker)
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "dismissed",
                "repository": {"full_name": "org/repo"},
                "pull_request": {"number": 5, "html_url": "https://github.com/org/repo/pull/5"},
                "review": {
                    "state": "changes_requested",
                    "user": {"login": "alice"},
                },
            }
        )
        result = handler._process("pull_request_review", payload)
        assert result == {"id": None, "posted_to_pr_thread": True}
        content = tracker._client.post_to_thread.call_args[0][1]
        assert "dismissed" in content.lower()
        assert "alice" in content

    def test_check_suite_pass_posts_to_thread(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 3)] = _PREntry(
            message_id=100,
            status=PRStatus.READY_FOR_REVIEW,
            content="",
        )
        handler = _make_github_handler(pr_tracker=tracker)
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "check_suite": {
                    "conclusion": "success",
                    "head_sha": "abc123",
                    "html_url": "https://github.com/org/repo/commit/abc123/checks",
                    "pull_requests": [{"number": 3}],
                },
            }
        )
        result = handler._process("check_suite", payload)
        assert isinstance(result, dict)
        tracker._client.post_to_thread.assert_called_once()
        content = tracker._client.post_to_thread.call_args[0][1]
        assert "All checks passed" in content

    def test_workflow_run_skipped_when_check_run_already_posted_same_suite(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 3)] = _PREntry(
            message_id=100,
            status=PRStatus.READY_FOR_REVIEW,
            content="",
        )
        handler = _make_github_handler(pr_tracker=tracker)
        sha = "abc123deadbeef"
        suite_id = 55_555
        payload_cr = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "check_run": {
                    "name": "build",
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/check-runs/1",
                    "check_suite": {"id": suite_id, "head_sha": sha},
                },
                "check_suite": {
                    "pull_requests": [{"number": 3}],
                },
            }
        )
        r1 = handler._process("check_run", payload_cr)
        assert r1 == {"id": None, "posted_to_pr_thread": True}
        payload_wr = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "workflow_run": {
                    "name": "CI",
                    "head_sha": sha,
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/actions/runs/99",
                    "check_suite_id": suite_id,
                    "pull_requests": [{"number": 3}],
                },
            }
        )
        r2 = handler._process("workflow_run", payload_wr)
        assert r2 == {"id": None, "skipped_duplicate_ci": True}

    def test_check_run_skipped_when_workflow_already_posted_same_suite(self):
        tracker = _make_mock_pr_tracker()
        tracker._store[("org/repo", 3)] = _PREntry(
            message_id=100,
            status=PRStatus.READY_FOR_REVIEW,
            content="",
        )
        handler = _make_github_handler(pr_tracker=tracker)
        sha = "deadbeef00"
        suite_id = 66_666
        payload_wr = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "workflow_run": {
                    "name": "CI",
                    "head_sha": sha,
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/actions/runs/100",
                    "check_suite_id": suite_id,
                    "pull_requests": [{"number": 3}],
                },
            }
        )
        r1 = handler._process("workflow_run", payload_wr)
        assert r1 == {"id": None, "posted_to_pr_thread": True}
        payload_cr = GitHubWebhookPayload.model_validate(
            {
                "action": "completed",
                "repository": {"full_name": "org/repo"},
                "check_run": {
                    "name": "build",
                    "conclusion": "failure",
                    "html_url": "https://github.com/org/repo/check-runs/2",
                    "check_suite": {"id": suite_id, "head_sha": sha},
                },
                "check_suite": {
                    "pull_requests": [{"number": 3}],
                },
            }
        )
        r2 = handler._process("check_run", payload_cr)
        assert r2 == {"id": None, "skipped_duplicate_ci": True}

    def test_pull_request_review_no_tracker_ignored(self):
        handler = _make_github_handler(pr_tracker=None)
        payload = GitHubWebhookPayload.model_validate(
            {
                "action": "submitted",
                "repository": {"full_name": "org/repo"},
                "pull_request": {"number": 1},
                "review": {"state": "approved", "user": {"login": "x"}},
            }
        )
        result = handler._process("pull_request_review", payload)
        assert result is None


class TestGenericHandler:
    def test_alert_source_as_field(self):
        client = MagicMock()
        gen_config = IntegrationConfig(
            chat_id=12345,
            display_name="Events Bot",
            display_avatar_url="https://example.com/events.png",
        )
        handler = GenericHandler(
            client=client,
            integration=gen_config,
            deploy_tracker=None,
            webhook_secret="gen-secret",
        )
        payload = GenericWebhookPayload(
            event_type="alert",
            source="monitor",
            title="CPU spike",
            severity=Severity.WARNING,
            fields={"Host": "vm-01"},
        )
        result = handler._process(payload)
        assert isinstance(result, StructuredMessage)
        assert "**Source:** monitor" in result.render()

    def test_deploy_without_id(self):
        client = MagicMock()
        gen_config = IntegrationConfig(
            chat_id=12345,
            display_name="Events Bot",
            display_avatar_url="https://example.com/events.png",
        )
        handler = GenericHandler(
            client=client,
            integration=gen_config,
            deploy_tracker=None,
            webhook_secret="gen-secret",
        )
        payload = GenericWebhookPayload(
            event_type="deploy",
            source="api",
            title="",
            environment="staging",
            version="1.2.3",
            status="succeeded",
        )
        result = handler._process(payload)
        assert isinstance(result, StructuredMessage)
