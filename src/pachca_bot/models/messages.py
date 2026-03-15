"""Structured message models for composing rich Pachca messages.

Pachca messages support markdown formatting. These models provide a
composable, parametrized way to build readable messages from typed blocks.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

GITHUB_BASE = "https://github.com"

_HEADER_EMOJI_RE = re.compile(r"^(## )\S+( )", re.MULTILINE)
_STATUS_FIELD_RE = re.compile(r"^\*\*Status:\*\* .+$", re.MULTILINE)
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def _gh_user_link(login: str) -> str:
    return f"[{login}]({GITHUB_BASE}/{login})"


def _gh_repo_link(full_name: str) -> str:
    return f"[{full_name}]({GITHUB_BASE}/{full_name})"


def _gh_branch_link(repo: str, branch: str) -> str:
    return f"[{branch}]({GITHUB_BASE}/{repo}/tree/{branch})"


def _gh_commit_link(repo: str, sha: str) -> str:
    return f"[{sha[:8]}]({GITHUB_BASE}/{repo}/commit/{sha})"


def _gh_release_link(url: str, label: str) -> str:
    return f"[{label}]({url})"


def _gh_pr_link(repo: str, number: int) -> str:
    return f"[#{number}]({GITHUB_BASE}/{repo}/pull/{number})"


def _strip_md_headings(text: str) -> str:
    """Remove markdown heading markers (# ## ###) from text."""
    return _MD_HEADING_RE.sub("", text)


class Severity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def emoji(self) -> str:
        return {
            Severity.INFO: "ℹ️",
            Severity.SUCCESS: "✅",
            Severity.WARNING: "⚠️",
            Severity.ERROR: "❌",
            Severity.CRITICAL: "🔥",
        }[self]


class PRStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    REOPENED = "reopened"
    READY_FOR_REVIEW = "ready_for_review"
    CHECKS_PASSED = "checks_passed"
    MERGED = "merged"
    CLOSED = "closed"

    @property
    def emoji(self) -> str:
        return {
            PRStatus.DRAFT: "📝",
            PRStatus.OPEN: "🆕",
            PRStatus.REOPENED: "🔄",
            PRStatus.READY_FOR_REVIEW: "👀",
            PRStatus.CHECKS_PASSED: "✅",
            PRStatus.MERGED: "🟣",
            PRStatus.CLOSED: "🚫",
        }[self]

    @property
    def label(self) -> str:
        return {
            PRStatus.DRAFT: "Draft",
            PRStatus.OPEN: "Open",
            PRStatus.REOPENED: "Reopened",
            PRStatus.READY_FOR_REVIEW: "Ready for review",
            PRStatus.CHECKS_PASSED: "Ready to merge",
            PRStatus.MERGED: "Merged",
            PRStatus.CLOSED: "Closed",
        }[self]


class DeployStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

    @property
    def emoji(self) -> str:
        return {
            DeployStatus.STARTED: "🚀",
            DeployStatus.SUCCEEDED: "✅",
            DeployStatus.FAILED: "❌",
            DeployStatus.ROLLED_BACK: "⏪",
        }[self]

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class GHDeployState(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    INACTIVE = "inactive"

    @property
    def emoji(self) -> str:
        return {
            GHDeployState.CREATED: "🚀",
            GHDeployState.PENDING: "⏳",
            GHDeployState.IN_PROGRESS: "🔄",
            GHDeployState.QUEUED: "📋",
            GHDeployState.SUCCESS: "✅",
            GHDeployState.FAILURE: "❌",
            GHDeployState.ERROR: "❌",
            GHDeployState.INACTIVE: "💤",
        }[self]

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Block primitives
# ---------------------------------------------------------------------------


class MessageBlock(BaseModel):
    def render(self) -> str:
        raise NotImplementedError


class HeaderBlock(MessageBlock):
    text: str
    level: Literal[1, 2, 3] = 1

    def render(self) -> str:
        prefix = "#" * self.level
        return f"{prefix} {self.text}"


class TextBlock(MessageBlock):
    text: str
    bold: bool = False
    italic: bool = False

    def render(self) -> str:
        t = self.text
        if self.bold:
            t = f"**{t}**"
        if self.italic:
            t = f"*{t}*"
        return t


class LinkBlock(MessageBlock):
    text: str
    url: str

    def render(self) -> str:
        return f"[{self.text}]({self.url})"


class FieldsBlock(MessageBlock):
    fields: dict[str, str]

    def render(self) -> str:
        lines = [f"**{k}:** {v}" for k, v in self.fields.items()]
        return "\n".join(lines)


class CodeBlock(MessageBlock):
    code: str
    language: str = ""

    def render(self) -> str:
        return f"```{self.language}\n{self.code}\n```"


class QuoteBlock(MessageBlock):
    text: str

    def render(self) -> str:
        lines = self.text.split("\n")
        return "\n".join(f"> {line}" for line in lines)


class ListBlock(MessageBlock):
    items: list[str]
    ordered: bool = False

    def render(self) -> str:
        result: list[str] = []
        for i, item in enumerate(self.items, 1):
            prefix = f"{i}." if self.ordered else "•"
            result.append(f"{prefix} {item}")
        return "\n".join(result)


class DividerBlock(MessageBlock):
    def render(self) -> str:
        return "---"


class StructuredMessage(BaseModel):
    blocks: list[MessageBlock] = Field(default_factory=list)

    def render(self) -> str:
        return "\n\n".join(block.render() for block in self.blocks)

    def add(self, block: MessageBlock) -> StructuredMessage:
        self.blocks.append(block)
        return self


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def render_status_update(
    before_emoji: str,
    before_label: str,
    after_emoji: str,
    after_label: str,
) -> str:
    return (
        f"Status updated:\n\n"
        f"**Before:** {before_emoji} {before_label}\n"
        f"**After:** {after_emoji} {after_label}"
    )


def patch_status_in_content(content: str, new_emoji: str, new_label: str) -> str:
    """Replace the leading emoji in the header and the Status field value."""
    result = _HEADER_EMOJI_RE.sub(rf"\g<1>{new_emoji}\2", content, count=1)
    result = _STATUS_FIELD_RE.sub(f"**Status:** {new_label}", result)
    return result


# ---------------------------------------------------------------------------
# GitHub message templates
# ---------------------------------------------------------------------------


class GitHubReleaseMessage(BaseModel):
    repo: str
    tag: str
    release_name: str
    author: str
    url: str
    body: str = ""
    prerelease: bool = False

    def to_structured(self) -> StructuredMessage:
        pre = "(pre-release) " if self.prerelease else ""
        release_link = _gh_release_link(self.url, self.tag)
        header = f"🔖 Release: {pre}{release_link}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        msg.add(
            FieldsBlock(
                fields={
                    "Repository": _gh_repo_link(self.repo),
                    "Author": _gh_user_link(self.author),
                }
            )
        )
        if self.body:
            cleaned = _strip_md_headings(self.body.strip())
            msg.add(TextBlock(text=cleaned[:1000]))
        msg.add(LinkBlock(text="View release", url=self.url))
        return msg


class GitHubCIMessage(BaseModel):
    workflow_name: str
    commit_sha: str
    repo: str
    conclusion: str
    url: str
    for_pr_thread: bool = False

    def to_structured(self) -> StructuredMessage:
        severity = Severity.ERROR if self.conclusion == "failure" else Severity.WARNING
        header = f"{severity.emoji} CI: {self.workflow_name} — {self.conclusion}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        fields: dict[str, str] = {}
        if not self.for_pr_thread:
            fields["Repository"] = _gh_repo_link(self.repo)
        fields["Commit"] = _gh_commit_link(self.repo, self.commit_sha)
        fields["Result"] = self.conclusion
        msg.add(FieldsBlock(fields=fields))
        msg.add(LinkBlock(text="View run", url=self.url))
        return msg


class GitHubPRMessage(BaseModel):
    repo: str
    number: int
    title: str
    author: str
    url: str
    base_branch: str
    head_branch: str
    status: PRStatus
    body: str = ""

    def to_parent(self) -> str:
        pr_link = _gh_pr_link(self.repo, self.number)
        header = f"{self.status.emoji} PR {pr_link}: {self.title}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        head_link = _gh_branch_link(self.repo, self.head_branch)
        base_link = _gh_branch_link(self.repo, self.base_branch)
        fields: dict[str, str] = {
            "Repository": _gh_repo_link(self.repo),
            "Author": _gh_user_link(self.author),
            "Branch": f"{head_link} → {base_link}",
            "Status": self.status.label,
        }
        msg.add(FieldsBlock(fields=fields))
        if self.body:
            msg.add(TextBlock(text=self.body[:500]))
        msg.add(LinkBlock(text="View pull request", url=self.url))
        return msg.render()

    def to_thread_update(self, old_status: PRStatus | None = None) -> str:
        if old_status:
            return render_status_update(
                old_status.emoji,
                old_status.label,
                self.status.emoji,
                self.status.label,
            )
        return f"{self.status.emoji} {self.status.label}"

    @staticmethod
    def patch_parent_status(content: str, new_status: PRStatus) -> str:
        return patch_status_in_content(content, new_status.emoji, new_status.label)


class GitHubDeploymentMessage(BaseModel):
    """GitHub deployment — supports thread-based tracking."""

    repo: str
    environment: str
    description: str = ""
    state: str = ""
    creator: str = ""
    sha: str = ""
    ref: str = ""
    url: str = ""

    def _resolve_state(self) -> GHDeployState:
        try:
            return GHDeployState(self.state)
        except ValueError:
            return GHDeployState.CREATED

    def to_parent(self) -> str:
        ds = self._resolve_state()
        header = f"{ds.emoji} Deployment: {self.environment}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        fields: dict[str, str] = {
            "Repository": _gh_repo_link(self.repo),
            "Environment": self.environment,
        }
        if self.ref:
            fields["Ref"] = _gh_branch_link(self.repo, self.ref)
        if self.sha:
            fields["Commit"] = _gh_commit_link(self.repo, self.sha)
        if self.creator:
            fields["Deployed by"] = _gh_user_link(self.creator)
        fields["Status"] = ds.label
        msg.add(FieldsBlock(fields=fields))
        if self.description:
            msg.add(TextBlock(text=self.description))
        if self.url:
            msg.add(LinkBlock(text="View deployment", url=self.url))
        return msg.render()

    def to_thread_update(self, old_state: GHDeployState) -> str:
        ds = self._resolve_state()
        return render_status_update(
            old_state.emoji,
            old_state.label,
            ds.emoji,
            ds.label,
        )

    @staticmethod
    def patch_parent_status(content: str, new_state: GHDeployState) -> str:
        return patch_status_in_content(content, new_state.emoji, new_state.label)


