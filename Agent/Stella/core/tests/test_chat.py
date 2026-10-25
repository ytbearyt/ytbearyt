from types import SimpleNamespace

from Agent.Stella.core.chat import ChatSession
from Agent.Stella.core.config import Settings


def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class FakeClient:
    def __init__(self):
        tool_call = SimpleNamespace(
            index=0,
            id="call-1",
            function=SimpleNamespace(name="getCurrentDir", arguments="{}"),
        )
        self.responses = [
            [_chunk(tool_calls=[tool_call])],
            [_chunk(content="完成"), _chunk(content="了")],
        ]
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_kwargs):
        return iter(self.responses.pop(0))


def test_chat_session_streams_tokens_and_completes_tool_cycle():
    session = ChatSession(
        Settings(base_url="https://example.invalid", api_key="test", model="test-model"),
        client=FakeClient(),
    )

    events = list(session.send("当前目录是什么？"))

    assert [event.kind for event in events] == [
        "tool_start",
        "tool_result",
        "token",
        "token",
        "done",
    ]
    assert "当前工作目录" in events[1].content
    assert "".join(event.content for event in events if event.kind == "token") == "完成了"