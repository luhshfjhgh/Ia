# -*- coding: utf-8 -*-
"""
core/auth.py — Sistema de contas da NOX AI (v2 — com Supabase)
────────────────────────────────────────────────────────────────────
Cadastro, login, papéis (admin/usuário), recuperação de senha e
histórico de conversas.

MODO ONLINE (Supabase configurado no .env):
  - Conta funciona em qualquer computador com a mesma conta.
  - Conversas ficam sincronizadas na nuvem (tabelas já usadas pelo
    api_server/: public.users, public.conversations, public.messages).
  - Um cache local (SQLite) guarda os últimos dados pra continuar
    funcionando mesmo sem internet.

MODO OFFLINE (sem Supabase configurado, ou sem internet no momento):
  - Cai automaticamente para o SQLite local (memory/nox_accounts.db),
    exatamente como funcionava antes — nada quebra.

Só usa a biblioteca padrão do Python (sqlite3, hashlib, secrets, json)
mais "requests" (via supabase_client) — nada novo pra instalar.
"""

from __future__ import annotations
import os
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta

import supabase_client as sb

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # nox_output/
_MEMORY_DIR  = os.path.join(_BASE_DIR, "memory")
DB_PATH      = os.path.join(_MEMORY_DIR, "nox_accounts.db")
SESSION_PATH = os.path.join(_MEMORY_DIR, ".session")


