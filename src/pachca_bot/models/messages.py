"""Structured message models for composing rich Pachca messages.

Pachca messages support markdown formatting. These models provide a
composable, parametrized way to build readable messages from typed blocks.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

GITHUB_BASE = "https://github.com"


def _gh_user_link(login: str) -> str:
    return f"[{login}]({GITHUB_BASE}/{login})"


def _gh_repo_link(full_name: str) -> str:
    return f"[{full_name}]({GITHUB_BASE}/{full_name})"


def _gh_branch_link(repo: str, branch: str) -> str:
    return f"[{branch}]({GITHUB_BASE}/{repo}/tree/{branch})"


def _gh_commit_link(repo: str, sha: str) -> str:
    return f"[{sha[:8]}]({GITHUB_BASE}/{repo}/commit/{sha})"


def _gh_release_link(url: str, tag: str) -> str:
    return f"[{tag}]({url})"


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


class MessageBlock(BaseModel):
    """Base block — every block can render itself to markdown."""

    def render(self) -> str:
        raise NotImplementedError


class HeaderBlock(MessageBlock):
    """Markdown header (h1–h3)."""

    text: str
    level: Literal[1, 2, 3] = 1

    def render(self) -> str:
        prefix = "#" * self.level
        return f"{prefix} {self.text}"


class TextBlock(MessageBlock):
    """Plain or formatted text paragraph."""

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
    """Markdown hyperlink."""

    text: str
    url: str

    def render(self) -> str:
        return f"[{self.text}]({self.url})"


class FieldsBlock(MessageBlock):
    """Key-value table rendered as a bold-label list.

    Example output:
        **Status:** failure
        **Branch:** main
    """

    fields: dict[str, str]

    def render(self) -> str:
        lines = [f"**{k}:** {v}" for k, v in self.fields.items()]
        return "\n".join(lines)


class CodeBlock(MessageBlock):
    """Fenced code block with optional language tag."""

    code: str
    language: str = ""

    def render(self) -> str:
        return f"```{self.language}\n{self.code}\n```"


class QuoteBlock(MessageBlock):
    """Blockquote."""

    text: str

    def render(self) -> str:
        lines = self.text.split("\n")
        return "\n".join(f"> {line}" for line in lines)


class ListBlock(MessageBlock):
    """Bulleted or numbered list."""

    items: list[str]
    ordered: bool = False

    def render(self) -> str:
        result: list[str] = []
        for i, item in enumerate(self.items, 1):
            prefix = f"{i}." if self.ordered else "•"
            result.append(f"{prefix} {item}")
        return "\n".join(result)


class DividerBlock(MessageBlock):
    """Horizontal rule."""

    def render(self) -> str:
        return "---"


class StructuredMessage(BaseModel):
    """Composable message built from ordered blocks.

    Renders all blocks into a single markdown string suitable for
    ``Pachca.create_message(content=...)``.
    """

    blocks: list[MessageBlock] = Field(default_factory=list)

    def render(self) -> str:
        return "\n\n".join(block.render() for block in self.blocks)

    def add(self, block: MessageBlock) -> StructuredMessage:
        self.blocks.append(block)
        return self


# ---------------------------------------------------------------------------
# Pre-built parametrized message templates
# ---------------------------------------------------------------------------


class GitHubReleaseMessage(BaseModel):
    """GitHub release event → Pachca message."""

    repo: str
    tag: str
    release_name: str
    author: str
    url: str
    body: str = ""
    prerelease: bool = False

    def to_structured(self) -> StructuredMessage:
        severity = Severity.WARNING if self.prerelease else Severity.SUCCESS
        pre = "(pre-release) " if self.prerelease else ""
        tag_link = _gh_release_link(self.url, self.tag)
        header = f"{severity.emoji} Release {pre}{tag_link}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        msg.add(
            FieldsBlock(
                fields={
                    "Repository": _gh_repo_link(self.repo),
                    "Release": _gh_release_link(self.url, self.release_name),
                    "Tag": _gh_release_link(self.url, self.tag),
                    "Author": _gh_user_link(self.author),
                }
            )
        )
        if self.body:
            msg.add(QuoteBlock(text=self.body[:1000]))
        msg.add(LinkBlock(text="View release", url=self.url))
        return msg


class GitHubCheckFailureMessage(BaseModel):
    """GitHub check / workflow run failure → Pachca message."""

    repo: str
    workflow_name: str
    branch: str
    commit_sha: str
    conclusion: str
    url: str
    actor: str = ""

    def to_structured(self) -> StructuredMessage:
        severity = Severity.ERROR if self.conclusion == "failure" else Severity.WARNING
        header = f"{severity.emoji} CI: {self.workflow_name} — {self.conclusion}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        fields: dict[str, str] = {
            "Repository": _gh_repo_link(self.repo),
            "Branch": _gh_branch_link(self.repo, self.branch),
            "Commit": _gh_commit_link(self.repo, self.commit_sha),
            "Result": self.conclusion,
        }
        if self.actor:
            fields["Triggered by"] = _gh_user_link(self.actor)
        msg.add(FieldsBlock(fields=fields))
        msg.add(LinkBlock(text="View run", url=self.url))
        return msg


class GitHubPullRequestMessage(BaseModel):
    """GitHub pull request event → Pachca message."""

    repo: str
    action: str
    number: int
    title: str
    author: str
    url: str
    base_branch: str
    head_branch: str
    body: str = ""
    merged: bool = False
    draft: bool = False

    def to_structured(self) -> StructuredMessage:
        action_emojis = {
            "opened": "🆕",
            "closed": "✅" if self.merged else "🚫",
            "reopened": "🔄",
            "ready_for_review": "👀",
            "review_requested": "👁️",
        }
        emoji = action_emojis.get(self.action, "🔔")
        verb = "merged" if self.merged and self.action == "closed" else self.action
        header = f"{emoji} PR #{self.number} {verb}: {self.title}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        head_link = _gh_branch_link(self.repo, self.head_branch)
        base_link = _gh_branch_link(self.repo, self.base_branch)
        fields: dict[str, str] = {
            "Repository": _gh_repo_link(self.repo),
            "Author": _gh_user_link(self.author),
            "Branch": f"{head_link} → {base_link}",
        }
        if self.draft:
            fields["Draft"] = "yes"
        msg.add(FieldsBlock(fields=fields))
        if self.body:
            msg.add(QuoteBlock(text=self.body[:1000]))
        msg.add(LinkBlock(text="View pull request", url=self.url))
        return msg


class GitHubDeploymentMessage(BaseModel):
    """GitHub deployment / deployment_status event → Pachca message."""

    repo: str
    environment: str
    description: str = ""
    state: str = ""
    creator: str = ""
    sha: str = ""
    ref: str = ""
    url: str = ""

    def to_structured(self) -> StructuredMessage:
        state_emoji = {
            "success": "✅",
            "failure": "❌",
            "error": "❌",
            "pending": "⏳",
            "in_progress": "🔄",
            "queued": "📋",
            "inactive": "💤",
        }
        emoji = state_emoji.get(self.state, "🚀")
        state_label = self.state or "created"
        header = f"{emoji} Deployment {state_label}: {self.environment}"

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
        if self.state:
            fields["Status"] = state_label
        msg.add(FieldsBlock(fields=fields))
        if self.description:
            msg.add(TextBlock(text=self.description))
        if self.url:
            msg.add(LinkBlock(text="View deployment", url=self.url))
        return msg


class GenericAlertMessage(BaseModel):
    """Generic alert message from any integration."""

    source: str
    title: str
    severity: Severity = Severity.INFO
    details: str = ""
    fields: dict[str, str] = Field(default_factory=dict)
    url: str = ""

    def to_structured(self) -> StructuredMessage:
        header = f"{self.severity.emoji} [{self.source}] {self.title}"
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        if self.fields:
            msg.add(FieldsBlock(fields=self.fields))
        if self.details:
            msg.add(TextBlock(text=self.details))
        if self.url:
            msg.add(LinkBlock(text="Details", url=self.url))
        return msg


class GenericDeployMessage(BaseModel):
    """Deployment notification from a custom VM or CI."""

    source: str
    environment: str
    version: str
    status: Literal["started", "succeeded", "failed", "rolled_back"]
    actor: str = ""
    url: str = ""
    changelog: list[str] = Field(default_factory=list)

    def to_structured(self) -> StructuredMessage:
        status_emoji = {
            "started": "🚀",
            "succeeded": "✅",
            "failed": "❌",
            "rolled_back": "⏪",
        }
        emoji = status_emoji[self.status]
        header = f"{emoji} Deploy {self.status}: {self.source}"

        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        fields: dict[str, str] = {
            "Environment": self.environment,
            "Version": self.version,
            "Status": self.status,
        }
        if self.actor:
            fields["Deployed by"] = self.actor
        msg.add(FieldsBlock(fields=fields))
        if self.changelog:
            msg.add(ListBlock(items=self.changelog))
        if self.url:
            msg.add(LinkBlock(text="View deployment", url=self.url))
        return msg
