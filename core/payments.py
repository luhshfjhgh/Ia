# -*- coding: utf-8 -*-
"""
core/payments.py — Sistema de Planos Premium (Pix)
────────────────────────────────────────────────────────────────────
Planos Free / Básico / Pro, tela de pagamento via Pix, e análise
automática (best-effort) de comprovantes anexados.

IMPORTANTE sobre a "análise automática": comprovantes de Pix têm
formatos MUITO diferentes entre bancos, então a extração de campos
aqui é heurística (baseada em padrões de texto comuns) — funciona bem
na maioria dos casos, mas não é garantida. Por isso todo comprovante
enviado fica com status "aguardando_confirmacao": um admin sempre
revisa e confirma manualmente (/confirmar_pagamento) antes do plano
virar ativo de verdade. Isso evita liberar um plano pago por engano
com base só numa leitura automática que pode errar.
"""

from __future__ import annotations
import os
import re
import sys

import supabase_client as sb

PIX_KEY = "059.022.980-08"


def _get_env(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    for path in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith(f"{key}="):
                        return line.strip().split("=", 1)[1]
        except FileNotFoundError:
            pass
    return default


PRO_PRICE_LABEL = _get_env("NOX_PRO_PRICE_LABEL", "R$ 29,90/mês")

PLANS = {
    "free": {
        "nome": "Free",
        "preco_label": "Grátis",
        "beneficios": ["Acesso limitado", "Quantidade reduzida de mensagens/dia", "Sem recursos Premium"],
        "mensagens_dia": 20,
        "premium": False,
    },
    "basic": {
        "nome": "Básico",
        "preco_label": "R$ 0,96/mês",
        "beneficios": ["Mais mensagens por dia", "Recursos Premium básicos", "Suporte prioritário"],
        "mensagens_dia": 500,
        "premium": True,
    },
    "pro": {
        "nome": "Pro",
        "preco_label": PRO_PRICE_LABEL,
        "beneficios": ["Mensagens ilimitadas", "Todos os recursos Premium", "Suporte prioritário máximo"],
        "mensagens_dia": None,  # ilimitado
        "premium": True,
    },
}


# ── Extração de campos do comprovante (best-effort) ───────────────────
def _extract_text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    text = ""

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader  # fallback em versões mais antigas
            except ImportError:
                return ""
        try:
            reader = PdfReader(path)
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            text = ""

    elif ext in (".png", ".jpg", ".jpeg"):
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path), lang="por+eng")
        except Exception:
            text = ""  # OCR indisponível — comprovante fica salvo pra revisão manual

    return text or ""


def _find(patterns: list[str], text: str) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return None


def extract_receipt_fields(path: str) -> dict:
    text = _extract_text_from_file(path)
    fields = {
        "valor":          _find([r"r\$\s*([\d.]{1,10},\d{2})"], text),
        "data_pagamento": _find([r"(\d{2}/\d{2}/\d{4})"], text),
        "hora_pagamento": _find([r"(\d{2}:\d{2}:\d{2})", r"(\d{2}:\d{2})"], text),
        "nome_destino":   _find([r"(?:favorecido|destinat[áa]rio|recebedor|nome)\s*:?\s*([A-ZÀ-Ú][^\n\r]{2,60})"], text),
        "banco":          _find([r"banco\s*:?\s*([^\n\r]{2,40})"], text),
        "chave_pix":      _find([r"chave\s*pix\s*:?\s*([^\n\r]{2,60})"], text),
        "e2e_txid":       _find([r"(?:e2e|txid|identificador)\s*:?\s*([A-Za-z0-9]{10,40})"], text),
        "texto_bruto":    text[:4000] if text else None,
    }
    return fields


# ── Fluxo de assinatura ───────────────────────────────────────────────
def start_subscription(user_id: str, username: str, plan_key: str) -> tuple[bool, str]:
    if plan_key == "free":
        if sb.is_configured():
            try:
                sb.set_user_plan(user_id, "free", "ativo")
                sb.log_event(user_id, username, "plan_changed", "plano=free")
            except Exception as e:
                return False, f"Erro ao mudar de plano: {e}"
        return True, "Plano Free ativado."
    if plan_key not in ("basic", "pro"):
        return False, "Plano inválido."
    return True, (
        f"Pra assinar o plano {PLANS[plan_key]['nome']}, pague via Pix na chave "
        f"{PIX_KEY} e envie o comprovante com /anexar <arquivo>."
    )


