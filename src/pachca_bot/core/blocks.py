"""Shared block primitives for composing Pachca markdown messages."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

HEADER_EMOJI_RE = re.compile(r"^(## )\S+( )", re.MULTILINE)
STATUS_FIELD_RE = re.compile(r"^\*\*Status:\*\* .+$", re.MULTILINE)


class MessageBlock(BaseModel):
    def render(self) -> str:
        raise NotImplementedError


class HeaderBlock(MessageBlock):
    text: str
    level: Literal[1, 2, 3] = 1

    def render(self) -> str:
        prefix = "#" * self.level
        return f"{prefix} {self.text}"


class TextBlock(MessageBlock):
    text: str
    bold: bool = False
    italic: bool = False

    def render(self) -> str:
        t = self.text
        if self.bold:
            t = f"**{t}**"
        if self.italic:
            t = f"*{t}*"
        return t


class LinkBlock(MessageBlock):
    text: str
    url: str

    def render(self) -> str:
        return f"[{self.text}]({self.url})"


class FieldsBlock(MessageBlock):
    fields: dict[str, str]

    def render(self) -> str:
        lines = [f"**{k}:** {v}" for k, v in self.fields.items()]
        return "\n".join(lines)


class CodeBlock(MessageBlock):
    code: str
    language: str = ""

    def render(self) -> str:
        return f"```{self.language}\n{self.code}\n```"


class QuoteBlock(MessageBlock):
    text: str

    def render(self) -> str:
        lines = self.text.split("\n")
        return "\n".join(f"> {line}" for line in lines)


class ListBlock(MessageBlock):
    items: list[str]
    ordered: bool = False

    def render(self) -> str:
        result: list[str] = []
        for i, item in enumerate(self.items, 1):
            prefix = f"{i}." if self.ordered else "•"
            result.append(f"{prefix} {item}")
        return "\n".join(result)


class DividerBlock(MessageBlock):
    def render(self) -> str:
        return "---"


class StructuredMessage(BaseModel):
    blocks: list[MessageBlock] = Field(default_factory=list)

    def render(self) -> str:
        return "\n\n".join(block.render() for block in self.blocks)

    def add(self, block: MessageBlock) -> StructuredMessage:
        self.blocks.append(block)
        return self


def render_status_update(
    before_emoji: str,
    before_label: str,
    after_emoji: str,
    after_label: str,
) -> str:
    return (
        f"Status updated:\n\n"
        f"**Before:** {before_emoji} {before_label}\n"
        f"**After:** {after_emoji} {after_label}"
    )


def patch_status_in_content(content: str, new_emoji: str, new_label: str) -> str:
    """Replace the leading emoji in the header and the Status field value."""
    result = HEADER_EMOJI_RE.sub(rf"\g<1>{new_emoji}\2", content, count=1)
    result = STATUS_FIELD_RE.sub(f"**Status:** {new_label}", result)
    return result
