# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║       NOX AI — Orchestrator Agent            ║
║   Cérebro central que coordena todos os      ║
║   times e agentes especializados             ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.base_agent   import AgentTask, AgentResult, Priority
from core.grok_client  import call_grok_async, quick_prompt
from memory.global_memory import gm


# ── Mapeamento de intenções → times ───────────────────────────────
INTENT_TEAM_MAP: Dict[str, str] = {
    # Web
    "landing page": "web",  "site": "web",         "página": "web",
    "html": "web",          "css": "web",           "react": "web",
    "nextjs": "web",        "vue": "web",           "tailwind": "web",
    "bootstrap": "web",     "e-commerce": "web",    "loja": "web",
    "blog": "web",          "saas": "web",          "portfolio": "web",
    "dashboard": "web",     "frontend": "web",      "interface": "web",
    # Software
    "api": "software",      "backend": "software",  "python": "software",
    "fastapi": "software",  "flask": "software",    "node": "software",
    "banco de dados": "software", "autenticação": "software",
    "sistema": "software",  "servidor": "software", "endpoint": "software",
    # Design
    "design": "design",     "logo": "design",       "cor": "design",
    "paleta": "design",     "fonte": "design",      "branding": "design",
    "identidade": "design", "ui": "design",         "ux": "design",
    # Content
    "texto": "content",     "copy": "content",      "artigo": "content",
    "post": "content",      "marketing": "content", "seo": "content",
    "descrição": "content", "instagram": "content", "linkedin": "content",
    # Automation
    "automação": "automation", "bot": "automation", "scraper": "automation",
    "whatsapp": "automation",  "telegram": "automation", "workflow": "automation",
    "integração": "automation", "agendamento": "automation",
    # Security
    "segurança": "security", "vulnerabilidade": "security",
    "revisão de código": "security", "compliance": "security", "lgpd": "security",
    # QA
    "teste": "qa",          "bug": "qa",            "erro": "qa",
    "debug": "qa",          "performance": "qa",    "corrigir": "qa",
}

# ── Projetos completos (múltiplos times) ───────────────────────────
FULL_PROJECT_KEYWORDS = [
    # site / página
    "crie um site", "crie uma página", "crie uma pagina",
    "criar site", "criar página", "criar pagina",
    "gere um site", "gere uma página", "gere uma pagina",
    "gerar site", "gerar página", "gerar pagina",
    "monte um site", "monte uma página",
    "faça um site", "faca um site", "faz um site",
    "desenvolva um site", "desenvolva uma página",
    "crie um portal", "criar portal",
    # landing page
    "crie uma landing", "criar landing", "landing page",
    # sistema / app / plataforma
    "crie um sistema", "criar sistema",
    "crie uma aplicação", "criar aplicação",
    "crie um app", "criar app",
    "criar plataforma", "crie uma plataforma",
    "criar saas", "crie um saas",
    # e-commerce / loja
    "crie um e-commerce", "criar e-commerce",
    "crie uma loja", "criar loja virtual",
    # blog / portfólio
    "crie um blog", "criar blog",
    "crie um portfólio", "criar portfólio",
    "crie um portfolio", "criar portfolio",
    # genérico completo
    "criar sistema completo", "criar aplicação completa",
    "criar plataforma ead", "criar blog completo",
]


@dataclass
class OrchestratorTask:
    request_id:  str           = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_input:  str           = ""
    intent:      str           = ""
    teams:       List[str]     = field(default_factory=list)
    project_id:  Optional[str] = None
    created_at:  float         = field(default_factory=time.time)
    results:     Dict[str, str] = field(default_factory=dict)
    final_output: str          = ""
    duration:    float         = 0.0


