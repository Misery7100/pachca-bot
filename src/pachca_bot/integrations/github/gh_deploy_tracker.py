"""Thread-based GitHub deployment tracking.

Maintains an in-memory mapping of (repo, environment, sha) → pachca_message_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pachca_bot.core.client import PachcaClient
from pachca_bot.core.config import IntegrationConfig
from pachca_bot.integrations.github.models import GHDeployState, GitHubDeploymentMessage

logger = logging.getLogger(__name__)


@dataclass
class _GHDeployEntry:
    message_id: int
    state: GHDeployState
    content: str = ""


class GHDeployTracker:
    """In-memory GitHub deployment tracker with chat-search fallback."""

    def __init__(self, client: PachcaClient, integration: IntegrationConfig) -> None:
        self._client = client
        self._integration = integration
        self._store: dict[tuple[str, str, str], _GHDeployEntry] = {}

    def _make_key(self, repo: str, environment: str, sha: str) -> tuple[str, str, str]:
        return (repo, environment, sha or "")

    def _search_chat(self, repo: str, environment: str, sha: str) -> _GHDeployEntry | None:
        try:
            messages = self._client.get_messages(self._integration.chat_id)
        except Exception:
            logger.warning("Failed to fetch messages for GH deploy lookup", exc_info=True)
            return None

        env_target = f"Deployment: {environment}"
        short_sha = (sha or "")[:8]

        for msg in messages:
            content = msg.get("content", "")
            if env_target not in content:
                continue
            if repo not in content:
                continue
            if short_sha and short_sha not in content:
                continue
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
        key = self._make_key(deploy_msg.repo, deploy_msg.environment, deploy_msg.sha)
        entry = self._store.get(key)

        if entry is None:
            found = self._search_chat(
                deploy_msg.repo, deploy_msg.environment, deploy_msg.sha
            )
            if found is not None:
                entry = found
                self._store[key] = entry

        new_state = deploy_msg._resolve_state()

        if entry is None:
            content = deploy_msg.to_parent()
            result = self._client.send_message(
                content,
                display_name=self._integration.display_name,
                display_avatar_url=self._integration.display_avatar_url,
                chat_id=self._integration.chat_id,
            )
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
                    thread_id,
                    thread_content,
                    display_name=self._integration.display_name,
                    display_avatar_url=self._integration.display_avatar_url,
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
            result = self._client.send_message(
                new_content,
                display_name=self._integration.display_name,
                display_avatar_url=self._integration.display_avatar_url,
                chat_id=self._integration.chat_id,
            )
            msg_id = result.get("id")
            if msg_id:
                self._store[key] = _GHDeployEntry(
                    message_id=msg_id, state=new_state, content=new_content
                )
            return result

        return {"id": entry.message_id}
