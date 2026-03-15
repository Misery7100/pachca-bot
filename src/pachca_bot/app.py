"""FastAPI application — exposes webhook endpoints for GitHub and generic integrations."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request

from pachca_bot.client import PachcaClient
from pachca_bot.config import (
    DISPLAY_NAME_GENERIC,
    DISPLAY_NAME_GITHUB,
    Settings,
    get_settings,
)
from pachca_bot.handlers.generic import handle_generic_event
from pachca_bot.handlers.github import handle_github_event
from pachca_bot.models.webhooks import (
    GenericWebhookPayload,
    GitHubWebhookPayload,
    WebhookResponse,
)
from pachca_bot.security import verify_bearer_token, verify_github_signature

logger = logging.getLogger(__name__)

_pachca_client: PachcaClient | None = None


def _get_client() -> PachcaClient:
    assert _pachca_client is not None, "PachcaClient not initialised"
    return _pachca_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pachca_client
    settings = get_settings()
    _pachca_client = PachcaClient(settings)
    logger.info("Pachca bot started — chat_id=%s", settings.pachca_chat_id)
    yield
    _pachca_client.close()
    _pachca_client = None


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Pachca Integration Bot",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # GitHub webhook
    # ------------------------------------------------------------------

    @app.post("/webhooks/github", response_model=WebhookResponse)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str = Header(""),
        x_github_event: str = Header(""),
    ) -> WebhookResponse:
        settings = get_settings()
        body = await request.body()

        if settings.github_webhook_secret:
            valid = verify_github_signature(
                x_hub_signature_256, body, settings.github_webhook_secret
            )
            if not valid:
                raise HTTPException(status_code=403, detail="Invalid signature")

        payload = GitHubWebhookPayload.model_validate_json(body)
        structured = handle_github_event(x_github_event, payload)

        if structured is None:
            return WebhookResponse(ok=True, detail="Event ignored")

        client = _get_client()
        content = structured.render()
        result = client.send_message(content, display_name=DISPLAY_NAME_GITHUB)
        return WebhookResponse(ok=True, message_id=result.get("id"), detail="Message sent")

    # ------------------------------------------------------------------
    # Generic webhook
    # ------------------------------------------------------------------

    @app.post("/webhooks/generic", response_model=WebhookResponse)
    async def generic_webhook(
        request: Request,
        authorization: str = Header(""),
    ) -> WebhookResponse:
        settings = get_settings()

        if settings.generic_webhook_secret:
            if not verify_bearer_token(authorization, settings.generic_webhook_secret):
                raise HTTPException(status_code=403, detail="Unauthorized")

        body = await request.body()
        payload = GenericWebhookPayload.model_validate_json(body)
        structured = handle_generic_event(payload)

        client = _get_client()
        content = structured.render()
        result = client.send_message(content, display_name=DISPLAY_NAME_GENERIC)
        return WebhookResponse(ok=True, message_id=result.get("id"), detail="Message sent")

    return app
