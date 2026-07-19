# -*- coding: utf-8 -*-
"""
model_selector.py — Seleção automática e centralizada de modelo de IA.
────────────────────────────────────────────────────────────────────────
Responsável por decidir, a cada mensagem do usuário, se a Nox deve usar:

  • O modelo padrão configurado (.env / config.json)              -> conversas normais
  • O DeepSeek Coder V2 (modo "NOX AI Developer Edition")          -> tarefas de
    criação/desenvolvimento de sites, landing pages, dashboards,
    sistemas web, SaaS, apps React/Next.js, frontend/backend, etc.

Este módulo é a ÚNICA fonte de verdade para essa decisão — nenhuma outra
parte do sistema deve duplicar a lógica de detecção de palavras-chave.
Basta chamar `select_model(mensagem, config)` e usar o resultado.

Não requer nenhuma configuração manual do usuário: a troca é 100%
automática e silenciosa (apenas logada no terminal).
"""

import re
from dataclasses import dataclass
from typing import Optional


# ════════════════════════════════════════════════════════════════
#  IDENTIDADE DO MODELO DE DESENVOLVIMENTO
# ════════════════════════════════════════════════════════════════

DEV_MODEL_NAME  = "__agents__"      # sentinela: roteamento para orchestrator interno
DEV_MODEL_LABEL = "NOX Multiagente"

# Prompt de sistema exclusivo para quando a Nox assume o papel de
# "NOX AI Developer Edition" (acionado automaticamente).
DEV_SYSTEM_PROMPT = """Você é NOX AI Developer Edition.

Especialista em:
- HTML
- CSS
- JavaScript
- React
- Next.js
- Python
- Node.js
- APIs
- Bancos de dados
- Flutter

Sempre entregue projetos completos.
Nunca entregue código incompleto.
Sempre utilize design moderno estilo SaaS.
Sempre gere arquivos completos.
Sempre gere código pronto para produção.
Sempre crie interfaces responsivas.
Sempre siga boas práticas de segurança e desempenho."""


# ════════════════════════════════════════════════════════════════
#  PALAVRAS-CHAVE DE DETECÇÃO
# ════════════════════════════════════════════════════════════════
# Cada entrada é tratada como uma expressão "solta" dentro do texto
# (case-insensitive, sem acento sensível). Cobrem PT-BR e termos
# técnicos universais usados mesmo em frases em português.

DEV_KEYWORDS = [
    # Pedidos diretos de criação de site
    "crie um site", "criar site", "criar um site", "desenvolver site",
    "desenvolver um site", "fazer um site", "fazer site", "construir site",
    "construir um site", "gerar site", "gerar um site", "programar site",
    "programar um site", "montar site", "montar um site",

    # Tipos de projeto / produto
    "landing page", "dashboard", "painel administrativo", "painel admin",
    "sistema web", "aplicação web", "aplicativo web", "app web", "webapp",
    "saas", "e-commerce", "ecommerce", "loja virtual", "site institucional",
    "portfólio online", "portfolio online", "blog", "página web",
    "pagina web", "página html", "pagina html",

    # Tecnologias / camadas
    "html", "css", "javascript", "typescript", "react", "react.js", "reactjs",
    "next.js", "nextjs", "vue", "vue.js", "angular", "node.js", "nodejs",
    "tailwind", "bootstrap", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full stack", "full-stack", "api rest", "rest api",
    "banco de dados", "flutter", "django", "flask", "express.js",

    # Verbos de criação combinados com "web"/"aplicação"
    "criar uma aplicação", "criar aplicação", "desenvolver uma aplicação",
    "desenvolver aplicação", "criar um app", "desenvolver um app",
]

# Pré-compila os padrões em uma única regex (mais eficiente para checar
# muitas frases em sequência, e evita problemas de substring acidental
# tratando os termos como blocos literais).
_PATTERN = re.compile(
    r"(" + "|".join(re.escape(k) for k in DEV_KEYWORDS) + r")",
    re.IGNORECASE,
)


