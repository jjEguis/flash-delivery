"""Reloj e identificadores del servidor; reemplazables en pruebas."""
from datetime import datetime, timezone
import secrets
import time

from lambdas.shared.storage import keys


def now():
    """Instante actual en el formato canónico de claves (UTC, seis decimales, Z)."""
    return keys.timestamp(datetime.now(timezone.utc))


def new_id(prefix):
    """ID opaco ordenable por tiempo: prefijo + milisegundos hex + 48 bits aleatorios."""
    return keys.identifier(f"{prefix}{int(time.time() * 1000):012x}{secrets.token_hex(6)}")


def month_of(timestamp):
    """YYYY-MM de un timestamp canónico."""
    return keys.month(keys.timestamp(timestamp)[:7])
