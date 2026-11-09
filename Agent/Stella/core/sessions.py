"""Local JSONL persistence for Stella conversation sessions."""

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    updated_at: str
    message_count: int
    preview: str


class SessionStore:
    """Stores complete session histories as simple, inspectable JSONL logs."""

    def __init__(self, project_root: Path | None = None, directory: str = ".agents/sessions"):
        self._root = (project_root or Path.cwd()) / directory
        self._root.mkdir(parents=True, exist_ok=True)

    def new_id(self) -> str:
        base = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = base
        suffix = 1
        while (self._root / f"{session_id}.jsonl").exists():
            session_id = f"{base}-{suffix}"
            suffix += 1
        return session_id

    def save(self, session_id: str, history: list[dict[str, Any]]) -> Path:
        target = self._root / f"{session_id}.jsonl"
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        with target.open("w", encoding="utf-8") as file:
            file.write(json.dumps({"type": "session_saved", "id": session_id, "updated_at": timestamp}, ensure_ascii=False) + "\n")
            for message in history:
                file.write(json.dumps({"type": "message", "message": message}, ensure_ascii=False) + "\n")
            file.flush()
        return target

    def load(self, session_id: str) -> list[dict[str, Any]]:
        target = self._root / f"{session_id}.jsonl"
        if not target.is_file():
            raise FileNotFoundError(f"找不到会话：{session_id}")
        history: list[dict[str, Any]] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("type") == "message" and isinstance(record.get("message"), dict):
                history.append(record["message"])
        return history

    def list(self) -> list[SessionSummary]:
        summaries: list[SessionSummary] = []
        for path in sorted(self._root.glob("*.jsonl"), reverse=True):
            try:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
                header = next(record for record in records if record.get("type") == "session_saved")
                messages = [record["message"] for record in records if record.get("type") == "message"]
            except (OSError, ValueError, StopIteration, json.JSONDecodeError, KeyError, TypeError):
                continue
            preview = next(
                (str(message.get("content", "")).replace("\n", " ")[:80] for message in messages if message.get("role") == "user"),
                "空会话",
            )
            summaries.append(SessionSummary(
                session_id=str(header.get("id", path.stem)),
                updated_at=str(header.get("updated_at", "")),
                message_count=len(messages),
                preview=preview,
            ))
        return summaries