class OrchestratorAgent:
    """Agente orquestrador central da NOX AI."""

    SYSTEM_PROMPT = """Você é o Orquestrador Central da NOX AI, uma IA avançada com mais de 60 agentes especializados.

Suas responsabilidades:
1. Analisar solicitações do usuário e identificar a intenção
2. Decidir quais times e agentes são necessários
3. Quebrar tarefas complexas em subtarefas
4. Coordenar execução paralela de agentes
5. Revisar e consolidar resultados
6. Entregar respostas completas e profissionais

Você responde SEMPRE em português brasileiro.
Seja preciso, eficiente e entregue resultados de alta qualidade."""

    def __init__(self):
        self._teams: Dict[str, Any] = {}
        self._history: List[OrchestratorTask] = []
        self._initialized = False
        self._project_counter = 0

    def _lazy_init(self):
        """Inicializa times sob demanda para evitar imports circulares."""
        if self._initialized:
            return
        try:
            from agents.leadership.team_leaders import (
                create_web_leader, create_software_leader,
                create_design_leader, create_content_leader,
                create_automation_leader, create_security_leader,
                create_qa_leader, create_research_leader,
                create_infra_leader, create_data_leader,
            )
            self._teams = {
                "web":            create_web_leader(),
                "software":       create_software_leader(),
                "design":         create_design_leader(),
                "content":        create_content_leader(),
                "automation":     create_automation_leader(),
                "security":       create_security_leader(),
                "qa":             create_qa_leader(),
                "research":       create_research_leader(),
                "infrastructure": create_infra_leader(),
                "data":           create_data_leader(),
            }
            self._initialized = True
        except Exception as e:
            print(f"[Orchestrator] Erro ao inicializar times: {e}")

    # ── Analisar intenção ──────────────────────────────────────────
    async def _analyze_intent(self, user_input: str) -> Tuple[str, List[str]]:
        lower = user_input.lower()

        # Verificar se é projeto completo
        is_full_project = any(kw in lower for kw in FULL_PROJECT_KEYWORDS)
        if is_full_project:
            return "full_project", ["web", "design", "content", "qa"]

        # Mapear por palavras-chave
        teams_found = set()
        for keyword, team in INTENT_TEAM_MAP.items():
            if keyword in lower:
                teams_found.add(team)

        if teams_found:
            intent = f"task_{list(teams_found)[0]}"
            return intent, list(teams_found)

        # Usar IA para determinar intenção
        team_names = list(self._teams.keys())
        prompt = (
            f"Solicitação: '{user_input}'\n\n"
            f"Times disponíveis: {', '.join(team_names)}\n\n"
            f"Qual(is) time(s) deve(m) tratar essa solicitação? "
            f"Responda SOMENTE com os nomes dos times separados por vírgula."
        )
        resp = await quick_prompt(prompt, max_tokens=100)
        teams = [t.strip().lower() for t in resp.split(",") if t.strip().lower() in self._teams]
        if not teams:
            teams = ["software"]  # fallback

        return f"task_{teams[0]}", teams

    # ── Gerar plano de execução ────────────────────────────────────
    async def _plan(self, user_input: str, teams: List[str]) -> Dict[str, str]:
        if len(teams) <= 1:
            return {teams[0]: user_input} if teams else {}

        team_list = ", ".join(teams)
        prompt = (
            f"Tarefa: '{user_input}'\n\n"
            f"Times envolvidos: {team_list}\n\n"
            f"Gere um plano em JSON. Para cada time, defina a subtarefa específica.\n"
            f"Formato: {{\"web\": \"criar o frontend...\", \"software\": \"criar a API...\"}}\n"
            f"Responda SOMENTE com o JSON válido."
        )
        resp = await quick_prompt(prompt, max_tokens=500)
        try:
            # Limpar possíveis blocos de código
            clean = resp.strip()
            if "```" in clean:
                clean = clean.split("```")[1].replace("json", "").strip()
            plan = json.loads(clean)
            # Garantir que só tem times válidos
            return {k: v for k, v in plan.items() if k in self._teams}
        except Exception:
            return {t: user_input for t in teams}

    # ── Barra de progresso ─────────────────────────────────────────
    @staticmethod
    def _progress(step: int, total: int, label: str, detail: str = ""):
        bar_len = 30
        filled  = int(bar_len * step / total)
        bar     = "█" * filled + "░" * (bar_len - filled)
        pct     = int(100 * step / total)
        detail_str = f"  ↳ {detail}" if detail else ""
        print(f"\r  [{bar}] {pct:3d}%  {label}{detail_str}        ", end="", flush=True)

    # ── Executar projeto completo (site/sistema) ───────────────────
    async def _run_full_project(self, user_input: str, project_id: str) -> str:
        TOTAL_STEPS = 3
        step = 0

        def prog(label: str, detail: str = ""):
            nonlocal step
            step += 1
            self._progress(step, TOTAL_STEPS, label, detail)

        print(f"\n  {'─'*54}")
        print(f"  🎯 Tarefa  : {user_input[:60]}")
        print(f"  📋 Projeto : {project_id}")
        print(f"  ⚡ Modo    : Eficiente (3 chamadas API — plano gratuito)")
        print(f"  {'─'*54}\n")

        gm.add_short(f"Iniciando projeto: {user_input}", source="orchestrator", importance=5)

        # ── CHAMADA 1: Planejamento + Design + Conteúdo ──────────────
        prog("Planejando e definindo conteúdo...", "estrutura, design e textos")
        prompt1 = f"""Você é um especialista em desenvolvimento web. Crie o planejamento completo para:

PROJETO: {user_input}

Responda em 3 seções bem separadas:

## PLANO
Nome do projeto, descrição, tecnologias usadas, paleta de cores (hex), fontes, estrutura de arquivos.

## DESIGN
Identidade visual completa: cores primária/secundária/acento, tipografia, estilo (moderno/minimalista/etc), ícones sugeridos.

## CONTEÚDO
Todos os textos do site: título principal, subtítulo, seções, parágrafos, call-to-actions, rodapé. Seja rico e detalhado.

Responda em português brasileiro."""

        resp1 = await quick_prompt(prompt1, max_tokens=3000)
        gm.update_project(project_id, "plan", resp1)
        gm.add_project_file(project_id, "planejamento.md", resp1)

        # Extrai seções
        sections = {"plano": "", "design": "", "conteudo": ""}
        current = None
        for line in resp1.splitlines():
            l = line.lower().strip()
            if "## plano" in l:      current = "plano"
            elif "## design" in l:   current = "design"
            elif "## conteúdo" in l or "## conteudo" in l: current = "conteudo"
            elif current:
                sections[current] += line + "\n"

        await asyncio.sleep(8)  # respeita limite gratuito

        # ── CHAMADA 2: HTML + CSS completos ─────────────────────────
        prog("Gerando HTML e CSS...", "estrutura completa + estilos responsivos")
        prompt2 = f"""Você é um desenvolvedor web expert. Crie um site completo e profissional para:

PROJETO: {user_input}

PLANO E DESIGN:
{sections['plano'][:600]}
{sections['design'][:400]}

CONTEÚDO PARA USAR:
{sections['conteudo'][:800]}

INSTRUÇÕES:
- Crie um arquivo HTML5 completo e moderno
- CSS embutido no <style> (não arquivo separado)
- Design responsivo (mobile-first)
- Cores vibrantes e modernas
- Animações CSS suaves
- Seções: Hero, Sobre, Benefícios/Features, Depoimentos, CTA, Rodapé
- Use gradientes, sombras, bordas arredondadas
- Sem JavaScript externo, apenas CSS puro

Responda SOMENTE com o código HTML completo, começando com <!DOCTYPE html>"""

        html_content = await quick_prompt(prompt2, max_tokens=8000)

        # Limpa bloco de código se vier com ```
        html_clean = html_content.strip()
        if "```html" in html_clean:
            html_clean = html_clean.split("```html")[1].split("```")[0].strip()
        elif "```" in html_clean:
            html_clean = html_clean.split("```")[1].split("```")[0].strip()

        gm.add_project_file(project_id, "index.html", html_clean)

        await asyncio.sleep(8)

        # ── CHAMADA 3: JavaScript + README ──────────────────────────
        prog("Adicionando interatividade e documentação...", "JavaScript + README")
        prompt3 = f"""Crie o JavaScript para o site: {user_input}

O site tem as seguintes seções: Hero, Sobre, Benefícios, Depoimentos, CTA, Rodapé.

Crie um arquivo main.js com:
- Menu mobile hamburger (toggle)
- Scroll suave para âncoras
- Animação de entrada dos elementos ao rolar (Intersection Observer)
- Contador animado nos números/estatísticas se houver
- Botão "voltar ao topo"
- Destaque do menu conforme seção ativa

Depois, separado por ===README===, crie um README.md profissional com:
- Descrição do projeto
- Tecnologias
- Estrutura de arquivos
- Como abrir (abrir index.html no navegador)"""

        resp3 = await quick_prompt(prompt3, max_tokens=3000)

        js_content = resp3
        readme_content = ""
        if "===README===" in resp3:
            parts = resp3.split("===README===")
            js_content   = parts[0].strip()
            readme_content = parts[1].strip()

        # Limpa blocos de código
        for marker in ["```javascript", "```js", "```"]:
            if marker in js_content:
                js_content = js_content.split(marker)[1].split("```")[0].strip()
                break

        gm.add_project_file(project_id, "assets/js/main.js", js_content)
        if readme_content:
            gm.add_project_file(project_id, "README.md", readme_content)
        else:
            gm.add_project_file(project_id, "README.md", f"# {user_input}\n\nAbra o arquivo index.html no navegador.")

        # Finalizado
        self._progress(TOTAL_STEPS, TOTAL_STEPS, "Projeto concluído! ✅")
        print("\n")

        gm.update_project(project_id, "status", "completed")
        gm.update_project(project_id, "results", ["planejamento", "index.html", "main.js", "readme"])

        files = list(gm.get_project(project_id)["files"].keys())
        summary = (
            f"✅ Projeto gerado com sucesso!\n\n"
            f"📁 Arquivos criados ({len(files)}):\n"
        )
        for fname in files:
            summary += f"  • {fname}\n"
        summary += f"\n💡 Use /agente_exportar para salvar os arquivos na pasta projects\\"
        return summary

        gm.add_short(f"Iniciando projeto completo: {user_input}", source="orchestrator", importance=5)

        # Fase 1: Planejamento
        prog("Planejando estrutura do projeto...", "analisando requisitos")
        plan_prompt = (
            f"Crie um plano detalhado para: '{user_input}'\n"
            f"Inclua: nome do projeto, descrição, tecnologias, estrutura de arquivos, "
            f"lista de páginas/componentes, paleta de cores sugerida.\n"
            f"Seja específico e prático."
        )
        plan = await quick_prompt(plan_prompt, system=self.SYSTEM_PROMPT, max_tokens=1000)
        gm.update_project(project_id, "plan", plan)
        await asyncio.sleep(4)

        results = {"plan": plan}

        # Fase 2: Design (identidade visual)
        if "web" in self._teams and "design" in self._teams:
            prog("Agente de Design trabalhando...", "criando identidade visual e paleta de cores")
            design_task = AgentTask(
                content=f"Crie identidade visual completa para: {user_input}\nPlano: {plan[:500]}",
                context={"project_id": project_id, "project_context": plan[:300]},
            )
            design_result = await self._teams["design"].handle(design_task)
            results["design"] = design_result
            gm.add_project_file(project_id, "design_brief.md", design_result)
            await asyncio.sleep(4)

        # Fase 3: Conteúdo (textos)
        if "content" in self._teams:
            prog("Agente de Conteúdo trabalhando...", "criando textos, títulos e copy")
            content_task = AgentTask(
                content=f"Crie todos os textos e copies para: {user_input}\nPlano: {plan[:500]}",
                context={"project_id": project_id, "project_context": plan[:300]},
            )
            content_result = await self._teams["content"].handle(content_task)
            results["content"] = content_result
            gm.add_project_file(project_id, "content.md", content_result)
            await asyncio.sleep(4)

        # Fase 4: HTML
        if "web" in self._teams:
            ctx = f"Plano: {plan[:400]}\nDesign: {results.get('design','')[:300]}\nTextos: {results.get('content','')[:300]}"

            prog("Agente HTML trabalhando...", "estruturando páginas e componentes")
            html_task = AgentTask(
                content=f"Crie o HTML completo para: {user_input}",
                context={"project_id": project_id, "project_context": ctx},
            )
            html_result = await self._teams["web"]._agents.get("html", list(self._teams["web"]._agents.values())[0]).execute(html_task)
            results["html"] = html_result.content if isinstance(html_result, AgentResult) else str(html_result)
            gm.add_project_file(project_id, "index.html", results["html"])
            await asyncio.sleep(4)

            # CSS
            prog("Agente CSS trabalhando...", "estilizando layout, cores e responsividade")
            css_task = AgentTask(
                content=f"Crie o CSS completo para: {user_input}\nHTML: {results['html'][:500]}",
                context={"project_id": project_id, "project_context": ctx},
            )
            css_agent = self._teams["web"]._agents.get("css")
            if css_agent:
                css_result = await css_agent.execute(css_task)
                results["css"] = css_result.content
                gm.add_project_file(project_id, "assets/css/style.css", results["css"])
            await asyncio.sleep(4)

            # JavaScript
            prog("Agente JavaScript trabalhando...", "adicionando interatividade e animações")
            js_task = AgentTask(
                content=f"Crie o JavaScript para: {user_input}\nHTML: {results['html'][:300]}",
                context={"project_id": project_id, "project_context": ctx},
            )
            js_agent = self._teams["web"]._agents.get("javascript")
            if js_agent:
                js_result = await js_agent.execute(js_task)
                results["js"] = js_result.content
                gm.add_project_file(project_id, "assets/js/main.js", results["js"])
            await asyncio.sleep(4)

        # Fase 5: QA
        if "qa" in self._teams:
            prog("Agente QA revisando...", "verificando qualidade e corrigindo erros")
            qa_task = AgentTask(
                content=f"Revise e valide tudo gerado para: {user_input}",
                context={"project_id": project_id, "project_context": str(list(results.keys()))},
            )
            qa_result = await self._teams["qa"].handle(qa_task)
            results["qa"] = qa_result
            gm.add_project_file(project_id, "QA_REPORT.md", qa_result)
            await asyncio.sleep(4)

        # README
        prog("Gerando documentação...", "criando README.md")
        readme = await quick_prompt(
            f"Crie um README.md profissional para o projeto: {user_input}\n"
            f"Inclua: descrição, tecnologias, estrutura de pastas, como rodar.",
            max_tokens=800,
        )
        gm.add_project_file(project_id, "README.md", readme)
        results["readme"] = readme

        # Finalizado
        self._progress(TOTAL_STEPS, TOTAL_STEPS, "Projeto concluído! ✅")
        print()  # nova linha após barra

        gm.update_project(project_id, "status", "completed")
        gm.update_project(project_id, "results", list(results.keys()))

        # Sumário final
        files = gm.get_project(project_id)["files"]
        summary = (
            f"✅ Projeto '{user_input}' gerado com sucesso!\n\n"
            f"📁 Arquivos criados ({len(files)}):\n"
        )
        for fname in files:
            summary += f"  • {fname}\n"
        summary += f"\n📋 Etapas concluídas: {', '.join(results.keys())}\n"
        summary += "\nUse /agente_projeto para ver detalhes ou exportar os arquivos."
        return summary

    # ── Processamento principal ────────────────────────────────────
    async def process(self, user_input: str) -> str:
        self._lazy_init()
        start = time.time()
        orch_task = OrchestratorTask(user_input=user_input)

        gm.add_short(f"Usuário: {user_input}", source="user", importance=2)

        # Analisar intenção
        intent, teams = await self._analyze_intent(user_input)
        orch_task.intent = intent
        orch_task.teams  = teams

        # Verificar se é projeto completo
        lower = user_input.lower()
        is_full = any(kw in lower for kw in FULL_PROJECT_KEYWORDS)

        if is_full:
            self._project_counter += 1
            project_id = f"proj_{self._project_counter:03d}"
            gm.start_project(project_id, user_input[:50], user_input)
            orch_task.project_id = project_id
            result = await self._run_full_project(user_input, project_id)
        elif len(teams) == 1:
            # Um time apenas
            print(f"\n  {'─'*54}")
            print(f"  🎯 Tarefa : {user_input[:60]}")
            print(f"  🤖 Agente : {teams[0].upper()}")
            print(f"  {'─'*54}\n")
            self._progress(1, 2, f"Agente [{teams[0].upper()}] processando...", user_input[:50])
            team_task = AgentTask(
                content=user_input,
                context={"project_context": gm.build_context_string()},
            )
            result = await self._teams[teams[0]].handle(team_task)
            self._progress(2, 2, "Concluído ✅")
            print()
        else:
            # Múltiplos times — planejar e executar em paralelo
            plan = await self._plan(user_input, teams)
            team_tasks = []
            for team_name, subtask in plan.items():
                if team_name in self._teams:
                    t = AgentTask(
                        content=subtask,
                        context={"project_context": gm.build_context_string()},
                    )
                    team_tasks.append((team_name, t))

            total_teams = len(team_tasks)
            print(f"\n  {'─'*54}")
            print(f"  🎯 Tarefa : {user_input[:60]}")
            print(f"  🤖 Times  : {', '.join(tn for tn, _ in team_tasks)}")
            print(f"  {'─'*54}\n")

            team_results_list = []
            for i, (tn, t) in enumerate(team_tasks, 1):
                self._progress(i, total_teams + 1, f"Agente [{tn.upper()}] trabalhando...", t.content[:50])
                try:
                    res = await self._teams[tn].handle(t)
                    team_results_list.append((tn, t, res))
                    await asyncio.sleep(4)
                except Exception as exc:
                    team_results_list.append((tn, t, str(exc)))

            self._progress(total_teams + 1, total_teams + 1, "Concluído ✅")
            print()

            combined = []
            for (tn, _, res) in team_results_list:
                if isinstance(res, str):
                    combined.append(f"[{tn.upper()}]\n{res}")
                    orch_task.results[tn] = res
            result = "\n\n".join(combined)

            # Consolidar com IA
            if len(combined) > 1:
                result = await quick_prompt(
                    f"Solicitação original: '{user_input}'\n\nResultados:\n{result}\n\n"
                    f"Consolide em resposta única coerente em português.",
                    system=self.SYSTEM_PROMPT,
                    max_tokens=3000,
                )

        orch_task.final_output = result
        orch_task.duration     = time.time() - start
        self._history.append(orch_task)
        gm.add_short(f"Resposta gerada em {orch_task.duration:.1f}s", source="orchestrator", importance=1)

        return result

    # ── Status e informações ───────────────────────────────────────
    def get_status(self) -> Dict:
        self._lazy_init()
        total_agents = sum(len(t.list_agents()) for t in self._teams.values())
        return {
            "teams":        len(self._teams),
            "total_agents": total_agents,
            "tasks_done":   len(self._history),
            "projects":     len(gm.list_projects()),
            "teams_detail": {
                name: {"agents": leader.list_agents(), "description": leader.description}
                for name, leader in self._teams.items()
            },
        }

    def get_history(self, n: int = 10) -> List[Dict]:
        return [
            {
                "id":      t.request_id,
                "input":   t.user_input[:80],
                "intent":  t.intent,
                "teams":   t.teams,
                "time":    f"{t.duration:.1f}s",
                "project": t.project_id,
            }
            for t in self._history[-n:]
        ]


# Instância global
orchestrator = OrchestratorAgent()
