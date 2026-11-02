"""Conversation orchestration and streaming model integration."""

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import Settings
from .events import ChatEvent
from .mcp_client import MCPClientManager
from .skills import SkillMetadata, discover_skills
from .tools import TOOLS, execute_tool


SYSTEM_PROMPT = (
    "你是 Stella。用户询问实时信息、官网、最新网页或需要联网核实的信息时，"
    "必须调用 searchWeb 搜索，再需要打开具体网页时调用 fetchWeb。"
    "不要声称自己没有联网能力，也不要用本地文件工具代替网页搜索。"
    "工具返回错误时，要向用户清楚说明错误类型，不能编造搜索结果。"
)


def build_system_prompt(skills: Mapping[str, SkillMetadata], mcp_status: str = "") -> str:
    skill_lines = [
        f"- {skill.name}: {skill.description}"
        for skill in skills.values()
    ]
    available_skills = "\n".join(skill_lines) or "- No skills are currently available."
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "You have access to the following skills:\n"
        f"{available_skills}\n"
        "Use the `loadSkill` tool to load the full instructions of a skill when needed. "
        "You can also load additional files referenced by a skill."
    )
    return f"{prompt}\n\n{mcp_status}" if mcp_status else prompt


class ChatSession:
    """A conversation session with no dependency on a particular UI."""

    def __init__(self, settings: Settings, client: Any | None = None):
        self._settings = settings
        self._client = client or OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._history: list[dict[str, Any]] = []
        self._skills: dict[str, SkillMetadata] = dict(discover_skills())
        self._mcp = MCPClientManager.from_project(Path.cwd())
        self._tools = [*TOOLS, *self._mcp.openai_tools]
        self._system_prompt = build_system_prompt(self._skills, self._mcp.status)

    @property
    def skills(self) -> dict[str, SkillMetadata]:
        return self._skills.copy()

    @property
    def mcp_status(self) -> str:
        return self._mcp.status

    def send(self, prompt: str) -> Iterator[ChatEvent]:
        if not self._history:
            self._history.append({"role": "system", "content": self._system_prompt})
        self._history.append({"role": "user", "content": prompt})
        try:
            while True:
                reply_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for event in self._stream_chat():
                    if event.kind == "token":
                        reply_parts.append(event.content)
                        yield event
                    elif event.kind == "response":
                        tool_calls = list(event.tool_calls)
                reply = "".join(reply_parts)
                message: dict[str, Any] = {"role": "assistant", "content": reply}
                if tool_calls:
                    message["tool_calls"] = tool_calls
                self._history.append(message)

                if not tool_calls:
                    yield ChatEvent("done")
                    return

                for call in tool_calls:
                    name = call["function"]["name"]
                    try:
                        arguments = json.loads(call["function"]["arguments"] or "{}")
                        if not isinstance(arguments, dict):
                            arguments = {}
                    except json.JSONDecodeError:
                        arguments = {}
                    yield ChatEvent("tool_start", content=str(arguments), tool_name=name)
                    result = execute_tool(name, arguments, self._skills, self._mcp)
                    if name == "createSkill" and result.startswith("已创建 Skill："):
                        self._system_prompt = build_system_prompt(self._skills)
                        if self._history and self._history[0].get("role") == "system":
                            self._history[0]["content"] = self._system_prompt
                    yield ChatEvent("tool_result", content=result, tool_name=name)
                    self._history.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": name,
                            "content": result,
                        }
                    )
        except Exception as exc:
            yield ChatEvent("error", content=f"{type(exc).__name__}: {exc}")
            yield ChatEvent("done")

    def _stream_chat(self) -> Iterator[ChatEvent]:
        stream = self._client.chat.completions.create(
            model=self._settings.model,
            messages=self._history,
            tools=self._tools,
            stream=True,
        )
        reply_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                reply_parts.append(delta.content)
                yield ChatEvent("token", content=delta.content)
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    call = calls.setdefault(
                        tool_call.index,
                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tool_call.id:
                        call["id"] = tool_call.id
                    if tool_call.function:
                        if tool_call.function.name:
                            call["function"]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            call["function"]["arguments"] += tool_call.function.arguments
        ordered = [calls[index] for index in sorted(calls)]
        yield ChatEvent("response", content="".join(reply_parts), tool_calls=tuple(ordered))