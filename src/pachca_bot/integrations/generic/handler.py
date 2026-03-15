"""Generic webhook handler — auth, parse, process, respond."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

from pachca_bot.core.blocks import StructuredMessage, TextBlock
from pachca_bot.integrations.generic.models import (
    DeployStatus,
    GenericAlertMessage,
    GenericDeployMessage,
    GenericWebhookPayload,
)
from pachca_bot.integrations.generic.security import verify_bearer_token

if TYPE_CHECKING:
    from pachca_bot.api.responses import WebhookResponse
    from pachca_bot.core.client import PachcaClient
    from pachca_bot.core.config import IntegrationConfig
    from pachca_bot.integrations.generic.deploy_tracker import DeployTracker


@dataclass
class GenericHandler:
    client: PachcaClient
    integration: IntegrationConfig
    deploy_tracker: DeployTracker | None
    webhook_secret: str

    async def handle(self, request: Request) -> WebhookResponse:
        from pachca_bot.api.responses import WebhookResponse

        if not self.webhook_secret:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Generic webhook secret not configured. "
                    "Set GENERIC__WEBHOOK_SECRET to enable this endpoint."
                ),
            )
        auth = request.headers.get("X-Authorization", "")
        if not verify_bearer_token(auth, self.webhook_secret):
            raise HTTPException(status_code=403, detail="Unauthorized")

        body = await request.body()
        payload = GenericWebhookPayload.model_validate_json(body)

        result = self._process(payload)

        if isinstance(result, dict):
            return WebhookResponse(
                ok=True,
                message_id=result.get("id"),
                detail="Deploy tracked",
            )

        display_name = payload.display_name or self.integration.display_name
        display_avatar_url = payload.display_avatar_url or self.integration.display_avatar_url
        content = result.render()
        api_result = self.client.send_message(
            content,
            display_name=display_name,
            display_avatar_url=display_avatar_url,
            chat_id=self.integration.chat_id,
        )
        return WebhookResponse(
            ok=True,
            message_id=api_result.get("id"),
            detail="Message sent",
        )

    def _process(self, payload: GenericWebhookPayload) -> StructuredMessage | dict:
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
                body=payload.body,
            )

            if payload.deploy_id and self.deploy_tracker is not None:
                return self.deploy_tracker.handle_deploy_event(
                    deploy_msg,
                    display_name=payload.display_name,
                    display_avatar_url=payload.display_avatar_url,
                )

            return StructuredMessage().add(TextBlock(text=deploy_msg.to_parent()))

        return GenericAlertMessage(
            source=payload.source,
            title=payload.title,
            severity=payload.severity,
            details=payload.details,
            fields=payload.fields,
            url=payload.url,
        ).to_structured()
