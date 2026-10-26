import json
import urllib.error

from Agent.Stella.core import tools


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
