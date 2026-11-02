import json
from types import SimpleNamespace
import urllib.error

from Agent.Stella.core import tools
from Agent.Stella.core.skills import discover_skills
from Agent.Stella.core.mcp_client import _exposed_tool_name, _format_tool_result


def test_baidu_web_search_empty_config():
    assert "缺少千帆搜索配置" in tools.baidu_web_search("天气", "")


def test_baidu_web_search_network_error(monkeypatch):
    def fail(_request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(tools.urllib.request, "urlopen", fail)
    result = tools.baidu_web_search("天气", "test-key")
    assert "网络请求失败" in result
    assert "connection refused" in result


def test_run_cli_uses_argument_list(monkeypatch):
    class Result:
        returncode = 0
        stdout = "ok\n"
        stderr = "warning\n"

    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(tools.subprocess, "run", run)
    result = tools.run_cli("python", ["-c", "print('ok')"])
    assert captured["command"] == ["python", "-c", "print('ok')"]
    assert captured["kwargs"]["shell"] is False
    assert "stdout:\nok" in result
    assert "stderr:\nwarning" in result
    assert "exit code: 0" in result


def test_run_cli_truncates_output(monkeypatch):
    class Result:
        returncode = 0
        stdout = "x" * (tools.CLI_OUTPUT_MAX_CHARS + 100)
        stderr = ""

    monkeypatch.setattr(tools.subprocess, "run", lambda *args, **kwargs: Result())
    result = tools.run_cli("program", [])
    assert "已截断" in result
    assert len(result) < tools.CLI_OUTPUT_MAX_CHARS + 200


def test_run_cli_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise tools.subprocess.TimeoutExpired(args[0], 30, output="partial", stderr="details")

    monkeypatch.setattr(tools.subprocess, "run", timeout)
    result = tools.run_cli("slow-command", [])
    assert "命令执行超时" in result
    assert "exit code: timeout" in result
    assert "partial" in result


def test_fetch_web_rejects_invalid_url():
    result = tools.fetch_web("not-a-url")
    assert "URL 无效" in result


def test_fetch_web_returns_markdown(monkeypatch):
    class CurlResult:
        returncode = 0
        stdout = "<html><body><article><h1>标题</h1><p>正文段落。</p></article></body></html>"
        stderr = ""

    monkeypatch.setattr(tools.subprocess, "run", lambda *args, **kwargs: CurlResult())
    result = tools.fetch_web("https://example.com/article")
    assert "原始 URL：https://example.com/article" in result
    assert "标题" in result
    assert "正文段落" in result


def test_fetch_web_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise tools.subprocess.TimeoutExpired(args[0], 35)

    monkeypatch.setattr(tools.subprocess, "run", timeout)
    result = tools.fetch_web("https://example.com")
    assert "网页访问超时" in result


def test_search_web_formats_summary_and_references(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "智能搜索摘要"}}],
                "references": [{"title": "官方页面", "url": "https://example.com", "content": "来源摘要"}],
            }).encode()

    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    result = tools.execute_tool("searchWeb", {"query": "测试查询"})
    assert "搜索摘要：\n智能搜索摘要" in result
    assert "[官方页面](https://example.com)" in result
    assert "来源摘要" in result


def test_load_skill_reads_skill_body_and_additional_file(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill\n---\n完整 Skill 说明", encoding="utf-8")
    (skill_dir / "references" / "guide.md").write_text("附加文件内容", encoding="utf-8")
    skills = discover_skills(tmp_path)

    assert tools.execute_tool("loadSkill", {"name": "demo"}, skills).endswith("完整 Skill 说明")
    assert tools.execute_tool("loadSkill", {"name": "demo", "filename": "references/guide.md"}, skills) == "附加文件内容"
    assert tools.execute_tool("loadSkill", {"name": "demo", "filename": ".agents/skills/demo/references/guide.md"}, skills) == "附加文件内容"


def test_load_skill_returns_unique_filename_match(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    (skill_dir / "nested").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill\n---\n说明", encoding="utf-8")
    (skill_dir / "nested" / "guide.md").write_text("唯一文件", encoding="utf-8")
    skills = discover_skills(tmp_path)

    result = tools.execute_tool("loadSkill", {"name": "demo", "filename": "guide.md"}, skills)

    assert result == "唯一文件"


def test_load_skill_rejects_files_outside_skill_directory(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill\n---\n说明", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("不能读取", encoding="utf-8")
    skills = discover_skills(tmp_path)

    result = tools.execute_tool("loadSkill", {"name": "demo", "filename": "../../../secret.txt"}, skills)

    assert "Skill 目录内" in result


def test_create_skill_writes_valid_skill_and_refreshes_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skills = {}
    content = "---\nname: meeting-notes\ndescription: Organize meeting notes\n---\n\n# Meeting Notes\n"

    result = tools.execute_tool("createSkill", {"name": "meeting-notes", "skillContext": content}, skills)

    assert "已创建 Skill" in result
    assert (tmp_path / ".agents" / "skills" / "meeting-notes" / "SKILL.md").read_text(encoding="utf-8") == content
    assert skills["meeting-notes"].description == "Organize meeting notes"


def test_create_skill_rejects_duplicate_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    original = "---\nname: demo\ndescription: Original\n---\nOriginal body\n"
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(original, encoding="utf-8")

    result = tools.execute_tool(
        "createSkill",
        {"name": "demo", "skillContext": "---\nname: demo\ndescription: New\n---\nNew body\n"},
    )

    assert "已存在" in result
    assert skill_file.read_text(encoding="utf-8") == original


def test_create_skill_requires_slug_and_matching_frontmatter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    invalid_name = tools.execute_tool(
        "createSkill",
        {"name": "Meeting Notes", "skillContext": "---\nname: Meeting Notes\ndescription: Notes\n---\n正文"},
    )
    mismatched_name = tools.execute_tool(
        "createSkill",
        {"name": "meeting-notes", "skillContext": "---\nname: other\ndescription: Notes\n---\n正文"},
    )

    assert "名称必须只包含" in invalid_name
    assert "name 必须与参数 name 一致" in mismatched_name


def test_execute_tool_dispatches_mcp_tool_without_affecting_local_tools():
    class FakeMCP:
        def has_tool(self, name):
            return name == "mcp__pet-hospital__list_pets"

        def execute(self, name, arguments):
            return f"called {name}: {arguments['page']}"

    result = tools.execute_tool(
        "mcp__pet-hospital__list_pets",
        {"page": 2},
        mcp_manager=FakeMCP(),
    )

    assert result == "called mcp__pet-hospital__list_pets: 2"
    assert "当前工作目录" in tools.execute_tool("getCurrentDir", {}, mcp_manager=FakeMCP())


def test_mcp_tool_names_are_prefixed_and_results_preserve_data_and_errors():
    assert _exposed_tool_name("pet-hospital", "list_pets") == "mcp__pet-hospital__list_pets"
    success = _format_tool_result(SimpleNamespace(
        isError=False,
        structuredContent={"count": 2},
        content=[SimpleNamespace(type="text", text="查询完成")],
    ))
    failure = _format_tool_result(SimpleNamespace(
        isError=True,
        structuredContent=None,
        content=[SimpleNamespace(type="text", text="后端不可用")],
    ))

    assert '"count": 2' in success
    assert "查询完成" in success
    assert "MCP 工具返回错误" in failure


def test_baidu_web_search_api_error(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"error": {"message": "invalid api key"}}).encode()

    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    result = tools.baidu_web_search("天气", "test-key")
    assert "千帆搜索 API 返回失败" in result
    assert "invalid api key" in result
