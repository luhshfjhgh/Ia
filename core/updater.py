# -*- coding: utf-8 -*-
"""
core/updater.py — Auto-atualização da NOX AI via GitHub
────────────────────────────────────────────────────────────────────
Usado pelo comando /manutencao. Compara a versão instalada com a
versão publicada no repositório GitHub do projeto e, se houver uma
mais nova, baixa e substitui os próprios arquivos automaticamente.

Repositório de atualização: https://github.com/luhshfjhgh/Ia (branch main)

Como funciona (visão geral):
  1. Lê a versão local em config/version.json
  2. Busca config/version.json no repositório (raw.githubusercontent.com)
  3. Se forem diferentes, baixa o .zip do repositório inteiro
  4. Faz backup da pasta atual (nox_output_backup_<data>)
  5. Copia os arquivos novos por cima dos atuais — SEM tocar em dados
     pessoais do usuário (memória, contas, .env, config salvo, etc.)
  6. Atualiza a versão local e reinicia o programa

Só usa "requests" (já é dependência do projeto) — nada novo a instalar.
"""

from __future__ import annotations
import os
import sys
import json
import shutil
import tempfile
import zipfile
import time
import requests
from typing import Callable, Optional

# ── Configuração do repositório ───────────────────────────────────────
REPO_OWNER  = "luhshfjhgh"
REPO_NAME   = "Ia"
REPO_BRANCH = "main"

# Caminho DENTRO do repositório onde fica o projeto (ex: "nox_output").
# Deixe "" se o conteúdo do projeto está na raiz do repositório.
REPO_SUBDIR = ""

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # nox_output/
VERSION_FILE = os.path.join(_BASE_DIR, "config", "version.json")

# Arquivos/pastas que NUNCA são sobrescritos — são dados pessoais do
# usuário e não devem ser perdidos numa atualização.
PRESERVE = {
    ".env",
    "config/config.json",
    "memory",
    "logs",
    "nox_aliases.json",
    "nox_notas.txt",
    "nox_habitos.json",
    "nox_metas.json",
    "nox_streak.json",
    ".session",
    "output",
    "projects",
}

ProgressFn = Optional[Callable[[str], None]]


def _preserved(rel_path: str) -> bool:
    rel_path = rel_path.replace("\\", "/")
    for p in PRESERVE:
        if rel_path == p or rel_path.startswith(p + "/"):
            return True
    return False


# ── Versão local ───────────────────────────────────────────────────────
def get_local_version() -> str:
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, encoding="utf-8") as f:
                return json.load(f).get("version", "0.0.0")
        except Exception:
            pass
    return "0.0.0"


def set_local_version(v: str) -> None:
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": v}, f)


# ── Versão remota (no GitHub) ───────────────────────────────────────────
def get_remote_version(timeout: int = 15) -> Optional[str]:
    """Retorna a versão publicada no repositório, ou None se não conseguir checar."""
    subdir = f"{REPO_SUBDIR}/" if REPO_SUBDIR else ""
    url = (
        f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/"
        f"{REPO_BRANCH}/{subdir}config/version.json"
    )
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json().get("version")
    except Exception:
        pass
    return None


# ── Download do repositório ────────────────────────────────────────────
def download_update(progress_cb: ProgressFn = None) -> tuple[str, str]:
    """
    Baixa o .zip do branch atual do repositório.
    Retorna (tmp_dir, pasta_do_projeto_extraida).
    """
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{REPO_BRANCH}.zip"
    if progress_cb:
        progress_cb(f"Baixando atualização de {REPO_OWNER}/{REPO_NAME} ({REPO_BRANCH})...")

    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        raise ConnectionError(f"Falha ao baixar atualização (HTTP {r.status_code}).")

    tmp_dir = tempfile.mkdtemp(prefix="nox_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")
    with open(zip_path, "wb") as f:
        f.write(r.content)

    if progress_cb:
        progress_cb("Extraindo arquivos...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_dir)

    extracted = None
    for name in os.listdir(tmp_dir):
        full = os.path.join(tmp_dir, name)
        if os.path.isdir(full) and name.lower().startswith(REPO_NAME.lower()):
            extracted = full
            break
    if not extracted:
        raise RuntimeError("Não encontrei a pasta extraída do repositório no .zip baixado.")

    if REPO_SUBDIR:
        extracted = os.path.join(extracted, REPO_SUBDIR)
        if not os.path.isdir(extracted):
            raise RuntimeError(f"Pasta '{REPO_SUBDIR}' não encontrada dentro do repositório.")

    return tmp_dir, extracted


# ── Backup da instalação atual ─────────────────────────────────────────
def backup_current(progress_cb: ProgressFn = None) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(_BASE_DIR), f"nox_backup_{ts}")
    if progress_cb:
        progress_cb(f"Fazendo backup em: {backup_dir}")
    shutil.copytree(
        _BASE_DIR,
        backup_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )
    return backup_dir


# ── Aplica a atualização ────────────────────────────────────────────────
def apply_update(new_files_dir: str, progress_cb: ProgressFn = None) -> int:
    """Copia os arquivos novos por cima dos atuais, preservando dados pessoais."""
    count = 0
    for root, dirs, files in os.walk(new_files_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        rel_root = os.path.relpath(root, new_files_dir)
        rel_root = "" if rel_root == "." else rel_root
        for fname in files:
            rel_path = os.path.join(rel_root, fname) if rel_root else fname
            if _preserved(rel_path):
                continue
            src = os.path.join(root, fname)
            dst = os.path.join(_BASE_DIR, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            count += 1
            if progress_cb and count % 15 == 0:
                progress_cb(f"  {count} arquivo(s) atualizado(s)...")
    return count


def cleanup(tmp_dir: str) -> None:
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