# ---------------------------------------------------------------------------
# Generic message templates
# ---------------------------------------------------------------------------


class GenericAlertMessage(BaseModel):
    source: str
    title: str
    severity: Severity = Severity.INFO
    details: str = ""
    fields: dict[str, str] = Field(default_factory=dict)
    url: str = ""

    def to_structured(self) -> StructuredMessage:
        header = f"{self.severity.emoji} {self.title}"
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        combined: dict[str, str] = {"Source": self.source}
        combined.update(self.fields)
        msg.add(FieldsBlock(fields=combined))
        if self.details:
            msg.add(TextBlock(text=self.details))
        if self.url:
            msg.add(LinkBlock(text="Details", url=self.url))
        return msg


class GenericDeployMessage(BaseModel):
    source: str
    environment: str
    version: str
    status: DeployStatus
    deploy_id: str = ""
    actor: str = ""
    url: str = ""
    changelog: list[str] = Field(default_factory=list)

    def to_parent(self) -> str:
        header = f"{self.status.emoji} Deployment: {self.source}"
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        fields: dict[str, str] = {}
        if self.deploy_id:
            fields["ID"] = self.deploy_id
        fields["Environment"] = self.environment
        fields["Version"] = self.version
        fields["Status"] = self.status.label
        if self.actor:
            fields["Deployed by"] = self.actor
        msg.add(FieldsBlock(fields=fields))
        if self.changelog:
            msg.add(ListBlock(items=self.changelog))
        if self.url:
            msg.add(LinkBlock(text="View deployment", url=self.url))
        return msg.render()

    def to_thread_update(self, old_status: DeployStatus) -> str:
        return render_status_update(
            old_status.emoji,
            old_status.label,
            self.status.emoji,
            self.status.label,
        )

    @staticmethod
    def patch_parent_status(content: str, new_status: DeployStatus) -> str:
        return patch_status_in_content(content, new_status.emoji, new_status.label)
