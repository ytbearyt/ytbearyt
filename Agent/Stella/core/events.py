"""UI-agnostic events emitted by a chat session."""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ChatEvent:
    kind: Literal["token", "tool_start", "tool_result", "error", "done", "response"]
    content: str = ""
    tool_name: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()