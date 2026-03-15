"""GitHub webhook payload and message models."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pachca_bot.core.blocks import (
    FieldsBlock,
    HeaderBlock,
    LinkBlock,
    StructuredMessage,
    TextBlock,
    patch_status_in_content,
    render_status_update,
)

GITHUB_BASE = "https://github.com"
MD_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def gh_user_link(login: str) -> str:
    if login.endswith("[bot]"):
        return login
    return f"[{login}]({GITHUB_BASE}/{login})"


def gh_repo_link(full_name: str) -> str:
    return f"[{full_name}]({GITHUB_BASE}/{full_name})"


def gh_branch_link(repo: str, branch: str) -> str:
    return f"[{branch}]({GITHUB_BASE}/{repo}/tree/{branch})"


def gh_commit_link(repo: str, sha: str) -> str:
    return f"[{sha[:8]}]({GITHUB_BASE}/{repo}/commit/{sha})"


def gh_release_link(url: str, label: str) -> str:
    return f"[{label}]({url})"


def gh_pr_link(repo: str, number: int) -> str:
    return f"[#{number}]({GITHUB_BASE}/{repo}/pull/{number})"


def strip_md_headings(text: str) -> str:
    return MD_HEADING_RE.sub("", text)


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
# Payload models
# ---------------------------------------------------------------------------


class GitHubUser(BaseModel, extra="allow"):
    login: str = ""


class GitHubRepo(BaseModel, extra="allow"):
    full_name: str = ""
    html_url: str = ""


class GitHubRelease(BaseModel, extra="allow"):
    action: str = ""
    tag_name: str = ""
    name: str = ""
    body: str = ""
    html_url: str = ""
    prerelease: bool = False
    author: GitHubUser = Field(default_factory=GitHubUser)


class GitHubWorkflowPR(BaseModel, extra="allow"):
    number: int = 0


class GitHubWorkflowRun(BaseModel, extra="allow"):
    name: str = ""
    head_branch: str = ""
    head_sha: str = ""
    conclusion: str | None = None
    html_url: str = ""
    actor: GitHubUser = Field(default_factory=GitHubUser)
    pull_requests: list[GitHubWorkflowPR] = Field(default_factory=list)


class GitHubCheckSuite(BaseModel, extra="allow"):
    conclusion: str | None = None
    head_branch: str = ""
    head_sha: str = ""


class GitHubCheckRun(BaseModel, extra="allow"):
    name: str = ""
    conclusion: str | None = None
    html_url: str = ""
    check_suite: GitHubCheckSuite = Field(default_factory=GitHubCheckSuite)


class GitHubPRRef(BaseModel, extra="allow"):
    ref: str = ""
    sha: str = ""


class GitHubPR(BaseModel, extra="allow"):
    number: int = 0
    title: str = ""
    body: str | None = ""
    html_url: str = ""
    state: str = ""
    user: GitHubUser = Field(default_factory=GitHubUser)
    head: GitHubPRRef = Field(default_factory=GitHubPRRef)
    base: GitHubPRRef = Field(default_factory=GitHubPRRef)
    merged: bool = False
    draft: bool = False
    mergeable_state: str | None = None


class GitHubLabel(BaseModel, extra="allow"):
    name: str = ""


class GitHubReview(BaseModel, extra="allow"):
    state: str = ""
    user: GitHubUser = Field(default_factory=GitHubUser)


class GitHubCheckSuitePR(BaseModel, extra="allow"):
    number: int = 0


class GitHubCheckSuiteTop(BaseModel, extra="allow"):
    id: int = 0
    head_branch: str = ""
    head_sha: str = ""
    status: str = ""
    conclusion: str | None = None
    pull_requests: list[GitHubCheckSuitePR] = Field(default_factory=list)


class GitHubDeployment(BaseModel, extra="allow"):
    id: int = 0
    sha: str = ""
    ref: str = ""
    environment: str = ""
    description: str | None = ""
    creator: GitHubUser = Field(default_factory=GitHubUser)


class GitHubDeploymentStatus(BaseModel, extra="allow"):
    state: str = ""
    description: str | None = ""
    target_url: str | None = ""
    log_url: str | None = ""


GitHubCheckSuiteTop.model_rebuild()
GitHubWorkflowRun.model_rebuild()


class GitHubWebhookPayload(BaseModel, extra="allow"):
    action: str = ""
    repository: GitHubRepo = Field(default_factory=GitHubRepo)
    sender: GitHubUser = Field(default_factory=GitHubUser)
    release: GitHubRelease | None = None
    workflow_run: GitHubWorkflowRun | None = None
    check_run: GitHubCheckRun | None = None
    check_suite: GitHubCheckSuiteTop | None = None
    pull_request: GitHubPR | None = None
    deployment: GitHubDeployment | None = None
    deployment_status: GitHubDeploymentStatus | None = None
    review: GitHubReview | None = None
    label: GitHubLabel | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


# ---------------------------------------------------------------------------
# Message templates
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
        release_link = gh_release_link(self.url, self.tag)
        header = f"🔖 Release: {release_link} {pre}"
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        msg.add(
            FieldsBlock(
                fields={
                    "Repository": gh_repo_link(self.repo),
                    "Author": gh_user_link(self.author),
                }
            )
        )
        if self.body:
            cleaned = strip_md_headings(self.body.strip())
            msg.add(TextBlock(text=cleaned))
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
            fields["Repository"] = gh_repo_link(self.repo)
        fields["Commit"] = gh_commit_link(self.repo, self.commit_sha)
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
        pr_link = gh_pr_link(self.repo, self.number)
        header = f"{self.status.emoji} PR {pr_link}: {self.title}"
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=header, level=2))
        head_link = gh_branch_link(self.repo, self.head_branch)
        base_link = gh_branch_link(self.repo, self.base_branch)
        fields: dict[str, str] = {
            "Repository": gh_repo_link(self.repo),
            "Author": gh_user_link(self.author),
            "Branch": f"{head_link} → {base_link}",
            "Status": self.status.label,
        }
        msg.add(FieldsBlock(fields=fields))
        if self.body:
            msg.add(TextBlock(text=self.body))
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
            "Repository": gh_repo_link(self.repo),
            "Environment": self.environment,
        }
        if self.ref:
            fields["Ref"] = gh_branch_link(self.repo, self.ref)
        if self.sha:
            fields["Commit"] = gh_commit_link(self.repo, self.sha)
        if self.creator:
            fields["Deployed by"] = gh_user_link(self.creator)
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
