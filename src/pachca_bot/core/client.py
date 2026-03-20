"""Thin wrapper around the pachca client with threading support."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from pachca import Pachca

if TYPE_CHECKING:
    from pachca_bot.core.config import Settings

MESSAGES_LIMIT = 50
MESSAGES_MAX_SCAN = 500
API_RETRIES = 2
API_RETRY_BASE_DELAY = 1.0

logger = logging.getLogger(__name__)


def _retry_with_backoff(
    fn,
    *,
    retries: int = API_RETRIES,
    base_delay: float = API_RETRY_BASE_DELAY,
):
    """Execute fn(), retrying on exception with exponential backoff. Re-raises last error."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt < retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "API call failed (attempt %s/%s), retrying in %.1fs: %s",
                    attempt + 1,
                    retries + 1,
                    delay,
                    e,
                )
                time.sleep(delay)
    raise last_error  # type: ignore[misc]


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

        def _send():
            client = self._ensure_client()
            result = client.create_message(**kwargs)
            logger.info("Message sent to chat %s (id=%s)", target_chat, result.get("id"))
            return result

        return _retry_with_backoff(_send)

    def update_message(self, message_id: int, content: str) -> dict:
        """Update an existing message's content."""

        def _update():
            client = self._ensure_client()
            result = client.update_message(message_id=message_id, content=content)
            logger.info("Message %s updated", message_id)
            return result

        return _retry_with_backoff(_update)

    def create_thread(self, message_id: int) -> dict:
        """Create (or get existing) thread for a message."""

        def _create():
            client = self._ensure_client()
            result = client.create_thread(message_id=message_id)
            logger.info(
                "Thread created/retrieved for message %s (thread_id=%s)",
                message_id,
                result.get("id"),
            )
            return result

        return _retry_with_backoff(_create)

    def get_thread_chat_id(self, thread_id: int) -> int | None:
        """Return the thread's chat id for listing thread messages (GET /messages?chat_id=...)."""

        def _fetch():
            client = self._ensure_client()
            path = f"{Pachca.THREADS}/{thread_id}"
            response = client.call_api(path, "get", {})
            data = response.get("data")
            if isinstance(data, dict):
                raw = data.get("chat_id")
                if raw is not None:
                    return int(raw)
            return None

        try:
            return _retry_with_backoff(_fetch)
        except Exception:
            logger.warning("Failed to fetch thread %s", thread_id, exc_info=True)
            return None

    def post_to_thread(
        self,
        thread_id: int,
        content: str,
        display_name: str = "",
        display_avatar_url: str | None = None,
    ) -> dict:
        """Post a message to an existing thread."""
        kwargs: dict = {
            "entity_id": thread_id,
            "content": content,
            "entity_type": "thread",
        }
        if display_name:
            kwargs["display_name"] = display_name
        if display_avatar_url:
            kwargs["display_avatar_url"] = display_avatar_url

        def _post():
            client = self._ensure_client()
            result = client.create_message(**kwargs)
            logger.info("Thread reply sent (thread=%s, id=%s)", thread_id, result.get("id"))
            return result

        return _retry_with_backoff(_post)

    def get_message(self, message_id: int) -> dict | None:
        """Fetch a single message by ID. Returns None on failure or if content missing."""

        def _fetch():
            client = self._ensure_client()
            path = f"{Pachca.MESSAGES}/{message_id}"
            response = client.call_api(path, "get", {})
            data = response.get("data", {})
            if isinstance(data, dict):
                return data
            return None

        try:
            return _retry_with_backoff(_fetch)
        except Exception:
            logger.warning("Failed to fetch message %s", message_id, exc_info=True)
            return None

    def get_messages(
        self,
        chat_id: int,
        max_messages: int | None = None,
        *,
        retries: int = API_RETRIES,
    ) -> list[dict]:
        """Retrieve up to max_messages from a chat using cursor-based pagination.

        Uses limit=50 per request and sequential requests for serverless deployments
        where in-memory state cannot be kept. Stops when max_messages reached or
        no more pages (meta.paginate.next_page). Retries on transient failure
        (e.g. rate limit) with exponential backoff.
        """
        _max = max_messages
        if _max is None:
            _max = getattr(
                self._settings, "messages_max_scan", MESSAGES_MAX_SCAN
            )

        def _fetch():
            return self._get_messages_impl(chat_id, _max)

        return _retry_with_backoff(_fetch, retries=retries)

    def _get_messages_impl(
        self, chat_id: int, max_messages: int
    ) -> list[dict]:
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
