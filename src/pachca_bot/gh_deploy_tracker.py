"""Thread-based GitHub deployment tracking.

Maintains an in-memory mapping of (repo, environment) → pachca_message_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pachca_bot.client import PachcaClient
from pachca_bot.config import DISPLAY_NAME_GITHUB
from pachca_bot.models.messages import GHDeployState, GitHubDeploymentMessage

logger = logging.getLogger(__name__)


@dataclass
class _GHDeployEntry:
    message_id: int
    state: GHDeployState
    content: str = ""


class GHDeployTracker:
    """In-memory GitHub deployment tracker with chat-search fallback."""

    def __init__(self, client: PachcaClient) -> None:
        self._client = client
        self._store: dict[tuple[str, str], _GHDeployEntry] = {}

    def _make_key(self, repo: str, environment: str) -> tuple[str, str]:
        return (repo, environment)

    def _search_chat(self, environment: str) -> _GHDeployEntry | None:
        try:
            messages = self._client.get_messages()
        except Exception:
            logger.warning("Failed to fetch messages for GH deploy lookup", exc_info=True)
            return None

        target = f"Deployment: {environment}"
        for msg in messages:
            content = msg.get("content", "")
            if target in content:
                state = self._infer_state(content)
                return _GHDeployEntry(
                    message_id=msg.get("id", 0),
                    state=state,
                    content=content,
                )
        return None

    @staticmethod
    def _infer_state(content: str) -> GHDeployState:
        for st in GHDeployState:
            if f"**Status:** {st.label}" in content:
                return st
        return GHDeployState.CREATED

    def handle_deploy_event(self, deploy_msg: GitHubDeploymentMessage) -> dict:
        key = self._make_key(deploy_msg.repo, deploy_msg.environment)
        entry = self._store.get(key)

        if entry is None:
            found = self._search_chat(deploy_msg.environment)
            if found is not None:
                entry = found
                self._store[key] = entry

        new_state = deploy_msg._resolve_state()

        if entry is None:
            content = deploy_msg.to_parent()
            result = self._client.send_message(content, display_name=DISPLAY_NAME_GITHUB)
            msg_id = result.get("id")
            if msg_id:
                self._store[key] = _GHDeployEntry(
                    message_id=msg_id, state=new_state, content=content
                )
            return result

        old_state = entry.state
        if old_state == new_state:
            return {"id": entry.message_id, "unchanged": True}

        try:
            thread = self._client.create_thread(entry.message_id)
            thread_id = thread.get("id")
            if thread_id:
                thread_content = deploy_msg.to_thread_update(old_state)
                self._client.post_to_thread(
                    thread_id, thread_content, display_name=DISPLAY_NAME_GITHUB
                )
        except Exception:
            logger.warning("Failed to post GH deploy thread update", exc_info=True)

        try:
            if entry.content:
                new_content = GitHubDeploymentMessage.patch_parent_status(entry.content, new_state)
            else:
                new_content = deploy_msg.to_parent()
            self._client.update_message(entry.message_id, new_content)
            entry.state = new_state
            entry.content = new_content
        except Exception:
            logger.warning("Failed to update GH deploy parent, creating new", exc_info=True)
            new_content = deploy_msg.to_parent()
            result = self._client.send_message(new_content, display_name=DISPLAY_NAME_GITHUB)
            msg_id = result.get("id")
            if msg_id:
                self._store[key] = _GHDeployEntry(
                    message_id=msg_id, state=new_state, content=new_content
                )
            return result

        return {"id": entry.message_id}
