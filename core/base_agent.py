# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║         NOX AI — Base Agent Class            ║
║     Classe base para todos os agentes        ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(Enum):
    IDLE       = "idle"
    RUNNING    = "running"
    WAITING    = "waiting"
    DONE       = "done"
    ERROR      = "error"


class Priority(Enum):
    LOW      = 1
    NORMAL   = 2
    HIGH     = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    task_id:    str            = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content:    str            = ""
    context:    Dict[str, Any] = field(default_factory=dict)
    priority:   Priority       = Priority.NORMAL
    created_at: float          = field(default_factory=time.time)
    result:     Optional[str]  = None
    error:      Optional[str]  = None
    duration:   float          = 0.0


@dataclass
class AgentResult:
    task_id:    str
    agent_name: str
    success:    bool
    content:    str
    metadata:   Dict[str, Any] = field(default_factory=dict)
    duration:   float          = 0.0


class BaseAgent(ABC):
    """Classe base para todos os agentes NOX."""

    def __init__(
        self,
        name:       str,
        specialty:  str,
        team:       str,
        priority:   Priority = Priority.NORMAL,
        max_tokens: int      = 2000,
    ):
        self.name        = name
        self.specialty   = specialty
        self.team        = team
        self.priority    = priority
        self.max_tokens  = max_tokens
        self.status      = AgentStatus.IDLE
        self.memory: List[Dict[str, str]] = []
        self.tools:  List[str]            = []
        self.stats   = {"tasks": 0, "success": 0, "errors": 0, "total_time": 0.0}
        self.agent_id = str(uuid.uuid4())[:8]

    # ── System prompt abstrato ─────────────────────────────────────
    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    # ── Execução principal ─────────────────────────────────────────
    async def execute(self, task: AgentTask) -> AgentResult:
        self.status = AgentStatus.RUNNING
        start = time.time()
        self.stats["tasks"] += 1
        try:
            result_text = await self._run(task)
            duration    = time.time() - start
            self.stats["success"]    += 1
            self.stats["total_time"] += duration
            self.status = AgentStatus.IDLE
            return AgentResult(
                task_id    = task.task_id,
                agent_name = self.name,
                success    = True,
                content    = result_text,
                duration   = duration,
                metadata   = {"team": self.team, "specialty": self.specialty},
            )
        except Exception as e:
            self.stats["errors"] += 1
            self.status = AgentStatus.ERROR
            return AgentResult(
                task_id    = task.task_id,
                agent_name = self.name,
                success    = False,
                content    = f"[ERRO {self.name}] {e}",
                duration   = time.time() - start,
            )

    @abstractmethod
    async def _run(self, task: AgentTask) -> str: ...

    # ── Memória de curto prazo ─────────────────────────────────────
    def remember(self, role: str, content: str, max_mem: int = 20):
        self.memory.append({"role": role, "content": content})
        if len(self.memory) > max_mem:
            self.memory = self.memory[-max_mem:]

    def clear_memory(self):
        self.memory.clear()

    # ── Representação ──────────────────────────────────────────────
    def __repr__(self) -> str:
        return f"<Agent {self.name} [{self.team}] {self.status.value}>"
