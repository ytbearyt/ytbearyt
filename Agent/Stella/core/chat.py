"""Conversation orchestration and streaming model integration."""

import json
import datetime as dt
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import Settings
from .events import ChatEvent
from .mcp_client import MCPClientManager
from .skills import SkillMetadata, discover_skills
from .sessions import SessionStore, SessionSummary
from .tools import TOOLS, configure_tools, execute_tool


SYSTEM_PROMPT = (
    "你是 Stella。用户询问实时信息、官网、最新网页或需要联网核实的信息时，"
    "必须调用 searchWeb 搜索，再需要打开具体网页时调用 fetchWeb。"
    "不要声称自己没有联网能力，也不要用本地文件工具代替网页搜索。"
    "工具返回错误时，要向用户清楚说明错误类型，不能编造搜索结果。"
)

COMPACTION_PROMPT = """你是一名 AI Agent 的上下文管理助手。当前会话即将达到上下文窗口限制，需要将历史对话压缩为一份高质量的工作摘要，以便 Agent 在新的上下文中继续执行任务。

请认真阅读提供的历史上下文，提取对后续工作仍然有价值的信息，并生成一份约 5,000 Tokens 的 Markdown 摘要。

摘要应重点保留：用户目标与要求、已经完成的工作、当前工作状态、关键技术信息、关键决策与原因、下一步任务。优先保留直接影响后续任务的信息，删除寒暄、重复讨论、过时尝试和无关内容；区分已验证事实与推测；准确保留文件路径、函数名称、配置项、命令和错误信息；不要把计划描述成已完成；历史细节如无法完整保留，说明可通过 recallContext 检索。使用清晰的 Markdown 结构输出摘要，不要附加解释。"""

