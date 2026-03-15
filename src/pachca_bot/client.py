"""Thin async-friendly wrapper around the pachca client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pachca import Pachca

if TYPE_CHECKING:
    from pachca_bot.config import Settings

logger = logging.getLogger(__name__)


class PachcaClient:
    """Manages a ``Pachca`` session and exposes a simple ``send_message`` API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Pachca | None = None

    def _ensure_client(self) -> Pachca:
        if self._client is None:
            self._client = Pachca(access_token=self._settings.pachca_access_token)
            self._client.__enter__()
        return self._client

    def send_message(
        self,
        content: str,
        display_name: str = "",
        chat_id: int | None = None,
    ) -> dict:
        """Post a markdown message to the configured Pachca chat.

        Returns the API response dict for the created message.
        """
        client = self._ensure_client()
        target_chat = chat_id or self._settings.pachca_chat_id

        kwargs: dict = {
            "entity_id": target_chat,
            "content": content,
            "entity_type": "discussion",
        }
        if display_name:
            kwargs["display_name"] = display_name
        if self._settings.bot_display_avatar_url:
            kwargs["display_avatar_url"] = self._settings.bot_display_avatar_url

        result = client.create_message(**kwargs)
        logger.info("Message sent to chat %s (id=%s)", target_chat, result.get("id"))
        return result

    def close(self) -> None:
        if self._client is not None:
            self._client.__exit__(None, None, None)
            self._client = None
