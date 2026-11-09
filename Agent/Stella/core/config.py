"""Configuration loading for the Stella application."""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    baidu_qianfan_api_key: str = ""
    context_window: int | None = None
    context_warning_ratio: float = 0.7
    cli_timeout_seconds: int = 30
    cli_output_max_chars: int = 20000
    max_read_chars: int = 20000
    max_read_bytes: int = 2 * 1024 * 1024
    context_result_max_chars: int = 8000
    web_timeout_seconds: int = 35
    session_directory: str = ".agents/sessions"
    configuration_required: bool = False
    config_path: Path | None = None

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        path = config_path or Path.cwd() / "config.ini"
        parser = configparser.ConfigParser()
        if not parser.read(path, encoding="utf-8"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_default_config_text(), encoding="utf-8")
            return cls(
                base_url="https://api.example.invalid/v1",
                api_key="replace-with-your-api-key",
                model="replace-with-your-model",
                context_window=128000,
                configuration_required=True,
                config_path=path,
            )
        if not parser.has_section("llm"):
            raise ValueError(f"配置文件缺少 [llm] 区段：{path}")

        section = parser["llm"]
        api_key = os.getenv("STELLA_API_KEY", section.get("api_key", "")).strip()
        base_url = os.getenv("STELLA_BASE_URL", section.get("base_url", "")).strip()
        model = os.getenv("STELLA_MODEL", section.get("model", "")).strip()
        missing = [name for name, value in (("base_url", base_url), ("api_key", api_key), ("model", model)) if not value]
        if missing:
            raise ValueError(f"模型配置不能为空：{', '.join(missing)}")
        configuration_required = (
            "api.example.invalid" in base_url
            or api_key == "replace-with-your-api-key"
            or model == "replace-with-your-model"
        )
        search_api_key = ""
        if parser.has_section("search"):
            search_api_key = parser["search"].get("baidu_qianfan_api_key", "").strip()
        context_section = parser["context"] if parser.has_section("context") else section
        tool_section = parser["tools"] if parser.has_section("tools") else {}
        configured_window = os.getenv("STELLA_CONTEXT_WINDOW", context_section.get("context_window", "")).strip()
        context_window = int(configured_window) if configured_window else None
        warning_ratio = float(os.getenv("STELLA_CONTEXT_WARNING_RATIO", context_section.get("warning_ratio", "0.7")))
        def integer(name: str, default: int) -> int:
            value = os.getenv(f"STELLA_{name.upper()}", str(tool_section.get(name, default))).strip()
            return int(value)

        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            baidu_qianfan_api_key=search_api_key,
            context_window=context_window,
            context_warning_ratio=warning_ratio,
            cli_timeout_seconds=integer("cli_timeout_seconds", 30),
            cli_output_max_chars=integer("cli_output_max_chars", 20000),
            max_read_chars=integer("max_read_chars", 20000),
            max_read_bytes=integer("max_read_bytes", 2 * 1024 * 1024),
            context_result_max_chars=integer("context_result_max_chars", 8000),
            web_timeout_seconds=integer("web_timeout_seconds", 35),
            session_directory=(parser.get("storage", "session_directory", fallback=".agents/sessions")),
            configuration_required=configuration_required,
            config_path=path,
        )


def _default_config_text() -> str:
    return """# Stella 配置文件。请修改 mock 配置后重新启动 Stella。
[llm]
base_url = https://api.example.invalid/v1
api_key = replace-with-your-api-key
model = replace-with-your-model

[context]
context_window = 128000
warning_ratio = 0.7

[tools]
cli_timeout_seconds = 30
cli_output_max_chars = 20000
max_read_chars = 20000
max_read_bytes = 2097152
context_result_max_chars = 8000
web_timeout_seconds = 35

[storage]
session_directory = .agents/sessions

[search]
baidu_qianfan_api_key =
"""