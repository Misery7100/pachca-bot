"""Tests for GHDeployTracker — GitHub deployment tracking."""

from unittest.mock import MagicMock

from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.github.gh_deploy_tracker import GHDeployTracker, _GHDeployEntry
from pachca_bot.integrations.github.models import GHDeployState, GitHubDeploymentMessage

_GH_INTEGRATION = IntegrationConfig(
    chat_id=12345,
    display_name="GitHub Bot",
    display_avatar_url="https://example.com/gh.png",
)


def _make_tracker() -> tuple[GHDeployTracker, MagicMock]:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return GHDeployTracker(client, _GH_INTEGRATION), client


def _make_deploy(state: str = "pending") -> GitHubDeploymentMessage:
    return GitHubDeploymentMessage(
        repo="org/repo",
        environment="production",
        state=state,
        creator="alice",
        sha="abc123",
        ref="main",
        url="https://github.com/org/repo/deployments",
    )


class TestGHDeployTrackerNew:
    def test_creates_message(self):
        tracker, client = _make_tracker()
        result = tracker.handle_deploy_event(_make_deploy())
        assert result["id"] == 100
        client.send_message.assert_called_once()


class TestGHDeployTrackerUpdate:
    def test_thread_update_has_emoji(self):
        tracker, client = _make_tracker()
        content = _make_deploy("pending").to_parent()
        tracker._store[("org/repo", "production")] = _GHDeployEntry(
            message_id=100, state=GHDeployState.PENDING, content=content
        )
        tracker.handle_deploy_event(_make_deploy("success"))
        thread_text = client.post_to_thread.call_args[0][1]
        assert "**Before:** ⏳ Pending" in thread_text
        assert "**After:** ✅ Success" in thread_text

    def test_patches_parent(self):
        tracker, client = _make_tracker()
        content = _make_deploy("pending").to_parent()
        tracker._store[("org/repo", "production")] = _GHDeployEntry(
            message_id=100, state=GHDeployState.PENDING, content=content
        )
        tracker.handle_deploy_event(_make_deploy("success"))
        updated = client.update_message.call_args[0][1]
        assert "✅" in updated
        assert "**Status:** Success" in updated
        assert "production" in updated

    def test_skips_same_state(self):
        tracker, client = _make_tracker()
        tracker._store[("org/repo", "production")] = _GHDeployEntry(
            message_id=100, state=GHDeployState.PENDING, content=""
        )
        result = tracker.handle_deploy_event(_make_deploy("pending"))
        assert result.get("unchanged") is True
