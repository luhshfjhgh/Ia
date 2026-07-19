# -*- coding: utf-8 -*-
"""
core/supabase_client.py — Cliente Supabase para a NOX AI (terminal)
────────────────────────────────────────────────────────────────────
Usa a REST API do Supabase (PostgREST) para ler/gravar nas MESMAS
tabelas que o api_server/ (Node) já usa: public.users, public.conversations
e public.messages (ver api_server/database/schema.sql).

Isso permite:
  - Fazer login com a MESMA conta em qualquer computador
  - Ver o histórico de conversas sincronizado na nuvem
  - Recuperar senha por código (campo reset_code já existe no schema)

Usa apenas "requests" — nenhuma biblioteca nova precisa ser instalada.
As chaves já estão no seu .env (NEXT_PUBLIC_SUPABASE_URL e
SUPABASE_SERVICE_ROLE_KEY), usadas pelo api_server/.
"""

from __future__ import annotations
import os
import requests
from typing import Optional, List, Dict, Any


def _load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    for path in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
        except FileNotFoundError:
            pass
    return env


_ENV = _load_env()


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _ENV.get(key, default)


SUPABASE_URL = _get("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
SERVICE_KEY  = _get("SUPABASE_SERVICE_ROLE_KEY")

# EmailJS — usado para enviar o código de recuperação de senha por e-mail
EMAILJS_SERVICE_ID  = _get("EMAILJS_SERVICE_ID")
EMAILJS_TEMPLATE_RESET = _get("EMAILJS_TEMPLATE_RESET")
EMAILJS_PUBLIC_KEY  = _get("EMAILJS_PUBLIC_KEY")
EMAILJS_PRIVATE_KEY = _get("EMAILJS_PRIVATE_KEY")


def is_configured() -> bool:
    return bool(SUPABASE_URL) and bool(SERVICE_KEY) and "COLE_" not in SERVICE_KEY


def _headers(extra: Optional[dict] = None) -> dict:
    h = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra:
        h.update(extra)
    return h


def _url(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


# ── Usuários ────────────────────────────────────────────────────────────
def get_user_by_username(username: str) -> Optional[dict]:
    r = requests.get(
        _url("users"), headers=_headers(),
        params={"username": f"eq.{username}", "select": "*"}, timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def count_users() -> int:
    r = requests.get(
        _url("users"),
        headers=_headers({"Prefer": "count=exact"}),
        params={"select": "id"}, timeout=15,
    )
    cr = r.headers.get("content-range", "0/0")
    try:
        return int(cr.split("/")[-1])
    except Exception:
        return 0


def create_user(name: str, username: str, email: str, password_hash: str, role: str = "user") -> dict:
    payload = {
        "name": name,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "is_verified": True,
        "role": role,
    }
    r = requests.post(_url("users"), headers=_headers(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json()[0]


def update_user(user_id: str, fields: dict) -> dict:
    r = requests.patch(
        _url("users"), headers=_headers(),
        params={"id": f"eq.{user_id}"}, json=fields, timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else {}


# ── Conversas & mensagens ────────────────────────────────────────────────
def create_conversation(user_id: str, title: str = "Sessão via terminal") -> dict:
    payload = {"user_id": user_id, "title": title}
    r = requests.post(_url("conversations"), headers=_headers(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json()[0]


def save_message(conversation_id: str, role: str, content: str) -> dict:
    payload = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "provider": "nox-terminal",
    }
    r = requests.post(_url("messages"), headers=_headers(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json()[0]


def get_messages(conversation_id: str, limit: int = 50) -> List[dict]:
    r = requests.get(
        _url("messages"), headers=_headers(),
        params={
            "conversation_id": f"eq.{conversation_id}",
            "select": "*",
            "order": "created_at.asc",
            "limit": limit,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def list_users() -> List[dict]:
    """Usado pelo /admin_usuarios (apenas admins)."""
    r = requests.get(
        _url("users"), headers=_headers(),
        params={"select": "id,username,name,role,created_at,last_login"}, timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ── Recuperação de senha por e-mail (via EmailJS REST API) ───────────────
def send_reset_email(to_email: str, to_name: str, code: str) -> tuple[bool, str]:
    if not (EMAILJS_SERVICE_ID and EMAILJS_TEMPLATE_RESET and EMAILJS_PUBLIC_KEY):
        return False, "EmailJS não configurado no .env."
    payload = {
        "service_id": EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_RESET,
        "user_id": EMAILJS_PUBLIC_KEY,
        "accessToken": EMAILJS_PRIVATE_KEY,
        "template_params": {
            "to_email": to_email,
            "to_name": to_name,
            "reset_code": code,
        },
    }
    try:
        r = requests.post("https://api.emailjs.com/api/v1.0/email/send", json=payload, timeout=15)
        if r.status_code == 200:
            return True, "E-mail enviado!"
        return False, f"EmailJS retornou {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)