# ── SQLite local (cache / fallback offline) ───────────────────────────
def _connect() -> sqlite3.Connection:
    os.makedirs(_MEMORY_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            name          TEXT,
            email         TEXT,
            password_hash TEXT NOT NULL,
            salt          TEXT,
            role          TEXT NOT NULL DEFAULT 'user',
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return digest.hex(), salt


def _local_upsert_user(user_id: str, username: str, name: str, email: str,
                        password_hash: str, salt: str, role: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (id, username, name, email, password_hash, salt, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, name=excluded.name, "
            "email=excluded.email, password_hash=excluded.password_hash, salt=excluded.salt, role=excluded.role",
            (str(user_id), username, name, email, password_hash, salt, role, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _local_get_user(username: str):
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT id, username, name, password_hash, salt, role FROM users WHERE username = ?",
            (username,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _local_count_users() -> int:
    conn = _connect()
    try:
        cur = conn.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]
    finally:
        conn.close()


# ── Cadastro ────────────────────────────────────────────────────────────
def register(username: str, password: str, email: str | None = None, name: str | None = None) -> tuple[bool, str]:
    username = username.strip()
    if len(username) < 3:
        return False, "O usuário precisa ter ao menos 3 caracteres."
    if not all(c.isalnum() or c in ("_", "-", ".") for c in username):
        return False, "Use apenas letras, números, _ - . no usuário."
    if len(password) < 4:
        return False, "A senha precisa ter ao menos 4 caracteres."

    name  = name or username
    email = email or f"{username}@nox.local"
    pwd_hash, salt = _hash_password(password)
    combined_hash = f"{pwd_hash}${salt}"  # formato salvo no Supabase (1 campo só)

    # ── Modo online: cria no Supabase ──────────────────────────────────
    if sb.is_configured():
        try:
            existing = sb.get_user_by_username(username)
            if existing:
                return False, "Esse nome de usuário já existe."
            is_first = sb.count_users() == 0
            role = "admin" if is_first else "user"
            created = sb.create_user(name, username, email, combined_hash, role=role)
            _local_upsert_user(created["id"], username, name, email, pwd_hash, salt, role)
            extra = " Você é o primeiro usuário — virou ADMIN. 👑" if is_first else ""
            return True, f"Conta criada com sucesso (sincronizada na nuvem)!{extra}"
        except Exception as e:
            return False, f"Não consegui falar com o Supabase agora ({e}). Tente novamente ou verifique sua internet."

    # ── Modo offline: só local ──────────────────────────────────────────
    row = _local_get_user(username)
    if row:
        return False, "Esse nome de usuário já existe."
    is_first = _local_count_users() == 0
    role = "admin" if is_first else "user"
    user_id = secrets.token_hex(8)
    _local_upsert_user(user_id, username, name, email, pwd_hash, salt, role)
    extra = " Você é o primeiro usuário — virou ADMIN. 👑" if is_first else ""
    return True, f"Conta criada com sucesso (modo offline — sem Supabase configurado).{extra}"


# ── Login ─────────────────────────────────────────────────────────────
def login(username: str, password: str) -> tuple[bool, dict | None, str]:
    username = username.strip()

    if sb.is_configured():
        try:
            user = sb.get_user_by_username(username)
            if user:
                stored = user.get("password_hash", "")
                if "$" in stored:
                    pwd_hash, salt = stored.split("$", 1)
                    test_hash, _ = _hash_password(password, salt)
                    if test_hash == pwd_hash:
                        role = user.get("role") or "user"
                        _local_upsert_user(user["id"], username, user.get("name", username),
                                            user.get("email", ""), pwd_hash, salt, role)
                        try:
                            sb.update_user(user["id"], {"last_login": datetime.now().isoformat()})
                        except Exception:
                            pass
                        return True, {"user_id": user["id"], "username": username, "role": role}, "Login realizado com sucesso!"
                return False, None, "Senha incorreta."
            # Não achou no Supabase — tenta cache local antes de desistir
        except Exception:
            pass  # sem internet — cai para o cache local abaixo

    row = _local_get_user(username)
    if not row:
        return False, None, "Usuário não encontrado."
    user_id, uname, name, stored_hash, salt, role = row
    test_hash, _ = _hash_password(password, salt)
    if test_hash != stored_hash:
        return False, None, "Senha incorreta."
    return True, {"user_id": user_id, "username": uname, "role": role}, "Login realizado (modo offline)!"


# ── Recuperação de senha ─────────────────────────────────────────────────
def request_password_reset(username: str) -> tuple[bool, str, str | None]:
    """Gera um código de 6 dígitos, salva no Supabase (se disponível) e
    tenta enviar por e-mail via EmailJS. Sempre retorna o código também,
    pra funcionar mesmo se o e-mail falhar (afinal é um app de terminal)."""
    if not sb.is_configured():
        return False, "Recuperação por e-mail requer Supabase configurado. Peça para um admin redefinir sua senha localmente.", None

    try:
        user = sb.get_user_by_username(username.strip())
        if not user:
            return False, "Usuário não encontrado.", None
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = (datetime.now() + timedelta(minutes=15)).isoformat()
        sb.update_user(user["id"], {"reset_code": code, "reset_code_expires_at": expires})
        ok, msg = sb.send_reset_email(user.get("email", ""), user.get("name", username), code)
        if ok:
            return True, f"Código enviado para {user.get('email')}. Válido por 15 min.", code
        return True, f"Não consegui enviar e-mail ({msg}), mas aqui está seu código (válido 15 min):", code
    except Exception as e:
        return False, f"Erro ao gerar código: {e}", None


def reset_password(username: str, code: str, new_password: str) -> tuple[bool, str]:
    if not sb.is_configured():
        return False, "Recuperação requer Supabase configurado."
    if len(new_password) < 4:
        return False, "A nova senha precisa ter ao menos 4 caracteres."
    try:
        user = sb.get_user_by_username(username.strip())
        if not user:
            return False, "Usuário não encontrado."
        stored_code = user.get("reset_code")
        expires_at  = user.get("reset_code_expires_at")
        if not stored_code or stored_code != code.strip():
            return False, "Código inválido."
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                now_dt = datetime.now(exp_dt.tzinfo) if exp_dt.tzinfo else datetime.now()
                if exp_dt < now_dt:
                    return False, "Código expirado. Peça um novo."
            except Exception:
                pass
        pwd_hash, salt = _hash_password(new_password)
        combined_hash = f"{pwd_hash}${salt}"
        sb.update_user(user["id"], {"password_hash": combined_hash, "reset_code": None, "reset_code_expires_at": None})
        _local_upsert_user(user["id"], username, user.get("name", username), user.get("email", ""),
                            pwd_hash, salt, user.get("role", "user"))
        return True, "Senha redefinida com sucesso! Faça login com a nova senha."
    except Exception as e:
        return False, f"Erro ao redefinir senha: {e}"


# ── Sessão local (mantém login entre execuções do comando "nox") ─────
def save_session(user_id, username: str, role: str = "user") -> None:
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({"user_id": user_id, "username": username, "role": role}, f)


def load_session() -> dict | None:
    if os.path.exists(SESSION_PATH):
        try:
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def clear_session() -> None:
    if os.path.exists(SESSION_PATH):
        try:
            os.remove(SESSION_PATH)
        except OSError:
            pass


# ── Histórico de conversas ────────────────────────────────────────────
_conversation_cache: dict[str, str] = {}  # user_id -> conversation_id (Supabase) desta sessão


def _get_or_create_conversation(user_id) -> str | None:
    if not sb.is_configured():
        return None
    key = str(user_id)
    if key in _conversation_cache:
        return _conversation_cache[key]
    try:
        conv = sb.create_conversation(user_id, title=f"Sessão terminal {datetime.now().strftime('%d/%m %H:%M')}")
        _conversation_cache[key] = conv["id"]
        return conv["id"]
    except Exception:
        return None


def save_message(user_id, role: str, content: str) -> None:
    # Cache local — sempre grava, funciona offline
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (str(user_id), role, content, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    # Sincroniza com Supabase, se disponível (nunca derruba o chat se falhar)
    if sb.is_configured():
        try:
            conv_id = _get_or_create_conversation(user_id)
            if conv_id:
                sb.save_message(conv_id, role, content)
        except Exception:
            pass


def get_conversation_history(user_id, limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT role, content, created_at FROM conversations "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (str(user_id), limit),
        )
        rows = cur.fetchall()
        rows.reverse()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
    finally:
        conn.close()


def list_all_users() -> list[dict]:
    """Para /admin_usuarios — tenta Supabase primeiro, cai pro cache local."""
    if sb.is_configured():
        try:
            return sb.list_users()
        except Exception:
            pass
    conn = _connect()
    try:
        cur = conn.execute("SELECT id, username, name, role, created_at FROM users")
        cols = ["id", "username", "name", "role", "created_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
