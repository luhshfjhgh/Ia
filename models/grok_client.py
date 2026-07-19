# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║      NOX AI — API Client (Google Gemini)     ║
║  Sistema multiagente usa Google AI Studio    ║
║  Plano gratuito: aistudio.google.com         ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import asyncio
import json
import os
import time
from typing import Dict, List

try:
    import requests
    REQUESTS_OK = True
except (ImportError, OSError, Exception):
    REQUESTS_OK = False
    requests = None

# ── Configuração ───────────────────────────────────────────────────
# URL da API do Google AI Studio (Gemini)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# Modelo padrão — gemini-2.0-flash é gratuito e muito capaz
GEMINI_MODEL = "gemini-2.0-flash"

# Compatibilidade com nomes antigos usados no restante do código
GROK_API_URL = GEMINI_API_URL
GROK_MODEL   = GEMINI_MODEL

_API_KEY: str = ""
_rate_calls   = []
MAX_PER_MIN   = 14  # limite gratuito do Gemini: 15 req/min


def _load_env() -> Dict[str, str]:
    """Carrega .env da raiz do projeto."""
    env: Dict[str, str] = {}
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

_ENV = _load_env()


def set_api_key(key: str):
    global _API_KEY
    _API_KEY = key.strip()


def get_api_key() -> str:
    if _API_KEY:
        return _API_KEY
    # 1) .env — chave GEMINI_API_KEY
    key = _ENV.get("GEMINI_API_KEY", "")
    if key:
        return key
    # 2) config.json
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("gemini_api_key", "")
        if key:
            return key
    except Exception:
        pass
    # 3) variável de ambiente do sistema
    return os.getenv("GEMINI_API_KEY", "")


# ── Rate limiter ───────────────────────────────────────────────────
def _check_rate():
    global _rate_calls
    now = time.time()
    _rate_calls = [t for t in _rate_calls if now - t < 60]
    if len(_rate_calls) >= MAX_PER_MIN:
        wait = 60 - (now - _rate_calls[0]) + 1
        time.sleep(wait)
        _rate_calls = []
    _rate_calls.append(time.time())


# ── Chamada síncrona ───────────────────────────────────────────────
def call_grok(
    messages:    List[Dict[str, str]],
    system:      str   = "",
    max_tokens:  int   = 8000,
    temperature: float = 0.7,
    model:       str   = "",
) -> str:
    if not REQUESTS_OK:
        return "[Erro] requests não instalado. Execute: pip install requests"

    key = get_api_key()
    if not key:
        return (
            "[Erro] Chave Gemini não configurada!\n"
            "  1. Acesse: https://aistudio.google.com/app/apikey\n"
            "  2. Clique em 'Create API key'\n"
            "  3. Abra o arquivo .env e adicione a linha:\n"
            "     GEMINI_API_KEY=AIzaSy...suachaveaqui"
        )

    _check_rate()

    use_model = model or GEMINI_MODEL

    # Monta o histórico no formato Gemini (role: user/model)
    gemini_contents = []
    if system:
        # Gemini não tem "system" direto no v1beta — injeta como primeiro turno
        gemini_contents.append({
            "role": "user",
            "parts": [{"text": f"[Instruções do sistema]: {system}"}]
        })
        gemini_contents.append({
            "role": "model",
            "parts": [{"text": "Entendido. Seguirei essas instruções."}]
        })

    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    payload = {
        "contents": gemini_contents,
        "generationConfig": {
            "maxOutputTokens": min(max_tokens, 8192),
            "temperature":     temperature,
        }
    }

    url = GEMINI_API_URL.format(model=use_model, key=key)

    for attempt in range(4):
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                status = e.response.status_code
                if status == 429:
                    wait = 15 * (attempt + 1)
                    time.sleep(wait)
                    continue
                if status == 400:
                    try:
                        msg = e.response.json().get("error", {}).get("message", str(e))
                    except Exception:
                        msg = e.response.text[:300]
                    return f"[Erro 400] {msg}"
                if status == 403:
                    return "[Erro 403] Chave inválida ou sem permissão. Verifique GEMINI_API_KEY no .env"
                return f"[Erro HTTP {status}] {e}"
            return f"[Erro HTTP] {e}"
        except Exception as e:
            return f"[Erro Gemini] {e}"

    return "[Erro 429] Limite do plano gratuito atingido. Aguarde 1 minuto e tente novamente."


# ── Chamada assíncrona ─────────────────────────────────────────────
async def call_grok_async(
    messages:    List[Dict[str, str]],
    system:      str   = "",
    max_tokens:  int   = 8000,
    temperature: float = 0.7,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: call_grok(messages, system, max_tokens, temperature),
    )


# ── Helper rápido ──────────────────────────────────────────────────
async def quick_prompt(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    return await call_grok_async(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
    )
