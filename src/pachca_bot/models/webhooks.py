"""Pydantic models for incoming webhook payloads and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from pachca_bot.models.messages import Severity

# ---------------------------------------------------------------------------
# Generic (abstract) webhook
# ---------------------------------------------------------------------------


class GenericWebhookPayload(BaseModel):
    """Payload for the abstract webhook endpoint.

    Callers send a JSON body with an event type and structured fields.
    The bot formats it and posts to Pachca.
    """

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


# ---------------------------------------------------------------------------
# GitHub webhook (only the fields we care about)
# ---------------------------------------------------------------------------


class _GitHubUser(BaseModel, extra="allow"):
    login: str = ""


class _GitHubRepo(BaseModel, extra="allow"):
    full_name: str = ""
    html_url: str = ""


class _GitHubRelease(BaseModel, extra="allow"):
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


class _GitHubCheckSuite(BaseModel, extra="allow"):
    conclusion: str | None = None
    head_branch: str = ""
    head_sha: str = ""


class _GitHubCheckRun(BaseModel, extra="allow"):
    name: str = ""
    conclusion: str | None = None
    html_url: str = ""
    check_suite: _GitHubCheckSuite = Field(default_factory=_GitHubCheckSuite)


class _GitHubPRHead(BaseModel, extra="allow"):
    ref: str = ""


class _GitHubPRBase(BaseModel, extra="allow"):
    ref: str = ""


class _GitHubPR(BaseModel, extra="allow"):
    number: int = 0
    title: str = ""
    body: str | None = ""
    html_url: str = ""
    user: _GitHubUser = Field(default_factory=_GitHubUser)
    head: _GitHubPRHead = Field(default_factory=_GitHubPRHead)
    base: _GitHubPRBase = Field(default_factory=_GitHubPRBase)
    merged: bool = False
    draft: bool = False


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
    pull_request: _GitHubPR | None = None
    deployment: _GitHubDeployment | None = None
    deployment_status: _GitHubDeploymentStatus | None = None

    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class WebhookResponse(BaseModel):
    ok: bool = True
    message_id: int | None = None
    detail: str = ""
