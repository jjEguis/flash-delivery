"""Configuración exclusiva del entorno local; nunca usa perfiles AWS."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


def validate_endpoint(value: str) -> str:
    url = urlsplit(value)
    if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "ministack"}
            or url.username or url.password or url.query or url.fragment
            or url.path not in {"", "/"}):
        raise ValueError("AWS_ENDPOINT_URL debe ser HTTP local: localhost, 127.0.0.1 o ministack")
    if not url.port:
        raise ValueError("AWS_ENDPOINT_URL requiere puerto explícito")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    endpoint: str
    region: str
    table_name: str
    redis_host: str
    redis_port: int
    connect_timeout: float
    read_timeout: float

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env", override=False)
        if os.getenv("ENVIRONMENT", "local") != "local":
            raise ValueError("Esta fase solo permite ENVIRONMENT=local")
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            # MiniStack sin AUTH inyecta el ID de cuenta emulada como access key.
            allowed = {"test", "000000000000"} if key == "AWS_ACCESS_KEY_ID" else {"test"}
            if os.getenv(key, "test") not in allowed:
                raise ValueError(f"{key} solo permite credenciales ficticias locales")
        host = os.getenv("REDIS_HOST", "127.0.0.1")
        if host not in {"localhost", "127.0.0.1", "redis"}:
            raise ValueError("REDIS_HOST debe apuntar al Redis local")
        connect = float(os.getenv("CONNECT_TIMEOUT", "2"))
        read = float(os.getenv("READ_TIMEOUT", "5"))
        port = int(os.getenv("REDIS_PORT", "6379"))
        if connect <= 0 or read <= 0 or not 0 < port < 65536:
            raise ValueError("Timeouts y puerto de Redis inválidos")
        return cls(validate_endpoint(os.getenv("AWS_ENDPOINT_URL", "http://127.0.0.1:4566")),
                   os.getenv("AWS_REGION", "us-east-1"),
                   os.getenv("DYNAMODB_TABLE_NAME", "FlashDeliveryTable"),
                   host, port, connect, read)
