# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║         NOX AI — Team Leaders                ║
║  Cada líder coordena seu time de agentes     ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import asyncio
import sys, os
# Aponta para a raiz do projeto (agents/leadership → ../..)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from typing import Dict, List, Tuple
from core.base_agent  import BaseAgent, AgentTask, AgentResult, Priority
from core.grok_client import call_grok_async, quick_prompt
from memory.global_memory import gm


class TeamLeader:
    """Coordena um time de agentes especializados."""

    def __init__(self, name: str, team: str, description: str):
        self.name        = name
        self.team        = team
        self.description = description
        self._agents: Dict[str, BaseAgent] = {}

    def register_agent(self, key: str, agent: BaseAgent):
        self._agents[key] = agent

    # ── Selecionar agentes para a tarefa ───────────────────────────
    async def select_agents(self, task: str) -> List[str]:
        if not self._agents:
            return []
        agent_list = "\n".join(f"- {k}: {a.specialty}" for k, a in self._agents.items())
        prompt = (
            f"Tarefa recebida: '{task}'\n\n"
            f"Agentes disponíveis no time {self.team}:\n{agent_list}\n\n"
            f"Responda SOMENTE com os nomes dos agentes necessários separados por vírgula, "
            f"sem explicação. Máximo 4 agentes. Apenas os mais relevantes."
        )
        resp = await quick_prompt(prompt, max_tokens=100)
        selected = [k.strip().lower() for k in resp.split(",") if k.strip().lower() in self._agents]
        return selected if selected else list(self._agents.keys())[:2]

    # ── Executar time em paralelo ──────────────────────────────────
    async def run_team(self, task: AgentTask, agent_keys: List[str] = None) -> List[AgentResult]:
        if agent_keys is None:
            agent_keys = await self.select_agents(task.content)

        results = await asyncio.gather(
            *[self._agents[k].execute(task) for k in agent_keys if k in self._agents],
            return_exceptions=True
        )
        valid = []
        for r in results:
            if isinstance(r, AgentResult):
                valid.append(r)
                gm.add_short(f"[{r.agent_name}] {r.content[:200]}", source=r.agent_name)
        return valid

    # ── Consolidar resultados ──────────────────────────────────────
    async def consolidate(self, task: str, results: List[AgentResult]) -> str:
        if not results:
            return "Nenhum resultado gerado."
        if len(results) == 1:
            return results[0].content

        combined = "\n\n".join(
            f"=== {r.agent_name} ===\n{r.content}" for r in results
        )
        prompt = (
            f"Tarefa original: '{task}'\n\n"
            f"Resultados dos agentes do time {self.team}:\n\n{combined}\n\n"
            f"Consolide esses resultados em uma resposta única, coerente e completa em português."
        )
        return await quick_prompt(prompt, max_tokens=3000)

    # ── Executar e consolidar ──────────────────────────────────────
    async def handle(self, task: AgentTask) -> str:
        agent_keys = await self.select_agents(task.content)
        results    = await self.run_team(task, agent_keys)
        return await self.consolidate(task.content, results)

    def list_agents(self) -> List[str]:
        return list(self._agents.keys())


# ═══════════════════════════════════════════════
#  LÍDERES DE CADA TIME
# ═══════════════════════════════════════════════

def create_web_leader() -> TeamLeader:
    from agents.research.web.web_agents import WEB_AGENTS
    leader = TeamLeader("WebTeamLead", "web", "Cria sites, landing pages, e-commerce, SaaS, blogs")
    for k, cls in WEB_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_software_leader() -> TeamLeader:
    from agents.specialized_agents import SOFTWARE_AGENTS
    leader = TeamLeader("SoftwareTeamLead", "software", "Cria sistemas, APIs, backends, bancos de dados")
    for k, cls in SOFTWARE_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_design_leader() -> TeamLeader:
    from agents.specialized_agents import DESIGN_AGENTS
    leader = TeamLeader("DesignTeamLead", "design", "UI/UX, branding, cores, tipografia, logos")
    for k, cls in DESIGN_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_content_leader() -> TeamLeader:
    from agents.specialized_agents import CONTENT_AGENTS
    leader = TeamLeader("ContentTeamLead", "content", "Copywriting, blog, marketing, redes sociais")
    for k, cls in CONTENT_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_automation_leader() -> TeamLeader:
    from agents.specialized_agents import AUTOMATION_AGENTS
    leader = TeamLeader("AutomationTeamLead", "automation", "Workflows, scrapers, bots, integrações")
    for k, cls in AUTOMATION_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_security_leader() -> TeamLeader:
    from agents.specialized_agents import SECURITY_AGENTS
    leader = TeamLeader("SecurityTeamLead", "security", "Segurança, vulnerabilidades, compliance")
    for k, cls in SECURITY_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_qa_leader() -> TeamLeader:
    from agents.specialized_agents import QA_AGENTS
    leader = TeamLeader("QATeamLead", "qa", "Testes, debug, performance, acessibilidade")
    for k, cls in QA_AGENTS.items():
        leader.register_agent(k, cls())
    return leader


def create_research_leader() -> TeamLeader:
    """Time de pesquisa usa agentes genéricos por ora."""
    leader = TeamLeader("ResearchTeamLead", "research", "Pesquisa, análise, relatórios técnicos")
    return leader


def create_infra_leader() -> TeamLeader:
    leader = TeamLeader("InfraTeamLead", "infrastructure", "DevOps, CI/CD, Docker, cloud")
    return leader


def create_data_leader() -> TeamLeader:
    leader = TeamLeader("DataTeamLead", "data", "Análise de dados, ML, visualização")
    return leader
