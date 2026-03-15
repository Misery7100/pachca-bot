"""Generic webhook payload and message models."""

from __future__ import annotations

from enum import Enum

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


class GenericWebhookPayload(BaseModel):
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
    body: str = ""
    deploy_id: str = ""
    display_name: str | None = None
    display_avatar_url: str | None = None


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
    body: str = ""

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
        if self.body:
            msg.add(TextBlock(text=self.body.strip()))
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
