"""Tests for message models and rendering."""

from pachca_bot.core.blocks import patch_status_in_content, render_status_update
from pachca_bot.integrations.generic.models import (
    DeployStatus,
    GenericAlertMessage,
    GenericDeployMessage,
    Severity,
)
from pachca_bot.integrations.github.models import (
    GHDeployState,
    GitHubCIMessage,
    GitHubDeploymentMessage,
    GitHubPRMessage,
    GitHubReleaseMessage,
    PRStatus,
)


class TestStatusUpdate:
    def test_format_has_emoji_and_bold(self):
        result = render_status_update("📝", "Draft", "🆕", "Open")
        assert "Status updated:\n\n**Before:** 📝 Draft\n**After:** 🆕 Open" == result


class TestPatchStatus:
    def test_replaces_emoji_and_status_field(self):
        content = "## 📝 PR [#1](https://github.com/o/r/pull/1): Title\n\n**Status:** Draft"
        patched = patch_status_in_content(content, "🟣", "Merged")
        assert patched.startswith("## 🟣 ")
        assert "📝" not in patched
        assert "**Status:** Merged" in patched


class TestReleaseMessage:
    def test_body_heading_stripped(self):
        m = GitHubReleaseMessage(
            repo="org/repo",
            tag="v1.0.0",
            release_name="v1.0.0",
            author="alice",
            url="https://github.com/org/repo/releases/tag/v1.0.0",
            body="### Changelog\n- Fixed auth\n- Added caching",
        )
        rendered = m.to_structured().render()
        assert "###" not in rendered
        assert "Changelog" in rendered
        assert "- Fixed auth" in rendered
        assert "[View release](" in rendered

    def test_no_body_renders_cleanly(self):
        m = GitHubReleaseMessage(
            repo="org/repo",
            tag="v1.0",
            release_name="v1.0",
            author="alice",
            url="https://github.com/org/repo/releases/tag/v1.0",
        )
        rendered = m.to_structured().render()
        assert "[alice](https://github.com/alice)" in rendered
        assert "[View release](" in rendered


class TestCIMessage:
    def test_channel_has_repo(self):
        m = GitHubCIMessage(
            workflow_name="CI",
            commit_sha="abc12345678",
            repo="org/repo",
            conclusion="failure",
            url="https://github.com/org/repo/actions/runs/1",
        )
        assert "[org/repo](" in m.to_structured().render()

    def test_pr_thread_no_repo(self):
        m = GitHubCIMessage(
            workflow_name="CI",
            commit_sha="abc12345678",
            repo="org/repo",
            conclusion="failure",
            url="https://github.com/org/repo/actions/runs/1",
            for_pr_thread=True,
        )
        assert "[org/repo](" not in m.to_structured().render()


class TestPRMessage:
    def _make_pr(self, status: PRStatus = PRStatus.OPEN) -> GitHubPRMessage:
        return GitHubPRMessage(
            repo="org/repo",
            number=42,
            title="Fix bug",
            author="alice",
            url="https://github.com/org/repo/pull/42",
            base_branch="main",
            head_branch="fix-bug",
            body="Description",
            status=status,
        )

    def test_parent_status_plain_text(self):
        rendered = self._make_pr(PRStatus.OPEN).to_parent()
        assert "**Status:** Open" in rendered
        assert "## 🆕 PR" in rendered

    def test_thread_update_has_emoji(self):
        pr = self._make_pr(PRStatus.READY_FOR_REVIEW)
        update = pr.to_thread_update(old_status=PRStatus.OPEN)
        assert "**Before:** 🆕 Open" in update
        assert "**After:** 👀 Ready for review" in update

    def test_reopened_status(self):
        pr = self._make_pr(PRStatus.REOPENED)
        rendered = pr.to_parent()
        assert "## 🔄 PR" in rendered
        assert "**Status:** Reopened" in rendered

    def test_patch_preserves_content(self):
        original = self._make_pr(PRStatus.OPEN).to_parent()
        patched = GitHubPRMessage.patch_parent_status(original, PRStatus.MERGED)
        assert "## 🟣 " in patched
        assert "🆕" not in patched
        assert "**Status:** Merged" in patched
        assert "[alice](" in patched
        assert "Fix bug" in patched


class TestGHDeployMessage:
    def test_to_parent(self):
        m = GitHubDeploymentMessage(
            repo="org/repo",
            environment="production",
            state="success",
            creator="alice",
            sha="abc12345678",
            ref="main",
            url="https://github.com/org/repo/deployments",
        )
        rendered = m.to_parent()
        assert "## ✅ Deployment: production" in rendered
        assert "**Status:** Success" in rendered
        assert "[alice](" in rendered

    def test_thread_update(self):
        m = GitHubDeploymentMessage(
            repo="org/repo",
            environment="prod",
            state="success",
        )
        update = m.to_thread_update(GHDeployState.PENDING)
        assert "**Before:** ⏳ Pending" in update
        assert "**After:** ✅ Success" in update

    def test_patch_status(self):
        m = GitHubDeploymentMessage(
            repo="org/repo",
            environment="production",
            state="pending",
            creator="alice",
            sha="abc123",
            ref="main",
        )
        original = m.to_parent()
        patched = GitHubDeploymentMessage.patch_parent_status(original, GHDeployState.SUCCESS)
        assert "## ✅ " in patched
        assert "⏳" not in patched
        assert "**Status:** Success" in patched
        assert "production" in patched


class TestGenericAlert:
    def test_source_as_field(self):
        m = GenericAlertMessage(
            source="monitoring",
            title="Disk usage",
            severity=Severity.WARNING,
            fields={"Host": "vm-01"},
        )
        rendered = m.to_structured().render()
        assert "**Source:** monitoring" in rendered


class TestGenericDeploy:
    def test_format(self):
        m = GenericDeployMessage(
            source="api",
            environment="prod",
            version="2.3.1",
            status=DeployStatus.STARTED,
            deploy_id="dep-42",
            actor="deployer",
        )
        rendered = m.to_parent()
        assert "## 🚀 Deployment: api" in rendered
        assert "**ID:** dep-42" in rendered
        assert "**Status:** Started" in rendered

    def test_thread_update_has_emoji(self):
        m = GenericDeployMessage(
            source="api",
            environment="prod",
            version="1.0",
            status=DeployStatus.SUCCEEDED,
        )
        update = m.to_thread_update(DeployStatus.STARTED)
        assert "**Before:** 🚀 Started" in update
        assert "**After:** ✅ Succeeded" in update

    def test_patch_status(self):
        m = GenericDeployMessage(
            source="api",
            environment="prod",
            version="1.0",
            status=DeployStatus.STARTED,
        )
        original = m.to_parent()
        patched = GenericDeployMessage.patch_parent_status(original, DeployStatus.SUCCEEDED)
        assert "## ✅ " in patched
        assert "🚀" not in patched
        assert "**Status:** Succeeded" in patched