def attach_receipt(user_id: str, username: str, plan_key: str, file_path: str) -> tuple[bool, str]:
    if not os.path.exists(file_path):
        return False, f"Arquivo não encontrado: {file_path}"
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".pdf"):
        return False, "Formato não aceito. Envie .png, .jpg, .jpeg ou .pdf."
    if plan_key not in ("basic", "pro"):
        return False, "Escolha um plano pago (basic ou pro) antes de anexar o comprovante."

    fields = extract_receipt_fields(file_path)
    payload = {
        "user_id": user_id,
        "username": username,
        "plan": plan_key,
        "file_name": os.path.basename(file_path),
        "status": "aguardando_confirmacao",
        **fields,
    }

    if not sb.is_configured():
        return False, "Supabase não configurado — não dá pra registrar o comprovante na nuvem."

    try:
        sb.create_payment_receipt(payload)
        sb.set_user_plan(user_id, plan_key, "aguardando_confirmacao")
        sb.log_event(user_id, username, "receipt_attached", f"plano={plan_key}; arquivo={payload['file_name']}")
    except Exception as e:
        return False, f"Erro ao registrar comprovante: {e}"

    resumo = []
    for label, key in (("Valor", "valor"), ("Data", "data_pagamento"), ("Hora", "hora_pagamento"),
                        ("Destinatário", "nome_destino"), ("Banco", "banco"),
                        ("Chave Pix", "chave_pix"), ("E2E/TXID", "e2e_txid")):
        v = fields.get(key)
        resumo.append(f"  {label}: {v if v else '(não identificado — revisão manual)'}")

    return True, (
        "📎 Comprovante recebido! Status: **aguardando confirmação**.\n"
        + "\n".join(resumo)
        + "\n\nUm admin vai revisar e confirmar em breve."
    )


def get_status(user_id: str) -> str:
    if not sb.is_configured():
        return "Supabase não configurado."
    try:
        user = sb.get_user_by_id(user_id)
        if not user:
            return "Conta não encontrada."
        plan = user.get("plan", "free")
        status = user.get("plan_status", "ativo")
        nome_plano = PLANS.get(plan, {}).get("nome", plan)
        status_label = {
            "ativo": "✅ Ativo",
            "aguardando_confirmacao": "⏳ Aguardando confirmação",
            "rejeitado": "❌ Rejeitado (pagamento não confirmado)",
        }.get(status, status)
        return f"Plano atual: {nome_plano}\nStatus: {status_label}"
    except Exception as e:
        return f"Erro ao consultar status: {e}"


# ── Confirmação (admin) ───────────────────────────────────────────────
def confirm_latest_receipt(target_username: str, approve: bool, reviewer: str) -> tuple[bool, str]:
    if not sb.is_configured():
        return False, "Supabase não configurado."
    try:
        user = sb.get_user_by_username(target_username)
        if not user:
            return False, "Usuário não encontrado."
        receipt = sb.get_latest_receipt(user["id"])
        if not receipt or receipt.get("status") != "aguardando_confirmacao":
            return False, "Não há comprovante pendente para esse usuário."

        novo_status = "confirmado" if approve else "rejeitado"
        sb.update_receipt(receipt["id"], {
            "status": novo_status, "reviewed_by": reviewer,
            "reviewed_at": __import__("datetime").datetime.now().isoformat(),
        })
        plano = receipt["plan"] if approve else "free"
        plano_status = "ativo" if approve else "rejeitado"
        sb.set_user_plan(user["id"], plano, plano_status)
        sb.log_event(user["id"], target_username, "payment_reviewed", f"aprovado={approve}; por={reviewer}")
        return True, f"Comprovante {'confirmado' if approve else 'rejeitado'} para '{target_username}'."
    except Exception as e:
        return False, f"Erro: {e}"


def list_pending() -> list[dict]:
    if not sb.is_configured():
        return []
    try:
        return sb.list_pending_receipts()
    except Exception:
        return []
