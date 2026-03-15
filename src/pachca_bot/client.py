"""Thin wrapper around the pachca client with threading support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pachca import Pachca

if TYPE_CHECKING:
    from pachca_bot.config import Settings

logger = logging.getLogger(__name__)


class PachcaClient:
    """Manages a ``Pachca`` session and exposes message, thread, and update APIs."""

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
        """Post a markdown message to the configured Pachca chat."""
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

    def update_message(self, message_id: int, content: str) -> dict:
        """Update an existing message's content."""
        client = self._ensure_client()
        result = client.update_message(message_id=message_id, content=content)
        logger.info("Message %s updated", message_id)
        return result

    def create_thread(self, message_id: int) -> dict:
        """Create (or get existing) thread for a message."""
        client = self._ensure_client()
        result = client.create_thread(message_id=message_id)
        logger.info(
            "Thread created/retrieved for message %s (thread_id=%s)",
            message_id,
            result.get("id"),
        )
        return result

    def post_to_thread(
        self,
        thread_id: int,
        content: str,
        display_name: str = "",
    ) -> dict:
        """Post a message to an existing thread."""
        client = self._ensure_client()
        kwargs: dict = {
            "entity_id": thread_id,
            "content": content,
            "entity_type": "thread",
        }
        if display_name:
            kwargs["display_name"] = display_name
        if self._settings.bot_display_avatar_url:
            kwargs["display_avatar_url"] = self._settings.bot_display_avatar_url

        result = client.create_message(**kwargs)
        logger.info("Thread reply sent (thread=%s, id=%s)", thread_id, result.get("id"))
        return result

    def get_messages(self, chat_id: int | None = None) -> list[dict]:
        """Retrieve recent messages from a chat."""
        client = self._ensure_client()
        target_chat = chat_id or self._settings.pachca_chat_id
        return client.get_messages(chat_id=target_chat)

    def close(self) -> None:
        if self._client is not None:
            self._client.__exit__(None, None, None)
            self._client = None
