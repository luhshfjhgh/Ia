# -*- coding: utf-8 -*-
"""
memory.py — Gerenciador de memória persistente da Nox AI v2.5
"""

import json
import os
from datetime import datetime
from typing import Any

MEMORY_FILE = "memory.json"
MAX_HISTORY_STORED = 200


class MemoryManager:
    def __init__(self, username: str | None = None):
        """
        Se "username" for informado, a memória fica isolada por conta
        (arquivo memory_<username>.json), permitindo que cada usuário
        cadastrado tenha seus próprios fatos, nome e histórico salvos
        separadamente. Sem username, mantém o comportamento antigo
        (memory.json único) para não quebrar quem não usa contas.
        """
        if username:
            safe = "".join(c for c in username.lower() if c.isalnum() or c in ("_", "-"))
            self.memory_file = f"memory_{safe}.json"
        else:
            self.memory_file = MEMORY_FILE
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "user": {
                "name":       None,
                "first_seen": datetime.now().isoformat(),
                "last_seen":  datetime.now().isoformat(),
                "facts":      {},
            },
            "history": [],
            "stats": {
                "total_exchanges": 0,
                "sessions":        1,
            },
        }

    def save(self):
        self._data["user"]["last_seen"] = datetime.now().isoformat()
        if len(self._data["history"]) > MAX_HISTORY_STORED:
            self._data["history"] = self._data["history"][-MAX_HISTORY_STORED:]
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"  [MEMÓRIA] Erro ao salvar: {e}")

    def clear(self):
        self._data = {
            "user": {
                "name":       None,
                "first_seen": datetime.now().isoformat(),
                "last_seen":  datetime.now().isoformat(),
                "facts":      {},
            },
            "history": [],
            "stats": {"total_exchanges": 0, "sessions": 1},
        }
        self.save()

    # ─── Nome ────────────────────────────────────────────────────────────────

    def get_user_name(self) -> str | None:
        return self._data["user"].get("name")

    def set_user_name(self, name: str):
        self._data["user"]["name"] = name
        self.save()

    # ─── Fatos aprendidos ─────────────────────────────────────────────────────

    def add_fact(self, key: str, value: Any):
        """Salva um fato aprendido sobre o usuário."""
        self._data["user"]["facts"][key] = {
            "value":   value,
            "learned": datetime.now().isoformat(),
        }
        self.save()

    def get_fact(self, key: str) -> Any | None:
        fact = self._data["user"]["facts"].get(key)
        return fact["value"] if fact else None

    def get_all_facts(self) -> dict:
        return self._data["user"].get("facts", {})

    def remove_fact(self, key: str) -> bool:
        if key in self._data["user"]["facts"]:
            del self._data["user"]["facts"][key]
            self.save()
            return True
        return False

    def get_facts_for_prompt(self) -> str:
        """Retorna fatos formatados para incluir no system prompt."""
        facts = self._data["user"].get("facts", {})
        if not facts:
            return ""
        lines = []
        for key, data in facts.items():
            val = data["value"] if isinstance(data, dict) else data
            lines.append(f"- {key}: {val}")
        return "Fatos conhecidos sobre o usuário:\n" + "\n".join(lines)

    def get_facts_summary(self) -> str:
        facts = self._data["user"].get("facts", {})
        if not facts:
            return "(nenhum fato salvo)"
        lines = []
        for key, data in facts.items():
            val = data["value"] if isinstance(data, dict) else data
            learned = ""
            if isinstance(data, dict) and "learned" in data:
                try:
                    dt = datetime.fromisoformat(data["learned"])
                    learned = f"  [{dt.strftime('%d/%m/%Y')}]"
                except Exception:
                    pass
            lines.append(f"  • {key}: {val}{learned}")
        return "\n".join(lines)

    # ─── Histórico ────────────────────────────────────────────────────────────

    def save_exchange(self, user_msg: str, nox_msg: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user":      user_msg,
            "nox":       nox_msg,
        }
        self._data["history"].append(entry)
        self._data["stats"]["total_exchanges"] = (
            self._data["stats"].get("total_exchanges", 0) + 1
        )
        if self._data["stats"]["total_exchanges"] % 10 == 0:
            self.save()

    def get_recent_history(self, n: int = 10) -> list[dict]:
        return self._data["history"][-n:]

    def get_session_history(self) -> list[dict]:
        """Retorna histórico desde a última inicialização (marcado por session_start)."""
        history = self._data["history"]
        # Pega até 50 últimas trocas como "sessão atual"
        return history[-50:]

    # ─── Stats e resumo ───────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        user  = self._data["user"]
        stats = self._data["stats"]

        def fmt_date(iso: str | None) -> str:
            if not iso:
                return "N/A"
            try:
                dt = datetime.fromisoformat(iso)
                return dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                return iso

        return {
            "user_name":       user.get("name", "Desconhecido"),
            "first_seen":      fmt_date(user.get("first_seen")),
            "last_seen":       fmt_date(user.get("last_seen")),
            "total_exchanges": stats.get("total_exchanges", 0),
            "sessions":        stats.get("sessions", 1),
            "facts_count":     len(user.get("facts", {})),
        }

    def increment_sessions(self):
        self._data["stats"]["sessions"] = self._data["stats"].get("sessions", 0) + 1
        self.save()
