# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║     NOX AI — Project File Exporter           ║
║   Salva projetos gerados em disco            ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Dict, Optional

PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "..", "projects")


def _safe_name(name: str) -> str:
    """Converte nome de projeto em nome de pasta seguro."""
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"\s+", "_", name.strip())
    return name[:40] or "projeto"


def export_project(project_id: str) -> str:
    """Exporta todos os arquivos de um projeto para disco."""
    from memory.global_memory import gm

    project = gm.get_project(project_id)
    if not project:
        return f"Projeto '{project_id}' não encontrado."

    safe_name = _safe_name(project["name"])
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir   = os.path.join(PROJECTS_DIR, f"{safe_name}_{ts}")

    os.makedirs(out_dir, exist_ok=True)

    files: Dict[str, str] = project.get("files", {})
    saved = []

    for rel_path, content in files.items():
        full_path = os.path.join(out_dir, rel_path.lstrip("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            saved.append(rel_path)
        except Exception as e:
            saved.append(f"[ERRO] {rel_path}: {e}")

    # Criar estrutura padrão ausente
    _ensure_structure(out_dir)

    lines = [
        f"\n📁 Projeto salvo em:",
        f"   {out_dir}",
        f"📄 {len(saved)} arquivo(s) gerado(s):",
    ] + [f"   • {f}" for f in saved]

    if not saved:
        lines.append("   ⚠️  Nenhum arquivo encontrado no projeto.")

    return "\n".join(lines)


def _ensure_structure(base: str):
    """Garante pastas padrão do projeto."""
    for folder in ["assets/css", "assets/js", "assets/images"]:
        os.makedirs(os.path.join(base, folder), exist_ok=True)

    # .gitkeep nas pastas de imagens
    gitkeep = os.path.join(base, "assets", "images", ".gitkeep")
    if not os.path.exists(gitkeep):
        open(gitkeep, "w", encoding="utf-8").close()


def list_exported_projects() -> str:
    if not os.path.exists(PROJECTS_DIR):
        return "Nenhum projeto exportado ainda."
    folders = sorted(os.listdir(PROJECTS_DIR), reverse=True)
    if not folders:
        return "Nenhum projeto exportado ainda."
    lines = ["📁 Projetos exportados:\n"]
    for f in folders[:10]:
        full = os.path.join(PROJECTS_DIR, f)
        if os.path.isdir(full):
            n_files = sum(len(files) for _, _, files in os.walk(full))
            lines.append(f"  • {f}  ({n_files} arquivos)")
    return "\n".join(lines)
