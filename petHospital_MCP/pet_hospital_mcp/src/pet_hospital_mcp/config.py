from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    backend_url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 8.0
    retries: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("MCP_HOST", cls.host),
            port=int(os.getenv("MCP_PORT", str(cls.port))),
            backend_url=os.getenv("PET_HOSPITAL_BASE_URL", cls.backend_url).rstrip("/"),
            timeout_seconds=float(os.getenv("PET_HOSPITAL_TIMEOUT", str(cls.timeout_seconds))),
            retries=int(os.getenv("PET_HOSPITAL_RETRIES", str(cls.retries))),
        )