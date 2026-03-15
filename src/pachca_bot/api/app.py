"""FastAPI application — routes delegate to integration handlers."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from pachca_bot.core import PachcaClient, get_settings
from pachca_bot.integrations.generic import DeployTracker, GenericHandler
from pachca_bot.integrations.github import GHDeployTracker, GitHubHandler, PRTracker

logger = logging.getLogger(__name__)

_github_handler: GitHubHandler | None = None
_generic_handler: GenericHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _github_handler, _generic_handler
    settings = get_settings()
    client = PachcaClient(settings)
    gh_config = settings.get_github_config()
    gen_config = settings.get_generic_config()

    pr_tracker = PRTracker(client, gh_config) if gh_config else None
    gh_deploy_tracker = GHDeployTracker(client, gh_config) if gh_config else None
    deploy_tracker = DeployTracker(client, gen_config) if gen_config else None

    _github_handler = (
        GitHubHandler(
            client=client,
            integration=gh_config,
            pr_tracker=pr_tracker,
            gh_deploy_tracker=gh_deploy_tracker,
            webhook_secret=settings.github.webhook_secret,
        )
        if gh_config
        else None
    )
    _generic_handler = (
        GenericHandler(
            client=client,
            integration=gen_config,
            deploy_tracker=deploy_tracker,
            webhook_secret=settings.generic.webhook_secret,
        )
        if gen_config
        else None
    )

    logger.info(
        "Pachca bot started — github_chat_id=%s, generic_chat_id=%s",
        gh_config.chat_id if gh_config else "—",
        gen_config.chat_id if gen_config else "—",
    )
    yield
    client.close()
    _github_handler = None
    _generic_handler = None


def create_app() -> FastAPI:
    from pachca_bot.api.responses import WebhookResponse

    app = FastAPI(
        title="Pachca Integration Bot",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/webhooks/github", response_model=WebhookResponse)
    async def github_webhook(request: Request):
        if _github_handler is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "GitHub integration not configured "
                    "(GITHUB__CHAT_ID or PACHCA_CHAT_ID required)"
                ),
            )
        return await _github_handler.handle(request)

    @app.post("/webhooks/generic", response_model=WebhookResponse)
    async def generic_webhook(request: Request):
        if _generic_handler is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Generic integration not configured "
                    "(GENERIC__CHAT_ID or PACHCA_CHAT_ID required)"
                ),
            )
        return await _generic_handler.handle(request)

    return app
