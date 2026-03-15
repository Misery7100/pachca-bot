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
from pachca_bot.deploy_tracker import DeployTracker
from pachca_bot.gh_deploy_tracker import GHDeployTracker
from pachca_bot.handlers.generic import handle_generic_event
from pachca_bot.handlers.github import handle_github_event
from pachca_bot.models.messages import StructuredMessage
from pachca_bot.models.webhooks import (
    GenericWebhookPayload,
    GitHubWebhookPayload,
    WebhookResponse,
)
from pachca_bot.pr_tracker import PRTracker
from pachca_bot.security import verify_bearer_token, verify_github_signature

logger = logging.getLogger(__name__)

_pachca_client: PachcaClient | None = None
_pr_tracker: PRTracker | None = None
_deploy_tracker: DeployTracker | None = None
_gh_deploy_tracker: GHDeployTracker | None = None


def _get_client() -> PachcaClient:
    assert _pachca_client is not None, "PachcaClient not initialised"
    return _pachca_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pachca_client, _pr_tracker, _deploy_tracker, _gh_deploy_tracker
    settings = get_settings()
    _pachca_client = PachcaClient(settings)
    _pr_tracker = PRTracker(_pachca_client)
    _deploy_tracker = DeployTracker(_pachca_client)
    _gh_deploy_tracker = GHDeployTracker(_pachca_client)
    logger.info("Pachca bot started — chat_id=%s", settings.pachca_chat_id)
    yield
    _pachca_client.close()
    _pachca_client = None
    _pr_tracker = None
    _deploy_tracker = None
    _gh_deploy_tracker = None


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Pachca Integration Bot",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

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
                x_hub_signature_256,
                body,
                settings.github_webhook_secret,
            )
            if not valid:
                raise HTTPException(status_code=403, detail="Invalid signature")

        payload = GitHubWebhookPayload.model_validate_json(body)
        result = handle_github_event(
            x_github_event,
            payload,
            pr_tracker=_pr_tracker,
            gh_deploy_tracker=_gh_deploy_tracker,
        )

        if result is None:
            return WebhookResponse(ok=True, detail="Event ignored")

        if isinstance(result, dict):
            return WebhookResponse(
                ok=True,
                message_id=result.get("id"),
                detail="Tracked event handled",
            )

        if isinstance(result, StructuredMessage):
            client = _get_client()
            content = result.render()
            api_result = client.send_message(content, display_name=DISPLAY_NAME_GITHUB)
            return WebhookResponse(
                ok=True, message_id=api_result.get("id"), detail="Message sent"
            )

        return WebhookResponse(ok=True, detail="Event handled")

    @app.post("/webhooks/generic", response_model=WebhookResponse)
    async def generic_webhook(
        request: Request,
        x_authorization: str = Header(""),
    ) -> WebhookResponse:
        settings = get_settings()

        if settings.generic_webhook_secret:
            if not verify_bearer_token(
                x_authorization, settings.generic_webhook_secret
            ):
                raise HTTPException(status_code=403, detail="Unauthorized")

        body = await request.body()
        payload = GenericWebhookPayload.model_validate_json(body)
        result = handle_generic_event(payload, deploy_tracker=_deploy_tracker)

        if isinstance(result, dict):
            return WebhookResponse(
                ok=True,
                message_id=result.get("id"),
                detail="Deploy tracked",
            )

        client = _get_client()
        content = result.render()
        api_result = client.send_message(content, display_name=DISPLAY_NAME_GENERIC)
        return WebhookResponse(
            ok=True, message_id=api_result.get("id"), detail="Message sent"
        )

    return app
