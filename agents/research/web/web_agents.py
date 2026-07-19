# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║         NOX AI — Web Team Agents             ║
║  HTML · CSS · JS · React · NextJS · Vue ...  ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import sys, os
# Aponta para a raiz do projeto (agents/research/web → ../../..)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.base_agent  import BaseAgent, AgentTask, Priority
from core.grok_client import call_grok_async


# ── Classe base para Web ───────────────────────────────────────────
class WebAgent(BaseAgent):
    async def _run(self, task: AgentTask) -> str:
        ctx = task.context.get("project_context", "")
        messages = []
        for m in self.memory[-6:]:
            messages.append(m)
        messages.append({"role": "user", "content": f"{ctx}\n\n{task.content}" if ctx else task.content})
        result = await call_grok_async(messages, system=self.system_prompt, max_tokens=self.max_tokens)
        self.remember("user",      task.content)
        self.remember("assistant", result)
        return result


# ═══════════════════════════════════════════════
#  AGENTES INDIVIDUAIS
# ═══════════════════════════════════════════════

class HTMLAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é um especialista em HTML5 semântico. Gere código HTML limpo, acessível e bem estruturado. "
            "Use tags semânticas (header, main, section, article, footer). Sempre inclua meta tags essenciais, "
            "viewport, charset e lang='pt-BR'. Gere código completo e pronto para uso."
        )
    def __init__(self): super().__init__("HTMLAgent", "HTML5 Semântico", "web", Priority.NORMAL, 3000)


class CSSAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é um especialista em CSS3 moderno. Crie estilos profissionais, responsivos e animados. "
            "Use variáveis CSS (--custom-properties), Flexbox, Grid, e media queries. "
            "Gere CSS organizado com comentários por seção. Priorize mobile-first. "
            "Inclua hover states, transições suaves e design system consistente."
        )
    def __init__(self): super().__init__("CSSAgent", "CSS3 & Design", "web", Priority.NORMAL, 3000)


class JavaScriptAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é um especialista em JavaScript ES2023+. Escreva código moderno, funcional e sem dependências "
            "externas desnecessárias. Use async/await, destructuring, módulos ES. "
            "Adicione comentários JSDoc. Valide inputs, trate erros graciosamente."
        )
    def __init__(self): super().__init__("JavaScriptAgent", "JavaScript ES2023", "web", Priority.NORMAL, 3000)


class TypeScriptAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em TypeScript com tipagem estrita. Defina interfaces, types e enums claros. "
            "Use generics onde aplicável. Escreva código tipado, seguro e escalável."
        )
    def __init__(self): super().__init__("TypeScriptAgent", "TypeScript", "web", Priority.NORMAL, 3000)


class ReactAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em React 18+ com hooks. Crie componentes funcionais reutilizáveis, "
            "use useState, useEffect, useCallback, useMemo corretamente. "
            "Escreva código limpo com PropTypes ou TypeScript. Otimize re-renders."
        )
    def __init__(self): super().__init__("ReactAgent", "React 18", "web", Priority.HIGH, 3000)


class NextJSAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em Next.js 14+ com App Router. Crie páginas com SSR, SSG e ISR. "
            "Use Server Components, Client Components corretamente. Implemente metadata, loading states, "
            "error boundaries. Otimize para SEO e performance."
        )
    def __init__(self): super().__init__("NextJSAgent", "Next.js 14", "web", Priority.HIGH, 3000)


class VueAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em Vue.js 3 com Composition API. Crie componentes com <script setup>, "
            "use ref, reactive, computed, watch. Implemente Pinia para estado global."
        )
    def __init__(self): super().__init__("VueAgent", "Vue.js 3", "web", Priority.NORMAL, 3000)


class TailwindAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em Tailwind CSS. Use utility classes de forma inteligente. "
            "Crie designs responsivos com prefixos sm:, md:, lg:, xl:. Use dark: para dark mode. "
            "Combine classes de forma eficiente. Prefira componentes reutilizáveis com @apply quando necessário."
        )
    def __init__(self): super().__init__("TailwindAgent", "Tailwind CSS", "web", Priority.NORMAL, 2000)


class BootstrapAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em Bootstrap 5. Use o grid system, componentes e utilities do Bootstrap. "
            "Crie layouts responsivos com breakpoints corretos. Use componentes nativos: navbar, cards, modals, forms."
        )
    def __init__(self): super().__init__("BootstrapAgent", "Bootstrap 5", "web", Priority.NORMAL, 2000)


class LandingPageAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em Landing Pages de alta conversão. Crie páginas com: "
            "hero section impactante, proposta de valor clara, prova social, benefícios, CTA poderoso, FAQ. "
            "Aplique princípios de copywriting e UX para maximizar conversões. "
            "Gere HTML + CSS + JS completo em um único arquivo auto-contido."
        )
    def __init__(self): super().__init__("LandingPageAgent", "Landing Pages", "web", Priority.HIGH, 4000)


class EcommerceAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em e-commerce. Crie lojas virtuais completas com: "
            "catálogo de produtos, carrinho, checkout, páginas de produto, filtros, busca. "
            "Implemente UX otimizada para conversão de vendas."
        )
    def __init__(self): super().__init__("EcommerceAgent", "E-commerce", "web", Priority.HIGH, 4000)


class BlogAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em blogs e plataformas de conteúdo. Crie templates de blog com: "
            "listagem de posts, página de post individual, categorias, tags, busca, sidebar, autor. "
            "Otimize para leitura e SEO."
        )
    def __init__(self): super().__init__("BlogAgent", "Blog & CMS", "web", Priority.NORMAL, 3000)


class EducationAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em plataformas EAD. Crie interfaces para: "
            "página de cursos, aula em vídeo, progresso do aluno, quizzes, certificados, "
            "painel do aluno, área de membros. Foque em engajamento e aprendizado."
        )
    def __init__(self): super().__init__("EducationAgent", "EAD & Educação", "web", Priority.HIGH, 4000)


class SaaSAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em produtos SaaS. Crie: landing pages de SaaS com pricing, "
            "dashboard administrativo, onboarding, settings, billing, analytics. "
            "Aplique padrões de design de produtos SaaS modernos como Vercel, Linear, Notion."
        )
    def __init__(self): super().__init__("SaaSAgent", "SaaS Products", "web", Priority.HIGH, 4000)


class PortfolioAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em portfólios profissionais. Crie portfólios para: "
            "devs, designers, fotógrafos, agências. Inclua: hero, sobre, habilidades, projetos, contato. "
            "Design criativo e memorável que impressiona recrutadores."
        )
    def __init__(self): super().__init__("PortfolioAgent", "Portfolio", "web", Priority.NORMAL, 3000)


class SEOAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em SEO técnico e on-page. Otimize: meta tags, Open Graph, Schema.org, "
            "sitemap.xml, robots.txt, Core Web Vitals, structured data, canonical URLs, hreflang. "
            "Analise e corrija problemas de SEO em código HTML."
        )
    def __init__(self): super().__init__("SEOAgent", "SEO Técnico", "web", Priority.NORMAL, 2000)


class AccessibilityAgent(WebAgent):
    @property
    def system_prompt(self) -> str:
        return (
            "Você é especialista em acessibilidade web (WCAG 2.1 AA). Garanta: "
            "alt text em imagens, labels em formulários, roles ARIA, contraste de cores adequado, "
            "navegação por teclado, skip navigation, foco visível. Revise e corrija código para acessibilidade."
        )
    def __init__(self): super().__init__("AccessibilityAgent", "Acessibilidade", "web", Priority.NORMAL, 2000)


# ── Registro do time ───────────────────────────────────────────────
WEB_AGENTS = {
    "html":          HTMLAgent,
    "css":           CSSAgent,
    "javascript":    JavaScriptAgent,
    "typescript":    TypeScriptAgent,
    "react":         ReactAgent,
    "nextjs":        NextJSAgent,
    "vue":           VueAgent,
    "tailwind":      TailwindAgent,
    "bootstrap":     BootstrapAgent,
    "landingpage":   LandingPageAgent,
    "ecommerce":     EcommerceAgent,
    "blog":          BlogAgent,
    "education":     EducationAgent,
    "saas":          SaaSAgent,
    "portfolio":     PortfolioAgent,
    "seo":           SEOAgent,
    "accessibility": AccessibilityAgent,
}