# ════════════════════════════════════════════════════════════════
#  ETAPAS DO PIPELINE (exibidas ao usuário durante a geração)
# ════════════════════════════════════════════════════════════════
# Quando o modo Developer é ativado, a Nox mostra cada uma destas
# etapas no terminal antes/durante a geração, para deixar claro que
# o site está sendo construído e que o chat está ocupado até concluir.
# Isso é só feedback visual — a geração de verdade acontece em uma
# única chamada ao modelo (DEV_SYSTEM_PROMPT já exige entrega completa),
# mas o usuário acompanha o progresso etapa por etapa.

DEV_PIPELINE_STEPS = [
    "Analisando o pedido e definindo a estrutura do projeto...",
    "Planejando layout e componentes (HTML/JSX)...",
    "Gerando estilos e design responsivo (CSS/Tailwind)...",
    "Implementando interatividade e lógica (JavaScript)...",
    "Revisando boas práticas de segurança e performance...",
    "Montando os arquivos finais do projeto...",
]


def get_pipeline_steps() -> list[str]:
    """
    Retorna a lista de etapas a serem exibidas ao usuário enquanto o
    DeepSeek Coder V2 está gerando o site/app. Mantida centralizada
    aqui para que qualquer parte do sistema (CLI, bots, API) use a
    mesma sequência de etapas.
    """
    return list(DEV_PIPELINE_STEPS)


@dataclass
class ModelSelection:
    """Resultado da seleção automática de modelo."""
    model: str                 # Nome do modelo a ser usado na chamada de API
    system_prompt: Optional[str]  # Prompt de sistema a usar (None = manter o padrão da Nox)
    is_dev_mode: bool          # True quando a tarefa foi roteada para o DeepSeek Coder V2
    matched_keyword: Optional[str] = None  # Palavra-chave que disparou a troca (debug/log)
    pipeline_steps: Optional[list] = None  # Etapas a exibir (preenchido quando is_dev_mode=True)

    def __post_init__(self):
        if self.pipeline_steps is None:
            self.pipeline_steps = []


def is_dev_request(message: str) -> Optional[str]:
    """
    Verifica se a mensagem do usuário corresponde a um pedido de
    desenvolvimento web/app. Retorna a palavra-chave encontrada
    (ou None se nenhuma keyword bater).
    """
    if not message:
        return None
    match = _PATTERN.search(message)
    return match.group(1) if match else None


def select_model(
    user_message: str,
    default_model: str,
    dev_model: str = DEV_MODEL_NAME,
    log_fn=print,
) -> ModelSelection:
    """
    Função CENTRALIZADA de seleção automática de modelo.

    Esta é a função que todo o resto do sistema deve chamar — nunca
    duplicar a lógica de detecção em outro lugar.

    Parâmetros:
        user_message:   texto digitado pelo usuário nesta mensagem.
        default_model:  modelo padrão da Nox (vem da config/.env).
        dev_model:      modelo a usar quando a tarefa é de desenvolvimento
                         web/app (default: "deepseek-coder-v2"). Pode ser
                         sobrescrito via config/.env (NOX_MODEL_DEV) sem
                         alterar este módulo.
        log_fn:         função usada para logar a decisão (default: print).
                         Pode receber `self.print_nox` ou `self.print_system`
                         da Nox para integrar com o terminal estilizado.

    Retorna:
        ModelSelection com o modelo escolhido, o prompt de sistema a
        aplicar (ou None para manter o prompt padrão da Nox) e flags
        auxiliares.
    """
    keyword = is_dev_request(user_message)

    if keyword:
        log_fn(f"[NOX] Modelo selecionado: {DEV_MODEL_LABEL}")
        return ModelSelection(
            model=dev_model,
            system_prompt=DEV_SYSTEM_PROMPT,
            is_dev_mode=True,
            matched_keyword=keyword,
            pipeline_steps=get_pipeline_steps(),
        )

    log_fn(f"[NOX] Modelo selecionado: {default_model}")
    return ModelSelection(
        model=default_model,
        system_prompt=None,
        is_dev_mode=False,
        matched_keyword=None,
    )
