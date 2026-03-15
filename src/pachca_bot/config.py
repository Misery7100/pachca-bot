from pydantic_settings import BaseSettings

DISPLAY_NAME_GITHUB = "GitHub"
DISPLAY_NAME_GENERIC = "GitHub (generic)"


class Settings(BaseSettings):
    pachca_access_token: str
    pachca_chat_id: int
    pachca_bot_user_id: int | None = None

    github_webhook_secret: str = ""
    generic_webhook_secret: str = ""

    bot_display_avatar_url: str | None = None

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    model_config = {"env_prefix": "", "case_sensitive": False}


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
