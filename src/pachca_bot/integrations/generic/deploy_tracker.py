"""Thread-based deploy tracking for generic webhooks.

Maintains an in-memory mapping of (source, deploy_id) → pachca_message_id.
When a deploy_id is provided, the tracker finds the existing parent message
and posts status updates in a thread, similar to PR tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pachca_bot.core.client import PachcaClient
from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.generic.models import DeployStatus, GenericDeployMessage

logger = logging.getLogger(__name__)


@dataclass
class _DeployEntry:
    message_id: int
    status: DeployStatus
    content: str = ""


class DeployTracker:
    """In-memory deploy → Pachca message tracker with chat-search fallback."""

    def __init__(self, client: PachcaClient, integration: IntegrationConfig) -> None:
        self._client = client
        self._integration = integration
        self._store: dict[tuple[str, str], _DeployEntry] = {}

    def _make_key(self, source: str, deploy_id: str) -> tuple[str, str]:
        return (source, deploy_id)

    def _search_chat_for_deploy(self, deploy_id: str) -> _DeployEntry | None:
        try:
            messages = self._client.get_messages(self._integration.chat_id)
        except Exception:
            logger.warning("Failed to fetch chat messages for deploy lookup", exc_info=True)
            return None

        target = f"**ID:** {deploy_id}"
        for msg in messages:
            content = msg.get("content", "")
            if target in content:
                status = self._infer_status(content)
                return _DeployEntry(
                    message_id=msg.get("id", 0),
                    status=status,
                    content=content,
                )
        return None

    @staticmethod
    def _infer_status(content: str) -> DeployStatus:
        for ds in DeployStatus:
            if f"**Status:** {ds.label}" in content:
                return ds
        return DeployStatus.STARTED

    def handle_deploy_event(
        self,
        deploy_msg: GenericDeployMessage,
        display_name: str | None = None,
        display_avatar_url: str | None = None,
    ) -> dict:
        _name = display_name or self._integration.display_name
        _avatar = display_avatar_url or self._integration.display_avatar_url

        if not deploy_msg.deploy_id:
            content = deploy_msg.to_parent()
            return self._client.send_message(
                content,
                display_name=_name,
                display_avatar_url=_avatar,
                chat_id=self._integration.chat_id,
            )

        key = self._make_key(deploy_msg.source, deploy_msg.deploy_id)
        entry = self._store.get(key)

        if entry is None:
            found = self._search_chat_for_deploy(deploy_msg.deploy_id)
            if found is not None:
                entry = found
                self._store[key] = entry

        if entry is None:
            content = deploy_msg.to_parent()
            result = self._client.send_message(
                content,
                display_name=_name,
                display_avatar_url=_avatar,
                chat_id=self._integration.chat_id,
            )
            msg_id = result.get("id")
            if msg_id:
                self._store[key] = _DeployEntry(
                    message_id=msg_id, status=deploy_msg.status, content=content
                )
            return result

        old_status = entry.status
        if old_status == deploy_msg.status:
            return {"id": entry.message_id, "unchanged": True}

        try:
            thread = self._client.create_thread(entry.message_id)
            thread_id = thread.get("id")
            if thread_id:
                thread_content = deploy_msg.to_thread_update(old_status)
                self._client.post_to_thread(
                    thread_id,
                    thread_content,
                    display_name=_name,
                    display_avatar_url=_avatar,
                )
        except Exception:
            logger.warning("Failed to post deploy thread update", exc_info=True)

        try:
            if entry.content:
                new_content = GenericDeployMessage.patch_parent_status(
                    entry.content, deploy_msg.status
                )
            else:
                new_content = deploy_msg.to_parent()
            self._client.update_message(entry.message_id, new_content)
            entry.status = deploy_msg.status
            entry.content = new_content
        except Exception:
            logger.warning("Failed to update deploy parent, creating new one", exc_info=True)
            new_content = deploy_msg.to_parent()
            result = self._client.send_message(
                new_content,
                display_name=_name,
                display_avatar_url=_avatar,
                chat_id=self._integration.chat_id,
            )
            msg_id = result.get("id")
            if msg_id:
                self._store[key] = _DeployEntry(
                    message_id=msg_id, status=deploy_msg.status, content=new_content
                )
            return result

        return {"id": entry.message_id}
