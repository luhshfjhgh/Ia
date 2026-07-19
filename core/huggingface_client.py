# -*- coding: utf-8 -*-
"""
core/huggingface_client.py — Modelo de programação via Hugging Face
────────────────────────────────────────────────────────────────────
Usa o endpoint oficial "router" da Hugging Face (compatível com a API
da OpenAI) para rodar um modelo especializado em código quando a NOX
está em modo Developer.

Requer apenas 2 variáveis no .env:
    HF_TOKEN=hf_xxx...........................
    HF_CODE_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct   (opcional, já tem padrão)

Como conseguir o token: https://huggingface.co/settings/tokens
(crie um token do tipo "Read" ou "Fine-grained" com a permissão
"Make calls to Inference Providers" habilitada).

Não usa nenhuma biblioteca nova — só "requests", que já é dependência
do projeto.
"""

from __future__ import annotations
import os
import requests
from typing import List, Dict

ROUTER_URL   = "https://router.huggingface.co/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"


def _load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    candidates = [
        ".env",
        os.path.join(os.path.dirname(__file__), "..", ".env"),
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
        except FileNotFoundError:
            pass
    return env


_ENV = _load_env()


def is_configured() -> bool:
    """True se HF_TOKEN estiver preenchido no .env."""
    token = os.environ.get("HF_TOKEN") or _ENV.get("HF_TOKEN", "")
    return bool(token) and token not in ("", "sua_chave_aqui", "hf_xxx")


def get_model_name() -> str:
    return os.environ.get("HF_CODE_MODEL") or _ENV.get("HF_CODE_MODEL", DEFAULT_MODEL)


def chat(
    messages: List[Dict[str, str]],
    model: str | None = None,
    max_tokens: int = 3000,
    temperature: float = 0.2,
    timeout: int = 90,
) -> str:
    """
    Envia uma conversa (lista de {"role": ..., "content": ...}) para o
    modelo de código da Hugging Face e devolve o texto da resposta.
    Levanta ConnectionError em caso de falha (chamador deve tratar).
    """
    token = os.environ.get("HF_TOKEN") or _ENV.get("HF_TOKEN", "")
    if not token:
        raise ConnectionError(
            "HF_TOKEN não configurado no .env. Crie um token em "
            "https://huggingface.co/settings/tokens e adicione ao .env."
        )

    payload = {
        "model": model or get_model_name(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(ROUTER_URL, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        try:
            err = resp.json().get("error", resp.text)
        except Exception:
            err = resp.text
        raise ConnectionError(f"Hugging Face (erro {resp.status_code}): {err}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
