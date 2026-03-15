"""Generic (abstract) webhook handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pachca_bot.models.messages import (
    DeployStatus,
    GenericAlertMessage,
    GenericDeployMessage,
    StructuredMessage,
    TextBlock,
)
from pachca_bot.models.webhooks import GenericWebhookPayload

if TYPE_CHECKING:
    from pachca_bot.deploy_tracker import DeployTracker

logger = logging.getLogger(__name__)


def handle_generic_event(
    payload: GenericWebhookPayload,
    deploy_tracker: DeployTracker | None = None,
) -> StructuredMessage | dict:
    """Build a structured message from a generic webhook payload.

    For deploy events with a deploy_id and a tracker, returns a dict
    (handled by DeployTracker directly). Otherwise returns StructuredMessage.
    """
    if payload.event_type == "deploy":
        try:
            status = DeployStatus(payload.status) if payload.status else DeployStatus.STARTED
        except ValueError:
            status = DeployStatus.STARTED

        deploy_msg = GenericDeployMessage(
            source=payload.source,
            environment=payload.environment or "unknown",
            version=payload.version or "unknown",
            status=status,
            deploy_id=payload.deploy_id,
            actor=payload.actor,
            url=payload.url,
            changelog=payload.changelog,
        )

        if payload.deploy_id and deploy_tracker is not None:
            return deploy_tracker.handle_deploy_event(deploy_msg)

        return StructuredMessage().add(TextBlock(text=deploy_msg.to_parent()))

    return GenericAlertMessage(
        source=payload.source,
        title=payload.title,
        severity=payload.severity,
        details=payload.details,
        fields=payload.fields,
        url=payload.url,
    ).to_structured()
