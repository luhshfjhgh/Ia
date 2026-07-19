# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║         NOX AI — Global Memory System        ║
║  Short-Term · Long-Term · Project · User     ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "agent_memory.json")


# ── Estruturas de dados ────────────────────────────────────────────
@dataclass
class MemoryEntry:
    content:    str
    source:     str          = "unknown"
    timestamp:  float        = field(default_factory=time.time)
    tags:       List[str]    = field(default_factory=list)
    importance: int          = 1   # 1-5

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "MemoryEntry":
        return cls(**d)


# ── Gerenciador global (singleton) ────────────────────────────────
class GlobalMemory:
    _instance: Optional["GlobalMemory"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        # Memória de curto prazo (últimas 100 interações)
        self.short_term: Deque[MemoryEntry] = deque(maxlen=100)
        # Memória de longo prazo (persistida em disco)
        self.long_term:  List[MemoryEntry]  = []
        # Memória de projetos ativos
        self.projects:   Dict[str, Dict[str, Any]] = {}
        # Memória de usuário
        self.user:       Dict[str, Any] = {}
        # Cache de resultados de agentes
        self.agent_cache: Dict[str, str] = {}
        self._load()

    # ── Persistência ───────────────────────────────────────────────
    def _load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.long_term = [MemoryEntry.from_dict(e) for e in data.get("long_term", [])]
                self.projects  = data.get("projects", {})
                self.user      = data.get("user", {})
            except Exception:
                pass

    def save(self):
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "long_term": [e.to_dict() for e in self.long_term[-500:]],
                        "projects":  self.projects,
                        "user":      self.user,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    # ── API Pública ────────────────────────────────────────────────
    def add_short(self, content: str, source: str = "system", tags: List[str] = None, importance: int = 1):
        self.short_term.append(MemoryEntry(content, source, tags=tags or [], importance=importance))

    def add_long(self, content: str, source: str = "system", tags: List[str] = None, importance: int = 3):
        entry = MemoryEntry(content, source, tags=tags or [], importance=importance)
        self.long_term.append(entry)
        if len(self.long_term) % 10 == 0:
            self.save()

    def get_recent(self, n: int = 10) -> List[str]:
        items = list(self.short_term)[-n:]
        return [f"[{e.source}] {e.content}" for e in items]

    def get_long_term(self, tag: str = None, limit: int = 20) -> List[str]:
        entries = self.long_term
        if tag:
            entries = [e for e in entries if tag in e.tags]
        return [f"[{e.source}] {e.content}" for e in entries[-limit:]]

    # ── Projetos ───────────────────────────────────────────────────
    def start_project(self, project_id: str, name: str, description: str = "") -> Dict:
        self.projects[project_id] = {
            "id":          project_id,
            "name":        name,
            "description": description,
            "created_at":  datetime.now().isoformat(),
            "files":       {},
            "status":      "active",
            "history":     [],
        }
        self.save()
        return self.projects[project_id]

    def update_project(self, project_id: str, key: str, value: Any):
        if project_id in self.projects:
            self.projects[project_id][key] = value
            self.projects[project_id]["history"].append(
                {"ts": datetime.now().isoformat(), "key": key, "action": "update"}
            )
            self.save()

    def add_project_file(self, project_id: str, filename: str, content: str):
        if project_id in self.projects:
            self.projects[project_id]["files"][filename] = content
            self.save()

    def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects.get(project_id)

    def list_projects(self) -> List[Dict]:
        return list(self.projects.values())

    # ── Usuário ────────────────────────────────────────────────────
    def set_user(self, key: str, value: Any):
        self.user[key] = value
        self.save()

    def get_user(self, key: str, default: Any = None) -> Any:
        return self.user.get(key, default)

    # ── Cache de agentes ───────────────────────────────────────────
    def cache_result(self, key: str, value: str):
        self.agent_cache[key] = value

    def get_cache(self, key: str) -> Optional[str]:
        return self.agent_cache.get(key)

    # ── Context para prompts ───────────────────────────────────────
    def build_context_string(self, project_id: str = None) -> str:
        parts = []
        recent = self.get_recent(5)
        if recent:
            parts.append("Contexto recente:\n" + "\n".join(recent))
        if project_id:
            proj = self.get_project(project_id)
            if proj:
                files = list(proj["files"].keys())
                parts.append(f"Projeto '{proj['name']}': {len(files)} arquivo(s) gerado(s): {', '.join(files)}")
        if self.user:
            user_info = ", ".join(f"{k}={v}" for k, v in list(self.user.items())[:5])
            parts.append(f"Usuário: {user_info}")
        return "\n".join(parts)


# Instância global
gm = GlobalMemory()
