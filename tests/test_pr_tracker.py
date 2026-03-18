"""Tests for PRTracker."""

from unittest.mock import MagicMock

from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.github.models import GitHubPRMessage, PRStatus
from pachca_bot.integrations.github.pr_tracker import PRTracker, _PREntry

_GH_INTEGRATION = IntegrationConfig(
    chat_id=12345,
    display_name="GitHub Bot",
    display_avatar_url="https://example.com/gh.png",
)


def _make_tracker() -> tuple[PRTracker, MagicMock]:
    client = MagicMock()
    client.send_message.return_value = {"id": 100}
    client.get_messages.return_value = []
    client.create_thread.return_value = {"id": 200}
    client.post_to_thread.return_value = {"id": 201}
    client.update_message.return_value = {"id": 100}
    return PRTracker(client, _GH_INTEGRATION), client


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
        assert "**Status updated:** 🆕 Open" in thread_text

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


class TestPRTrackerCIFailure:
    def test_downgrade_ready_to_merge_on_ci_failure(self):
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.CHECKS_PASSED).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.CHECKS_PASSED, content=content
        )
        result = tracker.downgrade_status_on_ci_failure("org/repo", 1)
        assert result is True
        client.update_message.assert_called_once()
        updated = client.update_message.call_args[0][1]
        assert "**Status:** Ready for review" in updated
        assert "Ready to merge" not in updated

    def test_downgrade_noop_when_not_ready_to_merge(self):
        tracker, client = _make_tracker()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.OPEN, content=""
        )
        result = tracker.downgrade_status_on_ci_failure("org/repo", 1)
        assert result is False
        client.update_message.assert_not_called()

    def test_get_thread_id_searches_when_not_in_store(self):
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.OPEN).to_parent()
        client.get_messages.return_value = [{"id": 99, "content": content}]
        thread_id = tracker.get_thread_id_for_pr("org/repo", 1)
        assert thread_id == 200
        client.create_thread.assert_called_once_with(99)

    def test_check_suite_does_not_create_corrupted_message_when_pr_not_found(self):
        """When check_suite fires but PR message is outside scan window, do not create one with blank Author/Branch."""
        tracker, client = _make_tracker()
        client.get_messages.return_value = []
        result = tracker.handle_check_suite_pass(
            repo="org/repo", number=1, commit_sha="abc123"
        )
        assert result is None
        client.send_message.assert_not_called()

    def test_check_suite_pass_posts_to_thread_does_not_promote_without_approval(self):
        """When checks pass but no approval, post to thread and keep Ready for review."""
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.READY_FOR_REVIEW).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.READY_FOR_REVIEW, content=content
        )
        result = tracker.handle_check_suite_pass(
            repo="org/repo", number=1, commit_sha="abc123"
        )
        assert result == {"id": 100}
        client.post_to_thread.assert_called_once()
        assert "Check passed" in client.post_to_thread.call_args[0][1]
        client.update_message.assert_not_called()

    def test_check_suite_pass_promotes_when_has_approval(self):
        """When checks pass and approval exists, promote to Ready to merge."""
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.READY_FOR_REVIEW).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100,
            status=PRStatus.READY_FOR_REVIEW,
            content=content,
            has_approval=True,
        )
        result = tracker.handle_check_suite_pass(
            repo="org/repo", number=1, commit_sha="abc123"
        )
        assert result == {"id": 100}
        client.update_message.assert_called_once()
        assert "Ready to merge" in client.update_message.call_args[0][1]

    def test_check_suite_pass_dedupes_same_commit_and_name(self):
        """Multiple check_suite events for same commit+check_name post only once."""
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.READY_FOR_REVIEW).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.READY_FOR_REVIEW, content=content
        )
        for _ in range(3):
            tracker.handle_check_suite_pass(
                repo="org/repo", number=1, commit_sha="abc123", check_name="CI"
            )
        assert client.post_to_thread.call_count == 1

    def test_check_suite_pass_posts_per_check_name(self):
        """Different check names post separate messages."""
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.READY_FOR_REVIEW).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.READY_FOR_REVIEW, content=content
        )
        tracker.handle_check_suite_pass(
            repo="org/repo", number=1, commit_sha="abc123", check_name="CI"
        )
        tracker.handle_check_suite_pass(
            repo="org/repo", number=1, commit_sha="abc123", check_name="Lint"
        )
        assert client.post_to_thread.call_count == 2
        assert "**Check passed:** ✅ CI" in client.post_to_thread.call_args_list[0][0][1]
        assert "**Check passed:** ✅ Lint" in client.post_to_thread.call_args_list[1][0][1]

    def test_approval_promotes_when_checks_passed(self):
        """When approval received and checks already passed, promote to Ready to merge."""
        tracker, client = _make_tracker()
        content = _make_pr(status=PRStatus.READY_FOR_REVIEW).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100,
            status=PRStatus.READY_FOR_REVIEW,
            content=content,
            checks_passed=True,
        )
        promoted = tracker.record_approval_and_maybe_promote("org/repo", 1)
        assert promoted is True
        client.update_message.assert_called_once()
        assert "Ready to merge" in client.update_message.call_args[0][1]

    def test_does_not_overwrite_with_minimal_when_content_empty(self):
        """When entry has no stored content and pr_msg is minimal, skip parent update to avoid corruption."""
        tracker, client = _make_tracker()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.OPEN, content=""
        )
        client.get_message.return_value = None
        client.get_messages.return_value = []
        minimal_pr = GitHubPRMessage(
            repo="org/repo",
            number=1,
            title="",
            author="",
            url="https://github.com/org/repo/pull/1",
            base_branch="",
            head_branch="",
            status=PRStatus.CHECKS_PASSED,
        )
        result = tracker.handle_pr_event(minimal_pr, create_if_missing=False)
        assert result == {"id": 100}
        client.update_message.assert_not_called()

    def test_fetches_content_via_get_message_when_empty(self):
        """When entry content is empty, try get_message before giving up."""
        tracker, client = _make_tracker()
        full_content = _make_pr(status=PRStatus.OPEN).to_parent()
        tracker._store[("org/repo", 1)] = _PREntry(
            message_id=100, status=PRStatus.OPEN, content=""
        )
        client.get_message.return_value = {"id": 100, "content": full_content}
        minimal_pr = GitHubPRMessage(
            repo="org/repo",
            number=1,
            title="",
            author="",
            url="https://github.com/org/repo/pull/1",
            base_branch="",
            head_branch="",
            status=PRStatus.CHECKS_PASSED,
        )
        result = tracker.handle_pr_event(minimal_pr, create_if_missing=False)
        assert result["id"] == 100
        client.get_message.assert_called_once_with(100)
        client.update_message.assert_called_once()
        updated = client.update_message.call_args[0][1]
        assert "**Status:** Ready to merge" in updated
