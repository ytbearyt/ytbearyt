"""Textual presentation layer for the chat session."""

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from ..core.chat import ChatSession
from ..core.events import ChatEvent


class StellaTUI(App[None]):
    """Terminal UI adapter; all conversation behavior stays in core."""

    TITLE = "Stella"
    SUB_TITLE = "Local AI assistant"
    CSS = """
    Screen {
        background: #101719;
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
    """

    def __init__(self, session: ChatSession):
        super().__init__()
        self._session = session
        self._transcript = "Stella 已就绪。输入消息开始对话。\n"
        self._assistant_reply = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="conversation"):
            yield Static(self._transcript, id="transcript", markup=False)
        yield Input(placeholder="输入消息，按 Enter 发送…", id="prompt")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        event.input.value = ""
        event.input.disabled = True
        self._assistant_reply = ""
        self._append(f"\n你：{prompt}\nStella：")
        self.process_prompt(prompt)

    @work(thread=True, exclusive=True)
    def process_prompt(self, prompt: str) -> None:
        for event in self._session.send(prompt):
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
        elif event.kind == "done":
            self._append("\n")
            self.query_one("#prompt", Input).disabled = False
            self.query_one("#prompt", Input).focus()

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