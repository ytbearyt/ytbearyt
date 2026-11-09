"""Textual presentation layer for the chat session."""

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from ..core.chat import ChatSession
from ..core.events import ChatEvent


SLASH_COMMANDS = {
    "/new": "保存当前会话并新建会话",
    "/resume": "打开历史会话列表并恢复选中会话",
    "/save": "保存当前会话",
    "/compact": "压缩当前上下文",
    "/clear": "清空当前界面显示，不删除会话历史",
    "/status": "显示当前会话和上下文状态",
    "/mcp": "显示已连接 MCP Server 和 tools",
    "/help": "显示全部斜杠命令",
    "/quit": "退出 Stella",
}


def _context_line(session: ChatSession) -> str:
    used, limit, percentage, defaulted = session.context_status
    suffix = "（默认）" if defaulted else ""
    return f"上下文：{used:,} / {limit:,} tokens（{percentage}%）{suffix}"


def _history_to_transcript(history: list[dict]) -> str:
    lines = ["Stella 已恢复历史会话。"]
    for message in history:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role == "user":
            lines.append(f"\n你：{content}")
        elif role == "assistant" and content:
            lines.append(f"\nStella：{content}")
        elif role == "tool":
            lines.append(f"\n[工具结果] {content}")
    return "\n".join(lines) + "\n"


