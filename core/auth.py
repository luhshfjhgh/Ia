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

    # ── Migração automática (parte 1): bancos criados por uma versão
    # ainda mais antiga tinham "id" como INTEGER (chave numérica). O
    # código atual usa "id" como TEXT (pra aceitar UUIDs do Supabase).
    # SQLite não deixa alterar o tipo de uma coluna existente, então
    # reconstruímos a tabela do zero preservando todos os dados.
    id_col = next((c for c in conn.execute("PRAGMA table_info(users)").fetchall() if c[1] == "id"), None)
    if id_col and id_col[2].upper() != "TEXT":
        old_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        conn.execute("ALTER TABLE users RENAME TO users_old_migrando")
        conn.execute("""
            CREATE TABLE users (
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
        name_sel = "name" if "name" in old_cols else "username"
        email_sel = "email" if "email" in old_cols else "NULL"
        salt_sel = "salt" if "salt" in old_cols else "NULL"
        role_sel = "role" if "role" in old_cols else "'user'"
        conn.execute(f"""
            INSERT INTO users (id, username, name, email, password_hash, salt, role, created_at)
            SELECT CAST(id AS TEXT), username, {name_sel}, {email_sel},
                   password_hash, {salt_sel}, {role_sel}, created_at
            FROM users_old_migrando
        """)
        conn.execute("DROP TABLE users_old_migrando")
        conn.commit()

    # ── Migração automática (parte 2): bancos criados por uma versão
    # mais antiga da NOX podem não ter as colunas "name", "email" e
    # "role". Adiciona o que estiver faltando, sem apagar dado nenhum.
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    for col_name, col_def in (
        ("name", "TEXT"),
        ("email", "TEXT"),
        ("role", "TEXT NOT NULL DEFAULT 'user'"),
    ):
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass  # coluna já existe (corrida entre processos) — ignora
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
            sb.log_event(created["id"], username, "account_created", f"role={role}")
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
_FAILED_LOGIN_ALERT_THRESHOLD = 5


def login(username: str, password: str) -> tuple[bool, dict | None, str]:
    username = username.strip()
    ip, location = (None, None)
    try:
        import geoip
        ip, location = geoip.get_ip_and_location()
    except Exception:
        pass

    if sb.is_configured():
        try:
            user = sb.get_user_by_username(username)
            if user:
                # ── Conta banida? (independe do PC — segue o usuário) ──
                if user.get("is_banned"):
                    until = user.get("ban_until")
                    still_active = True
                    if until:
                        try:
                            still_active = datetime.fromisoformat(until.replace("Z", "+00:00")).replace(tzinfo=None) > datetime.now()
                        except Exception:
                            still_active = True
                    if still_active:
                        sb.log_event(user["id"], username, "login_blocked_banned", user.get("ban_reason", ""), ip or "", location or "")
                        motivo = user.get("ban_reason") or "sem motivo especificado"
                        return False, None, f"🚫 Esta conta está banida. Motivo: {motivo}"
                    else:
                        sb.unban_account(user["id"])  # ban expirou, libera automaticamente

                stored = user.get("password_hash", "")
                if "$" in stored:
                    pwd_hash, salt = stored.split("$", 1)
                    test_hash, _ = _hash_password(password, salt)
                    if test_hash == pwd_hash:
                        role = user.get("role") or "user"
                        _local_upsert_user(user["id"], username, user.get("name", username),
                                            user.get("email", ""), pwd_hash, salt, role)
                        try:
                            sb.update_user(user["id"], {
                                "last_login": datetime.now().isoformat(),
                                "last_login_ip": ip, "last_login_location": location,
                            })
                            sb.reset_failed_login(user["id"])
                            sb.log_event(user["id"], username, "login_success", "", ip or "", location or "")
                        except Exception:
                            pass
                        return True, {"user_id": user["id"], "username": username, "role": role}, "Login realizado com sucesso!"

                # Senha errada — conta tentativa e alerta por e-mail se passar do limite
                try:
                    new_count = sb.increment_failed_login(user["id"], user.get("failed_login_count", 0))
                    sb.log_event(user["id"], username, "login_failed", f"tentativa {new_count}", ip or "", location or "")
                    if new_count >= _FAILED_LOGIN_ALERT_THRESHOLD:
                        loc_txt = f" (localização aproximada: {location})" if location else ""
                        sb.send_security_alert_email(
                            user.get("email", ""), user.get("name", username),
                            f"{new_count} tentativas de login falharam na sua conta NOX AI{loc_txt}. "
                            f"Se não foi você, troque sua senha.",
                        )
                except Exception:
                    pass
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


# ── Moderação (admin) — ban/desban por CONTA, não por PC ────────────────
def admin_ban_account(target_username: str, reason: str, hours: int | None = None) -> tuple[bool, str]:
    if not sb.is_configured():
        return False, "Isso requer Supabase configurado (ban por conta precisa da nuvem)."
    try:
        user = sb.get_user_by_username(target_username.strip())
        if not user:
            return False, "Usuário não encontrado."
        until_iso = (datetime.now() + timedelta(hours=hours)).isoformat() if hours else None
        sb.ban_account(user["id"], reason, until_iso)
        return True, f"Conta '{target_username}' banida" + (f" por {hours}h." if hours else " (indefinidamente).")
    except Exception as e:
        return False, f"Erro: {e}"


def admin_unban_account(target_username: str) -> tuple[bool, str]:
    if not sb.is_configured():
        return False, "Isso requer Supabase configurado."
    try:
        user = sb.get_user_by_username(target_username.strip())
        if not user:
            return False, "Usuário não encontrado."
        sb.unban_account(user["id"])
        return True, f"Conta '{target_username}' desbanida."
    except Exception as e:
        return False, f"Erro: {e}"


# ── Cota diária de mensagens (não se aplica a admin) ─────────────────────
def check_and_bump_daily_limit(user_id, role: str) -> tuple[bool, int, int]:
    """Retorna (pode_continuar, uso_atual, limite). Admin sempre passa."""
    if role == "admin" or not sb.is_configured():
        return True, 0, 0
    try:
        user = sb.get_user_by_id(user_id)
        if not user:
            return True, 0, 0
        limit = user.get("daily_message_limit") or 200
        count, limit = sb.bump_daily_message_count(user)
        return (count <= limit), count, limit
    except Exception:
        return True, 0, 0  # se a checagem falhar, não trava o usuário por causa de um erro de rede


# ── Auditoria (admin) ────────────────────────────────────────────────────
def get_audit_log(limit: int = 30) -> list[dict]:
    if not sb.is_configured():
        return []
    try:
        return sb.get_audit_log(limit)
    except Exception:
        return []


def log_event(user_id, username: str, event: str, details: str = "") -> None:
    if sb.is_configured():
        try:
            sb.log_event(user_id, username, event, details)
        except Exception:
            pass
