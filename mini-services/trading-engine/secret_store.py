"""Local encrypted secret storage. Secrets are never committed or returned by APIs."""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Dict, Optional


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Encrypted local vault is supported on Windows; use environment variables elsewhere")
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(b"QuantPulse-JARVIS-v1")
    output = _DataBlob()
    _ = source_buffer, entropy_buffer
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "JARVIS local credentials", ctypes.byref(entropy), None, None,
        0x01, ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Encrypted local vault is supported on Windows; use environment variables elsewhere")
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(b"QuantPulse-JARVIS-v1")
    output = _DataBlob()
    _ = source_buffer, entropy_buffer
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None,
        0x01, ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


class LocalSecretStore:
    def __init__(self, path: Optional[Path] = None):
        base = Path(os.getenv("JARVIS_STATE_DIR") or Path(__file__).parent / "data")
        self.path = Path(path or base / "secure" / "credentials.bin")

    def save(self, values: Dict[str, str]) -> None:
        clean = {key: str(value) for key, value in values.items() if value}
        if not clean:
            raise ValueError("No credentials provided")
        encrypted = _protect(json.dumps(clean, separators=(",", ":")).encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_bytes(encrypted)
        temp.replace(self.path)

    def load(self) -> Dict[str, str]:
        try:
            value = json.loads(_unprotect(self.path.read_bytes()).decode("utf-8"))
            return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}
        except (FileNotFoundError, OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
            return {}

    def configured(self) -> bool:
        return self.path.is_file()


def restore_telegram_credentials(store: Optional[LocalSecretStore] = None) -> bool:
    """Restore only missing environment values before broker modules import."""
    values = (store or LocalSecretStore()).load()
    token = values.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = values.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        os.environ.setdefault("TELEGRAM_BOT_TOKEN", token)
        os.environ.setdefault("TELEGRAM_CHAT_ID", chat_id)
        return True
    return False
