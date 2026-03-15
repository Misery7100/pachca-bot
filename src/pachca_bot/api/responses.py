"""API response models."""

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    ok: bool = True
    message_id: int | None = None
    detail: str = ""
