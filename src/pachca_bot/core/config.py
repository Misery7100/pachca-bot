"""Application settings with per-integration configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


def _backward_compat_env() -> None:
    """Map flat env vars to nested for backward compatibility."""
    mapping = [
        ("GITHUB_WEBHOOK_SECRET", "GITHUB__WEBHOOK_SECRET"),
        ("GITHUB_PACHCA_CHAT_ID", "GITHUB__PACHCA_CHAT_ID"),
        ("GITHUB_BOT_DISPLAY_NAME", "GITHUB__BOT_DISPLAY_NAME"),
        ("GITHUB_BOT_DISPLAY_AVATAR_URL", "GITHUB__BOT_DISPLAY_AVATAR_URL"),
        ("GENERIC_WEBHOOK_SECRET", "GENERIC__WEBHOOK_SECRET"),
        ("GENERIC_PACHCA_CHAT_ID", "GENERIC__PACHCA_CHAT_ID"),
        ("GENERIC_BOT_DISPLAY_NAME", "GENERIC__BOT_DISPLAY_NAME"),
        ("GENERIC_BOT_DISPLAY_AVATAR_URL", "GENERIC__BOT_DISPLAY_AVATAR_URL"),
    ]
    for flat, nested in mapping:
        if os.environ.get(flat) and not os.environ.get(nested):
            os.environ[nested] = os.environ[flat]

DEFAULT_GITHUB_AVATAR = (
    "https://raw.githubusercontent.com/Misery7100/pachca-bot/main/images/github-bot.png"
)
DEFAULT_GENERIC_AVATAR = (
    "https://raw.githubusercontent.com/Misery7100/pachca-bot/main/images/events-bot.png"
)
DEFAULT_GITHUB_BOT_NAME = "GitHub Bot"
DEFAULT_GENERIC_BOT_NAME = "Events Bot"


class IntegrationSettings(BaseSettings):
    """Per-integration settings: chat, webhook secret, bot display."""

    chat_id: int | None = None
    webhook_secret: str = ""
    bot_display_name: str = ""
    display_avatar_url: str | None = None

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


class GitHubIntegrationSettings(IntegrationSettings):
    chat_id: int | None = Field(default=None, validation_alias="pachca_chat_id")
    bot_display_name: str = DEFAULT_GITHUB_BOT_NAME
    display_avatar_url: str | None = DEFAULT_GITHUB_AVATAR
    pr_tracker_stateless_safe: bool = Field(
        default=False,
        description=(
            "Reload PR state from Pachca on each webhook; dedupe check-pass via thread "
            "markers. Use for serverless / multi-instance (env: GITHUB__PR_TRACKER_STATELESS_SAFE)"
        ),
    )

    model_config = {"case_sensitive": False, "extra": "ignore", "populate_by_name": True}


class GenericIntegrationSettings(IntegrationSettings):
    chat_id: int | None = Field(default=None, validation_alias="pachca_chat_id")
    bot_display_name: str = DEFAULT_GENERIC_BOT_NAME
    display_avatar_url: str | None = DEFAULT_GENERIC_AVATAR

    model_config = {"case_sensitive": False, "extra": "ignore", "populate_by_name": True}


@dataclass(frozen=True)
class IntegrationConfig:
    """Resolved integration config for handlers (chat_id, display name, avatar)."""

    chat_id: int
    display_name: str
    display_avatar_url: str
    pr_tracker_stateless_safe: bool = False


class Settings(BaseSettings):
    pachca_access_token: str
    pachca_chat_id: int | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    messages_max_scan: int = Field(
        default=500,
        description="Max messages to scan when searching chat (env: MESSAGES_MAX_SCAN)",
    )

    github: GitHubIntegrationSettings = Field(default_factory=GitHubIntegrationSettings)
    generic: GenericIntegrationSettings = Field(default_factory=GenericIntegrationSettings)

    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "env_nested_delimiter": "__",
    }

    @model_validator(mode="after")
    def _require_chat_id(self) -> "Settings":
        if not any(
            (
                self.pachca_chat_id,
                self.github.chat_id,
                self.generic.chat_id,
            )
        ):
            raise ValueError(
                "At least one of PACHCA_CHAT_ID, GITHUB__CHAT_ID, "
                "or GENERIC__CHAT_ID must be set"
            )
        return self

    def get_github_config(self) -> IntegrationConfig | None:
        chat_id = self.github.chat_id or self.pachca_chat_id
        if chat_id is None:
            return None
        return IntegrationConfig(
            chat_id=chat_id,
            display_name=self.github.bot_display_name or DEFAULT_GITHUB_BOT_NAME,
            display_avatar_url=self.github.display_avatar_url or DEFAULT_GITHUB_AVATAR,
            pr_tracker_stateless_safe=self.github.pr_tracker_stateless_safe,
        )

    def get_generic_config(self) -> IntegrationConfig | None:
        chat_id = self.generic.chat_id or self.pachca_chat_id
        if chat_id is None:
            return None
        return IntegrationConfig(
            chat_id=chat_id,
            display_name=self.generic.bot_display_name or DEFAULT_GENERIC_BOT_NAME,
            display_avatar_url=self.generic.display_avatar_url or DEFAULT_GENERIC_AVATAR,
        )


def get_settings() -> Settings:
    _backward_compat_env()
    return Settings()  # type: ignore[call-arg]
