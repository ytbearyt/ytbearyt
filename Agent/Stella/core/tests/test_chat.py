import json
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


class LoadSkillClient:
    def __init__(self):
        tool_call = SimpleNamespace(
            index=0,
            id="call-skill-1",
            function=SimpleNamespace(name="loadSkill", arguments='{"name":"weather"}'),
        )
        self.responses = [
            [_chunk(tool_calls=[tool_call])],
            [_chunk(content="已加载")],
        ]
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_kwargs):
        return iter(self.responses.pop(0))


class CreateSkillClient:
    def __init__(self):
        content = "---\nname: focus\ndescription: Improve focus\n---\nFocus instructions\n"
        tool_call = SimpleNamespace(
            index=0,
            id="call-create-skill-1",
            function=SimpleNamespace(
                name="createSkill",
                arguments=json.dumps({"name": "focus", "skillContext": content}),
            ),
        )
        self.responses = [
            [_chunk(tool_calls=[tool_call])],
            [_chunk(content="已创建")],
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


def test_chat_session_discovers_skill_metadata_from_working_directory(tmp_path, monkeypatch):
    skill_dir = tmp_path / ".agents" / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Check the weather\n---\n"
        "This body must not be loaded during initialization.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    session = ChatSession(
        Settings(base_url="https://example.invalid", api_key="test", model="test-model"),
        client=FakeClient(),
    )

    assert session.skills["weather"].description == "Check the weather"
    assert "This body" not in repr(session.skills["weather"])


def test_chat_session_injects_skill_metadata_into_system_prompt(tmp_path, monkeypatch):
    skill_dir = tmp_path / ".agents" / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Check the weather\n---\nInstructions\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    session = ChatSession(
        Settings(base_url="https://example.invalid", api_key="test", model="test-model"),
        client=FakeClient(),
    )

    list(session.send("有哪些技能？"))

    system_prompt = session._history[0]["content"]
    assert "You have access to the following skills:" in system_prompt
    assert "- weather: Check the weather" in system_prompt
    assert "Use the `loadSkill` tool" in system_prompt


def test_skill_body_enters_context_only_after_load_skill_call(tmp_path, monkeypatch):
    skill_dir = tmp_path / ".agents" / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Check the weather\n---\n"
        "PRIVATE_SKILL_INSTRUCTIONS\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    session = ChatSession(
        Settings(base_url="https://example.invalid", api_key="test", model="test-model"),
        client=LoadSkillClient(),
    )

    events = list(session.send("加载天气技能"))

    assert "PRIVATE_SKILL_INSTRUCTIONS" not in session._history[0]["content"]
    assert any("PRIVATE_SKILL_INSTRUCTIONS" in event.content for event in events if event.kind == "tool_result")
    assert any(
        item["role"] == "tool" and "PRIVATE_SKILL_INSTRUCTIONS" in item["content"]
        for item in session._history
    )


def test_create_skill_refreshes_current_session_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = ChatSession(
        Settings(base_url="https://example.invalid", api_key="test", model="test-model"),
        client=CreateSkillClient(),
    )

    events = list(session.send("创建一个专注技能"))

    assert any(event.kind == "tool_result" and "已创建 Skill" in event.content for event in events)
    assert session.skills["focus"].description == "Improve focus"
    assert "- focus: Improve focus" in session._history[0]["content"]