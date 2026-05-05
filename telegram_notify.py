"""
Envio de notificacoes via Telegram Bot API.

Le credenciais por ordem:
  1. Env vars TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (cloud / GH Actions secrets)
  2. Arquivo `telegram_config.json` local, formato:
        {"bot_token": "123456:ABC...", "chat_id": "987654321"}

Se nenhum dos dois funcionar, levanta TelegramNotConfigured.
"""

from __future__ import annotations
import json
import mimetypes
import os
import ssl
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent / "telegram_config.json"
API_BASE = "https://api.telegram.org"


class TelegramNotConfigured(Exception):
    """Levantada quando nenhuma fonte de credenciais Telegram esta configurada."""


def _load_config() -> tuple[str, str]:
    # 1. Env vars (cloud)
    token_env = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_env = os.environ.get("TELEGRAM_CHAT_ID")
    if token_env and chat_env:
        return token_env.strip(), chat_env.strip()

    # 2. JSON local
    if not CONFIG_PATH.exists():
        raise TelegramNotConfigured(
            f"Sem env vars TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID e config local "
            f"nao encontrada: {CONFIG_PATH}"
        )
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TelegramNotConfigured(f"JSON invalido em {CONFIG_PATH}: {e}") from e
    token = cfg.get("bot_token")
    chat_id = cfg.get("chat_id")
    if not token or not chat_id:
        raise TelegramNotConfigured("config precisa de 'bot_token' e 'chat_id'")
    return str(token), str(chat_id)


def _post_multipart(url: str, fields: dict, files: dict) -> bytes:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    for k, (fname, content, ctype) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
        parts.append(content)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return r.read()


def send_photo(image_path: Path, caption: str = "") -> None:
    """Envia uma foto pra chat_id configurado. Levanta exceção em erro."""
    token, chat_id = _load_config()
    url = f"{API_BASE}/bot{token}/sendPhoto"
    img_bytes = image_path.read_bytes()
    ctype, _ = mimetypes.guess_type(image_path.name)
    ctype = ctype or "image/png"
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    files = {"photo": (image_path.name, img_bytes, ctype)}
    resp = _post_multipart(url, fields, files)
    data = json.loads(resp.decode("utf-8", errors="replace"))
    if not data.get("ok"):
        raise RuntimeError(f"Telegram retornou erro: {data}")


def send_message(text: str) -> None:
    """Envia texto simples (fallback se foto falhar)."""
    token, chat_id = _load_config()
    url = f"{API_BASE}/bot{token}/sendMessage"
    fields = {"chat_id": chat_id, "text": text}
    body = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in fields.items())
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    if not data.get("ok"):
        raise RuntimeError(f"Telegram retornou erro: {data}")


if __name__ == "__main__":
    import urllib.parse  # used by send_message
    img = Path(__file__).parent / "logs" / "preview.png"
    if not img.exists():
        print(f"ERRO: rode primeiro `python gerar_imagem.py` para criar {img}")
    else:
        try:
            send_photo(img, caption="Teste — Margem Futura")
            print("OK: foto enviada")
        except TelegramNotConfigured as e:
            print(f"AVISO: {e}")
            print("Crie telegram_config.json (veja README do projeto)")