class CompressionReviewScreen(Screen[None]):
    """Modal view showing the complete context before and after compression."""

    CSS = """
    Screen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    #compact-dialog {
        width: 94%;
        height: 88%;
        padding: 1;
        border: round #b5d6a1;
        background: #182426;
    }
    #compact-title {
        height: 2;
        color: #e5eee9;
        text-style: bold;
    }
    #compact-columns {
        height: 1fr;
        layout: horizontal;
    }
    .compact-column {
        width: 1fr;
        height: 1fr;
        border: round #3e6660;
        margin: 0 1 1 0;
    }
    .compact-column:last-child {
        margin-right: 0;
    }
    .compact-heading {
        height: 2;
        padding: 0 1;
        color: #b5d6a1;
        text-style: bold;
    }
    .compact-content {
        height: 1fr;
        padding: 0 1;
        color: #e5eee9;
    }
    #close-compact {
        width: 12;
        min-width: 12;
        margin: 0 0 0 1;
        dock: right;
    }
    """

    def __init__(self, before: str, after: str):
        super().__init__()
        self._before = before
        self._after = after

    def compose(self) -> ComposeResult:
        with Vertical(id="compact-dialog"):
            yield Static("上下文压缩结果", id="compact-title")
            with Horizontal(id="compact-columns"):
                with Vertical(classes="compact-column"):
                    yield Static("压缩前原文", classes="compact-heading")
                    with VerticalScroll(classes="compact-content"):
                        yield Static(self._before, markup=False)
                with Vertical(classes="compact-column"):
                    yield Static("压缩后摘要", classes="compact-heading")
                    with VerticalScroll(classes="compact-content"):
                        yield Static(self._after, markup=False)
            yield Button("关闭", id="close-compact", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-compact":
            self.dismiss()


class ResumeScreen(Screen[str | None]):
    """Keyboard-selectable history session list."""

    CSS = """
    Screen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    #resume-dialog {
        width: 76%;
        height: 70%;
        padding: 1;
        border: round #b5d6a1;
        background: #182426;
    }
    #resume-title {
        height: 2;
        color: #e5eee9;
        text-style: bold;
    }
    #resume-list {
        height: 1fr;
        border: round #3e6660;
    }
    #resume-hint {
        height: 2;
        color: #b5d6a1;
    }
    """

    def __init__(self, summaries):
        super().__init__()
        self._summaries = summaries

    def compose(self) -> ComposeResult:
        with Vertical(id="resume-dialog"):
            yield Static("恢复历史会话", id="resume-title")
            with ListView(id="resume-list"):
                for summary in self._summaries:
                    yield ListItem(Label(
                        f"{summary.session_id}  |  {summary.updated_at}  |  {summary.message_count} 条消息  |  {summary.preview}"
                    ))
            yield Static("上下键选择，回车恢复，Esc 取消", id="resume-hint")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.index is not None:
            self.dismiss(self._summaries[event.list_view.index].session_id)

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


class SetupRequiredScreen(Screen[None]):
    """Blocks model use until the generated configuration is edited."""

    CSS = """
    Screen {
        align: center middle;
        background: rgba(0, 0, 0, 0.78);
    }
    #setup-dialog {
        width: 72%;
        height: auto;
        padding: 2;
        border: round #d7a85d;
        background: #182426;
    }
    #setup-title {
        color: #f0c77b;
        text-style: bold;
    }
    #setup-message {
        height: auto;
        margin: 1 0;
        color: #e5eee9;
    }
    """

    def __init__(self, config_path):
        super().__init__()
        self._config_path = config_path

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-dialog"):
            yield Static("Stella 需要配置", id="setup-title")
            yield Static(
                f"当前目录没有 config.ini，Stella 已创建 mock 配置：\n{self._config_path}\n\n"
                "请编辑该文件，填写真实的模型地址、API Key 和模型名称，然后重新启动 Stella。",
                id="setup-message",
                markup=False,
            )
            yield Button("退出 Stella", id="setup-exit", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-exit":
            self.app.exit()


class StellaTUI(App[None]):
    """Terminal UI adapter; all conversation behavior stays in core."""

    TITLE = "Stella"
    SUB_TITLE = "Local AI assistant"
    CSS = """
    Screen {
        background: #101719;
    }
    #body {
        height: 1fr;
    }
    #sidebar {
        width: 28;
        min-width: 24;
        padding: 1;
        border: round #3e6660;
        margin: 1 0 1 2;
        color: #e5eee9;
    }
    #sidebar-title {
        height: 2;
        color: #b5d6a1;
        text-style: bold;
    }
    #mcp-list {
        height: 1fr;
        overflow-y: auto;
    }
    #main {
        width: 1fr;
    }
    #conversation {
        height: 1fr;
        padding: 1 2;
        border: round #3e6660;
        margin: 1 2;
        color: #e5eee9;
    }
    #prompt {
        margin: 0 2 1 2;
        border: tall #568c7d;
    }
    #prompt:focus {
        border: tall #b5d6a1;
    }
    #context-status {
        height: 1;
        margin: 0 2;
        color: #b5d6a1;
    }
    #slash-help {
        height: auto;
        max-height: 8;
        margin: 0 2;
        padding: 0 1;
        border: round #3e6660;
        color: #b5d6a1;
        display: none;
    }
    """

    def __init__(self, session: ChatSession):
        super().__init__()
        self._session = session
        self._transcript = "Stella 已就绪。输入消息开始对话。\n"
        if session.mcp_status:
            self._transcript += f"\n{session.mcp_status}\n"
        self._assistant_reply = ""
        self._mcp_loading = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static("MCP 服务器", id="sidebar-title")
                yield Static("正在异步加载…", id="mcp-list", markup=False)
            with Vertical(id="main"):
                with VerticalScroll(id="conversation"):
                    yield Static(self._transcript, id="transcript", markup=False)
                yield Static("", id="slash-help", markup=False)
                yield Static(self._context_text(), id="context-status")
                yield Input(placeholder="输入消息，按 Enter 发送…", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        prompt = self.query_one("#prompt", Input)
        if self._session.configuration_required:
            prompt.disabled = True
            self.push_screen(SetupRequiredScreen(self._session.config_path))
        self.load_mcp_async()

    @work(thread=True, exclusive=False)
    def load_mcp_async(self) -> None:
        try:
            servers = self._session.load_mcp()
            self.call_from_thread(self._update_mcp_sidebar, servers)
        except Exception as exc:
            self.call_from_thread(self._update_mcp_sidebar, [], f"加载失败：{type(exc).__name__}: {exc}")

    def _update_mcp_sidebar(self, servers, error: str = "") -> None:
        lines: list[str] = []
        if error:
            lines.append(error)
        elif not servers:
            lines.append("未配置 MCP Server")
        for server in servers:
            mark = "已连接" if server["connected"] else "连接失败"
            lines.append(f"[{mark}] {server['name']}")
            for tool in server["tools"]:
                lines.append(f"  • {tool}")
            if server["error"]:
                lines.append(f"  {server['error']}")
        self.query_one("#mcp-list", Static).update("\n".join(lines))
        self._mcp_loading = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        event.input.value = ""
        event.input.disabled = True
        self._assistant_reply = ""
        self._hide_slash_help()
        if prompt == "/compact" or prompt.startswith("/compact "):
            self._append("\n[上下文压缩开始]\n")
            self.process_compact()
        elif prompt.startswith("/"):
            self._run_command(prompt)
        else:
            self._append(f"\n你：{prompt}\nStella：")
            self.process_prompt(prompt)

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value.strip()
        if value.startswith("/") and " " not in value:
            matches = [(name, description) for name, description in SLASH_COMMANDS.items() if name.startswith(value)]
            if matches:
                self.query_one("#slash-help", Static).update("\n".join(f"{name}  {description}" for name, description in matches))
                self.query_one("#slash-help", Static).display = True
                return
        self._hide_slash_help()

    def _hide_slash_help(self) -> None:
        self.query_one("#slash-help", Static).display = False

    def _run_command(self, command_line: str) -> None:
        command = command_line.split(maxsplit=1)[0].lower()
        if command == "/new":
            session_id = self._session.new_session()
            self._transcript = f"Stella 已新建会话：{session_id}\n"
            self._refresh_transcript()
            self._finish_command()
        elif command == "/save":
            path = self._session.save()
            self._append(f"\n[会话] 已保存：{path}\n")
            self._finish_command()
        elif command == "/resume":
            summaries = self._session.list_sessions()
            if not summaries:
                self._append("\n[会话] 没有可恢复的历史会话。\n")
                self._finish_command()
            else:
                self.push_screen(ResumeScreen(summaries), self._resume_selected)
        elif command == "/clear":
            self._transcript = "Stella 已清空当前界面显示，历史会话仍然保留。\n"
            self._refresh_transcript()
            self._finish_command()
        elif command == "/status":
            self._append(f"\n[状态] 会话 {self._session.session_id}\n")
            self._append(f"[状态] {_context_line(self._session)}\n")
            self._finish_command()
        elif command == "/mcp":
            self._append("\n[状态] MCP 信息已显示在左侧栏。\n")
            self._finish_command()
        elif command == "/help":
            self._append("\n" + "\n".join(f"{name}：{description}" for name, description in SLASH_COMMANDS.items()) + "\n")
            self._finish_command()
        elif command == "/compact":
            self._append("\n[上下文压缩开始]\n")
            self.process_compact()
        elif command == "/quit":
            self.exit()
        else:
            self._append(f"\n[命令] 未知命令：{command}，请输入 /help 查看可用命令。\n")
            self._finish_command()

    def _resume_selected(self, session_id: str | None) -> None:
        if not session_id:
            self._finish_command()
            return
        try:
            self._session.resume_session(session_id)
            self._transcript = _history_to_transcript(self._session.history)
            self._refresh_transcript()
        except Exception as exc:
            self._append(f"\n[会话] 恢复失败：{type(exc).__name__}: {exc}\n")
        self._finish_command()

    def _finish_command(self) -> None:
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = False
        prompt.focus()
        self._refresh_context_status()

    @work(thread=True, exclusive=True)
    def process_prompt(self, prompt: str) -> None:
        for event in self._session.send(prompt):
            self.call_from_thread(self._handle_event, event)

    @work(thread=True, exclusive=True)
    def process_compact(self) -> None:
        for event in self._session.compact():
            self.call_from_thread(self._handle_event, event)

    def _handle_event(self, event: ChatEvent) -> None:
        if event.kind == "token":
            self._assistant_reply += event.content
            self._replace_transcript_tail(self._assistant_reply)
        elif event.kind == "tool_start":
            self._append(f"\n[工具] {event.tool_name}({event.content})\n")
        elif event.kind == "tool_result":
            self._append(f"[结果] {event.content}\nStella：{self._assistant_reply}")
        elif event.kind == "error":
            self._append(f"\n[错误] {event.content}\n")
        elif event.kind == "context_warning":
            self._append(f"\n[上下文] {event.content}\n")
        elif event.kind == "compact":
            self._append(f"[压缩] {event.content}\n")
            if event.details.get("before") and event.details.get("after"):
                self.push_screen(CompressionReviewScreen(event.details["before"], event.details["after"]))
        elif event.kind == "done":
            self._append("\n")
            self.query_one("#prompt", Input).disabled = False
            self.query_one("#prompt", Input).focus()
            self._refresh_context_status()

    def _append(self, text: str) -> None:
        self._transcript += text
        self._refresh_transcript()

    def _replace_transcript_tail(self, text: str) -> None:
        marker = "Stella："
        position = self._transcript.rfind(marker)
        if position >= 0:
            self._transcript = self._transcript[: position + len(marker)] + text
            self._refresh_transcript()

    def _refresh_transcript(self) -> None:
        self.query_one("#transcript", Static).update(self._transcript)
        self.query_one("#conversation", VerticalScroll).scroll_end(animate=False)

    def _context_text(self) -> str:
        return _context_line(self._session)

    def _refresh_context_status(self) -> None:
        self.query_one("#context-status", Static).update(self._context_text())