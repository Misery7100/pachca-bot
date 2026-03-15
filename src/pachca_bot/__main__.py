"""Entry point: ``python -m pachca_bot``."""

import uvicorn

from pachca_bot.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "pachca_bot.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
