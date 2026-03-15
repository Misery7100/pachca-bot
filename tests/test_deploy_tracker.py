"""Tests for DeployTracker."""

from unittest.mock import MagicMock

from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.generic.deploy_tracker import DeployTracker, _DeployEntry
from pachca_bot.integrations.generic.models import DeployStatus, GenericDeployMessage

_GEN_INTEGRATION = IntegrationConfig(
    chat_id=12345,
    display_name="Events Bot",
    display_avatar_url="https://example.com/events.png",
)


def _make_tracker() -> tuple[DeployTracker, MagicMock]:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return DeployTracker(client, _GEN_INTEGRATION), client


def _make_deploy(
    deploy_id: str = "dep-1", status: DeployStatus = DeployStatus.STARTED
) -> GenericDeployMessage:
    return GenericDeployMessage(
        source="api",
        environment="prod",
        version="1.0",
        status=status,
        deploy_id=deploy_id,
    )


class TestDeployTrackerUpdate:
    def test_thread_update_has_emoji(self):
        tracker, client = _make_tracker()
        content = _make_deploy().to_parent()
        tracker._store[("api", "dep-1")] = _DeployEntry(
            message_id=100, status=DeployStatus.STARTED, content=content
        )
        tracker.handle_deploy_event(_make_deploy(status=DeployStatus.SUCCEEDED))
        thread_text = client.post_to_thread.call_args[0][1]
        assert "**Before:** 🚀 Started" in thread_text
        assert "**After:** ✅ Succeeded" in thread_text

    def test_patches_parent(self):
        tracker, client = _make_tracker()
        content = _make_deploy().to_parent()
        tracker._store[("api", "dep-1")] = _DeployEntry(
            message_id=100, status=DeployStatus.STARTED, content=content
        )
        tracker.handle_deploy_event(_make_deploy(status=DeployStatus.SUCCEEDED))
        updated = client.update_message.call_args[0][1]
        assert "✅" in updated
        assert "**Status:** Succeeded" in updated

    def test_skips_same_status(self):
        tracker, client = _make_tracker()
        tracker._store[("api", "dep-1")] = _DeployEntry(
            message_id=100, status=DeployStatus.STARTED, content=""
        )
        result = tracker.handle_deploy_event(_make_deploy())
        assert result.get("unchanged") is True
