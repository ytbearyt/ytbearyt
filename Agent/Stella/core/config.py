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

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        path = config_path or PROJECT_ROOT / "core" / "config.ini"
        parser = configparser.ConfigParser()
        if not parser.read(path, encoding="utf-8"):
            raise FileNotFoundError(
                f"找不到配置文件：{path}。请复制 core/config.example.ini 为 core/config.ini 并填写模型配置。"
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
        search_api_key = ""
        if parser.has_section("search"):
            search_api_key = parser["search"].get("baidu_qianfan_api_key", "").strip()
        return cls(base_url=base_url, api_key=api_key, model=model, baidu_qianfan_api_key=search_api_key)