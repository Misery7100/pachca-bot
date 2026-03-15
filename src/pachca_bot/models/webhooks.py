"""Pydantic models for incoming webhook payloads and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from pachca_bot.models.messages import Severity

# ---------------------------------------------------------------------------
# Generic (abstract) webhook
# ---------------------------------------------------------------------------


class GenericWebhookPayload(BaseModel):
    """Payload for the abstract webhook endpoint."""

    event_type: str = Field(
        ...,
        description="Type of event, e.g. 'deploy', 'alert', 'metric', 'custom'",
    )
    source: str = Field(
        ..., description="Origin system, e.g. 'vm-prod-01', 'monitoring'"
    )
    title: str
    severity: Severity = Severity.INFO
    details: str = ""
    fields: dict[str, str] = Field(default_factory=dict)
    url: str = ""

    environment: str = ""
    version: str = ""
    status: str = ""
    actor: str = ""
    changelog: list[str] = Field(default_factory=list)
    deploy_id: str = ""


# ---------------------------------------------------------------------------
# GitHub webhook (only the fields we care about)
# ---------------------------------------------------------------------------


class _GitHubUser(BaseModel, extra="allow"):
    login: str = ""


class _GitHubRepo(BaseModel, extra="allow"):
    full_name: str = ""
    html_url: str = ""


class _GitHubRelease(BaseModel, extra="allow"):
    action: str = ""
    tag_name: str = ""
    name: str = ""
    body: str = ""
    html_url: str = ""
    prerelease: bool = False
    author: _GitHubUser = Field(default_factory=_GitHubUser)


class _GitHubWorkflowRun(BaseModel, extra="allow"):
    name: str = ""
    head_branch: str = ""
    head_sha: str = ""
    conclusion: str | None = None
    html_url: str = ""
    actor: _GitHubUser = Field(default_factory=_GitHubUser)
    pull_requests: list[_GitHubWorkflowPR] = Field(default_factory=list)


class _GitHubWorkflowPR(BaseModel, extra="allow"):
    number: int = 0


class _GitHubCheckSuite(BaseModel, extra="allow"):
    conclusion: str | None = None
    head_branch: str = ""
    head_sha: str = ""


class _GitHubCheckRun(BaseModel, extra="allow"):
    name: str = ""
    conclusion: str | None = None
    html_url: str = ""
    check_suite: _GitHubCheckSuite = Field(default_factory=_GitHubCheckSuite)


class _GitHubPRRef(BaseModel, extra="allow"):
    ref: str = ""
    sha: str = ""


class _GitHubPR(BaseModel, extra="allow"):
    number: int = 0
    title: str = ""
    body: str | None = ""
    html_url: str = ""
    state: str = ""
    user: _GitHubUser = Field(default_factory=_GitHubUser)
    head: _GitHubPRRef = Field(default_factory=_GitHubPRRef)
    base: _GitHubPRRef = Field(default_factory=_GitHubPRRef)
    merged: bool = False
    draft: bool = False
    mergeable_state: str | None = None


class _GitHubLabel(BaseModel, extra="allow"):
    name: str = ""


class _GitHubReview(BaseModel, extra="allow"):
    state: str = ""
    user: _GitHubUser = Field(default_factory=_GitHubUser)


class _GitHubCheckSuiteTop(BaseModel, extra="allow"):
    """Top-level check_suite object in check_suite events."""

    id: int = 0
    head_branch: str = ""
    head_sha: str = ""
    status: str = ""
    conclusion: str | None = None
    pull_requests: list[_GitHubCheckSuitePR] = Field(default_factory=list)


class _GitHubCheckSuitePR(BaseModel, extra="allow"):
    """Minimal PR reference inside a check_suite payload."""

    number: int = 0


# Resolve forward references
_GitHubCheckSuiteTop.model_rebuild()
_GitHubWorkflowRun.model_rebuild()


class _GitHubDeployment(BaseModel, extra="allow"):
    id: int = 0
    sha: str = ""
    ref: str = ""
    environment: str = ""
    description: str | None = ""
    creator: _GitHubUser = Field(default_factory=_GitHubUser)


class _GitHubDeploymentStatus(BaseModel, extra="allow"):
    state: str = ""
    description: str | None = ""
    target_url: str | None = ""
    log_url: str | None = ""


class GitHubWebhookPayload(BaseModel, extra="allow"):
    """Top-level GitHub webhook payload — loosely typed to tolerate any event."""

    action: str = ""

    repository: _GitHubRepo = Field(default_factory=_GitHubRepo)
    sender: _GitHubUser = Field(default_factory=_GitHubUser)

    release: _GitHubRelease | None = None
    workflow_run: _GitHubWorkflowRun | None = None
    check_run: _GitHubCheckRun | None = None
    check_suite: _GitHubCheckSuiteTop | None = None
    pull_request: _GitHubPR | None = None
    deployment: _GitHubDeployment | None = None
    deployment_status: _GitHubDeploymentStatus | None = None
    review: _GitHubReview | None = None
    label: _GitHubLabel | None = None

    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class WebhookResponse(BaseModel):
    ok: bool = True
    message_id: int | None = None
    detail: str = ""
