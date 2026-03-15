"""Thin wrapper around the pachca client with threading support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pachca import Pachca

if TYPE_CHECKING:
    from pachca_bot.core.config import Settings

MESSAGES_LIMIT = 50
MESSAGES_MAX_SCAN = 300

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
        display_avatar_url: str | None = None,
        chat_id: int | None = None,
    ) -> dict:
        """Post a markdown message to the configured Pachca chat."""
        client = self._ensure_client()
        target_chat = chat_id

        kwargs: dict = {
            "entity_id": target_chat,
            "content": content,
            "entity_type": "discussion",
        }
        if display_name:
            kwargs["display_name"] = display_name
        if display_avatar_url:
            kwargs["display_avatar_url"] = display_avatar_url

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
        display_avatar_url: str | None = None,
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
        if display_avatar_url:
            kwargs["display_avatar_url"] = display_avatar_url

        result = client.create_message(**kwargs)
        logger.info("Thread reply sent (thread=%s, id=%s)", thread_id, result.get("id"))
        return result

    def get_messages(self, chat_id: int, max_messages: int = MESSAGES_MAX_SCAN) -> list[dict]:
        """Retrieve up to max_messages from a chat using cursor-based pagination.

        Uses limit=50 per request and sequential requests for serverless deployments
        where in-memory state cannot be kept. Stops when max_messages reached or
        no more pages (meta.paginate.next_page).
        """
        client = self._ensure_client()
        messages: list[dict] = []
        cursor: str | None = None

        while len(messages) < max_messages:
            payload: dict = {
                "chat_id": chat_id,
                "limit": MESSAGES_LIMIT,
                "sort[id]": "desc",
            }
            if cursor:
                payload["cursor"] = cursor

            response = client.call_api(Pachca.MESSAGES, "get", payload)
            data = response.get("data", [])
            messages.extend(data)

            meta = response.get("meta", {})
            paginate = meta.get("paginate", {})
            next_page = paginate.get("next_page")

            if not next_page or len(data) < MESSAGES_LIMIT:
                break
            cursor = next_page

        return messages[:max_messages]

    def close(self) -> None:
        if self._client is not None:
            self._client.__exit__(None, None, None)
            self._client = None
