"""Tests for PRTracker."""

from unittest.mock import MagicMock

from pachca_bot.models.messages import GitHubPRMessage, PRStatus
from pachca_bot.pr_tracker import PRTracker, _PREntry


def _make_tracker() -> tuple[PRTracker, MagicMock]:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return PRTracker(client), client


def _make_pr(number: int = 1, status: PRStatus = PRStatus.OPEN) -> GitHubPRMessage:
    return GitHubPRMessage(
        repo="org/repo",
        number=number,
        title="Test",
        author="alice",
        url=f"https://github.com/org/repo/pull/{number}",
        base_branch="main",
        head_branch="feat",
        status=status,
    )


class TestPRTrackerUpdate:
    def test_thread_update_has_emoji(self):
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.DRAFT).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.DRAFT, content=content
        )
        tracker.handle_pr_event(_make_pr(status=PRStatus.OPEN))

        thread_text = client.post_to_thread.call_args[0][1]
        assert "**Before:** 📝 Draft" in thread_text
        assert "**After:** 🆕 Open" in thread_text

    def test_patches_parent(self):
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.DRAFT).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.DRAFT, content=content
        )
        tracker.handle_pr_event(_make_pr(status=PRStatus.MERGED))
        updated = client.update_message.call_args[0][1]
        assert "🟣" in updated
        assert "**Status:** Merged" in updated
        assert "[alice](" in updated

    def test_skips_same_status(self):
        tracker, client = _make_tracker()
        tracker._store[("org/repo", 1)] = _PREntry(message_id=100, status=PRStatus.OPEN, content="")
        result = tracker.handle_pr_event(_make_pr(status=PRStatus.OPEN))
        assert result.get("unchanged") is True
        client.create_thread.assert_not_called()


class TestPRTrackerReopened:
    def test_reopened_always_new_message(self):
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.CLOSED).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.CLOSED, content=content
        )
        tracker.handle_pr_event(_make_pr(status=PRStatus.REOPENED))

        client.send_message.assert_called_once()
        sent = client.send_message.call_args[0][0]
        assert "🔄" in sent
        assert "Reopened" in sent
        client.create_thread.assert_not_called()
        client.update_message.assert_not_called()


class TestPRTrackerLifecycle:
    def test_draft_to_open_to_merged(self):
        tracker, client = _make_tracker()
        tracker.handle_pr_event(_make_pr(status=PRStatus.DRAFT))
        tracker.handle_pr_event(_make_pr(status=PRStatus.OPEN))
        tracker.handle_pr_event(_make_pr(status=PRStatus.MERGED))
        assert client.send_message.call_count == 1
        assert client.create_thread.call_count == 2
        assert client.update_message.call_count == 2
