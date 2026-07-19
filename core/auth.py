# -*- coding: utf-8 -*-
"""
core/auth.py — Sistema de contas da NOX AI
────────────────────────────────────────────────────────────────────
Cadastro, login e histórico de conversas por usuário, usando SQLite
(banco de dados local em nox_output/memory/nox_accounts.db).

Não depende de nenhum pacote externo — usa apenas a biblioteca padrão
do Python (sqlite3, hashlib, secrets), então funciona em qualquer
instalação sem precisar rodar pip install de novo.

Sessão: depois de logar uma vez, a NOX lembra o usuário automaticamente
nas próximas vezes que o comando "nox" for aberto (arquivo .session).
Use /logout para sair da conta e voltar à tela de login.
"""

from __future__ import annotations
import os
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # nox_output/
_MEMORY_DIR  = os.path.join(_BASE_DIR, "memory")
DB_PATH      = os.path.join(_MEMORY_DIR, "nox_accounts.db")
SESSION_PATH = os.path.join(_MEMORY_DIR, ".session")


def _connect() -> sqlite3.Connection:
    os.makedirs(_MEMORY_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    return conn


# ── Hash de senha (PBKDF2 — padrão do Python, sem dependências) ──────
def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    )
    return digest.hex(), salt


# ── Cadastro ──────────────────────────────────────────────────────────
def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if len(username) < 3:
        return False, "O usuário precisa ter ao menos 3 caracteres."
    if not all(c.isalnum() or c in ("_", "-", ".") for c in username):
        return False, "Use apenas letras, números, _ - . no usuário."
    if len(password) < 4:
        return False, "A senha precisa ter ao menos 4 caracteres."

    conn = _connect()
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            return False, "Esse nome de usuário já existe."
        pwd_hash, salt = _hash_password(password)
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, pwd_hash, salt, datetime.now().isoformat()),
        )
        conn.commit()
        return True, "Conta criada com sucesso!"
    finally:
        conn.close()


# ── Login ─────────────────────────────────────────────────────────────
def login(username: str, password: str) -> tuple[bool, int | None, str]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE username = ?",
            (username.strip(),),
        )
        row = cur.fetchone()
        if not row:
            return False, None, "Usuário não encontrado."
        user_id, stored_hash, salt = row
        test_hash, _ = _hash_password(password, salt)
        if test_hash != stored_hash:
            return False, None, "Senha incorreta."
        return True, user_id, "Login realizado com sucesso!"
    finally:
        conn.close()


# ── Sessão (mantém login entre execuções do comando "nox") ───────────
def save_session(user_id: int, username: str) -> None:
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({"user_id": user_id, "username": username}, f)


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


# ── Histórico de conversas por usuário ────────────────────────────────
def save_message(user_id: int, role: str, content: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_conversation_history(user_id: int, limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT role, content, created_at FROM conversations "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cur.fetchall()
        rows.reverse()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
    finally:
        conn.close()


def delete_account(user_id: int) -> None:
    """Remove a conta e todo o histórico de conversas associado."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