DEFAULT_CONTEXT_WINDOW = 128000
CONTEXT_WARNING_RATIO = 0.7


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
        configure_tools(settings)
        self._client = client or OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._history: list[dict[str, Any]] = []
        self._skills: dict[str, SkillMetadata] = dict(discover_skills())
        self._mcp = MCPClientManager.from_project(Path.cwd())
        self._tools = list(TOOLS)
        self._system_prompt = build_system_prompt(self._skills, self._mcp.status)
        self._store = SessionStore(Path.cwd(), settings.session_directory)
        self._session_id = self._store.new_id()
        self._history = self._initial_history()
        self._context_window = settings.context_window or DEFAULT_CONTEXT_WINDOW
        self._context_window_defaulted = settings.context_window is None
        self._context_tokens = 0
        self._context_blocked = False
        self._compacting = False
        self._last_prompt_tokens: int | None = None
        self._refresh_context_state()
        self.save()

    @property
    def skills(self) -> dict[str, SkillMetadata]:
        return self._skills.copy()

    @property
    def mcp_status(self) -> str:
        return self._mcp.status

    @property
    def configuration_required(self) -> bool:
        return self._settings.configuration_required

    @property
    def config_path(self) -> Path | None:
        return self._settings.config_path

    @property
    def mcp_servers(self) -> list[dict[str, Any]]:
        return self._mcp.server_summaries

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def history(self) -> list[dict[str, Any]]:
        return [dict(message) for message in self._history]

    def load_mcp(self) -> list[dict[str, Any]]:
        self._mcp.discover()
        self._tools = [*TOOLS, *self._mcp.openai_tools]
        self._system_prompt = build_system_prompt(self._skills, self._mcp.status)
        if self._history and self._history[0].get("role") == "system":
            self._history[0]["content"] = self._system_prompt
        self.save()
        return self.mcp_servers

    def save(self) -> Path:
        return self._store.save(self._session_id, self._history)

    def list_sessions(self) -> list[SessionSummary]:
        return self._store.list()

    def new_session(self) -> str:
        self.save()
        self._session_id = self._store.new_id()
        self._history = self._initial_history()
        self.save()
        return self._session_id

    def resume_session(self, session_id: str) -> None:
        history = self._store.load(session_id)
        if not history:
            raise ValueError(f"会话 {session_id} 没有可恢复的消息")
        self._session_id = session_id
        self._history = history
        self._refresh_context_state()

    def _initial_history(self) -> list[dict[str, Any]]:
        history = [{"role": "system", "content": self._system_prompt}]
        agents_path = Path.cwd() / "AGENTS.md"
        if agents_path.is_file():
            content = agents_path.read_text(encoding="utf-8")
            history.append({
                "role": "system",
                "content": f"项目 AGENTS.md（一次加载，后续轮次复用）：\n\n{content}",
                "name": "AGENTS.md",
            })
        return history

    @property
    def context_status(self) -> tuple[int, int, int, bool]:
        percentage = round(self._context_tokens / self._context_window * 100)
        return self._context_tokens, self._context_window, percentage, self._context_window_defaulted

    def _estimate_tokens(self) -> int:
        history_chars = sum(len(json.dumps(message, ensure_ascii=False)) for message in self._history)
        if not self._history:
            history_chars += len(self._system_prompt)
        tool_chars = len(json.dumps(self._tools, ensure_ascii=False))
        return max(1, (history_chars + tool_chars) // 2)

    def _refresh_context_state(self) -> bool:
        estimated = self._estimate_tokens()
        self._context_tokens = max(estimated, self._last_prompt_tokens or 0)
        self._context_blocked = self._context_tokens >= self._context_window * self._settings.context_warning_ratio
        return self._context_blocked

    def send(self, prompt: str) -> Iterator[ChatEvent]:
        if self._compacting:
            yield ChatEvent("error", content="上下文压缩进行中，暂时不能处理普通提示词。")
            yield ChatEvent("done")
            return
        if self._context_blocked:
            yield ChatEvent("context_warning", content="当前上下文已达到 70%，请先执行 /compact。")
            yield ChatEvent("done")
            return
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
                    self.save()
                    if self._refresh_context_state():
                        yield ChatEvent("context_warning", content="当前上下文已达到 70%，请执行 /compact 后继续。")
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
                        self._system_prompt = build_system_prompt(self._skills, self._mcp.status)
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
                    self.save()
        except Exception as exc:
            yield ChatEvent("error", content=f"{type(exc).__name__}: {exc}")
            yield ChatEvent("done")

    def compact(self) -> Iterator[ChatEvent]:
        if self._compacting:
            yield ChatEvent("error", content="上下文压缩已经在进行中。")
            yield ChatEvent("done")
            return
        if len(self._history) <= 1:
            yield ChatEvent("error", content="当前没有可压缩的对话历史。")
            yield ChatEvent("done")
            return
        original_history = [dict(message) for message in self._history]
        self._compacting = True
        try:
            archive_id = self._archive_history(original_history)
            yield ChatEvent("compact", content=f"已保存原始上下文：{archive_id}")
            response = self._client.chat.completions.create(
                model=self._settings.model,
                messages=[
                    {"role": "system", "content": COMPACTION_PROMPT},
                    {"role": "user", "content": json.dumps(original_history, ensure_ascii=False)},
                ],
                tools=[],
                stream=False,
            )
            summary = response.choices[0].message.content if response.choices else ""
            if not summary or not summary.strip():
                raise ValueError("压缩模型没有返回摘要")
            timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary += f"\n\n> 此前上下文已于 {timestamp} 完成压缩，原始上下文保存在编号为 {archive_id} 的归档文件中。如需查找历史信息，请使用 recallContext 工具。"
            self._history = [
                {"role": "system", "content": self._system_prompt},
                {"role": "assistant", "content": summary},
            ]
            self._context_blocked = False
            self._last_prompt_tokens = None
            self._refresh_context_state()
            yield ChatEvent(
                "compact",
                content=f"上下文压缩完成：{archive_id}",
                details={
                    "before": json.dumps(original_history, ensure_ascii=False, indent=2),
                    "after": summary,
                    "archive_id": archive_id,
                },
            )
        except Exception as exc:
            self._history = original_history
            yield ChatEvent("error", content=f"上下文压缩失败，原有上下文已保留：{type(exc).__name__}: {exc}")
        finally:
            self._compacting = False
        yield ChatEvent("done")

    def _archive_history(self, history: list[dict[str, Any]]) -> str:
        context_dir = Path.cwd() / ".agents" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        base_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_id = base_id
        suffix = 1
        target = context_dir / f"{archive_id}.jsonl"
        while target.exists():
            archive_id = f"{base_id}-{suffix}"
            suffix += 1
            target = context_dir / f"{archive_id}.jsonl"
        with target.open("x", encoding="utf-8") as file:
            for message in history:
                file.write(json.dumps(message, ensure_ascii=False) + "\n")
            file.flush()
        return archive_id

    def _stream_chat(self) -> Iterator[ChatEvent]:
        request = {
            "model": self._settings.model,
            "messages": self._history,
            "tools": self._tools,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        try:
            stream = self._client.chat.completions.create(**request)
        except TypeError:
            request.pop("stream_options")
            stream = self._client.chat.completions.create(**request)
        reply_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None and getattr(usage, "prompt_tokens", None) is not None:
                self._last_prompt_tokens = usage.prompt_tokens
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