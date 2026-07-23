# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║      NOX AI — API Client (Multi-backend)     ║
║  Prioridade: Groq (NOX_API_KEY) → Ollama     ║
║              → Gemini → fallback informativo  ║
╚══════════════════════════════════════════════╝
"""

from __future__ import annotations
import asyncio
import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, List

# ── Carrega .env ──────────────────────────────────────────────────
def _load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    candidates = [
        ".env",
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
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
_API_KEY: str = ""            # pode ser sobrescrito por set_api_key()
_rate_calls: list = []
MAX_PER_MIN = 14


# ── API Key ────────────────────────────────────────────────────────
def set_api_key(key: str):
    global _API_KEY
    _API_KEY = key.strip()


def get_api_key() -> str:
    if _API_KEY:
        return _API_KEY
    # Prioridade: NOX_API_KEY → GEMINI_API_KEY
    return _ENV.get("NOX_API_KEY", "") or _ENV.get("GEMINI_API_KEY", "")


# ── Rate limiter simples ───────────────────────────────────────────
def _check_rate():
    global _rate_calls
    now = time.time()
    _rate_calls = [t for t in _rate_calls if now - t < 60]
    if len(_rate_calls) >= MAX_PER_MIN:
        wait = 62 - (now - _rate_calls[0])
        if wait > 0:
            time.sleep(wait)
        _rate_calls = []
    _rate_calls.append(time.time())


# ── Backend 1: Groq / OpenAI-compatible (NOX_API_KEY) ────────────
def _call_groq(messages: List[Dict], system: str, max_tokens: int, temperature: float, model: str) -> str | None:
    api_url = _ENV.get("NOX_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    api_key = _API_KEY or _ENV.get("NOX_API_KEY", "")
    api_model = model or _ENV.get("NOX_MODEL", "openai/gpt-oss-120b")

    if not api_url or not api_key or api_key in ("sua_chave_aqui", ""):
        return None

    all_msgs: List[Dict] = []
    if system:
        all_msgs.append({"role": "system", "content": system})
    all_msgs.extend(messages)

    payload = json.dumps({
        "model":       api_model,
        "messages":    all_msgs,
        "max_tokens":  min(max_tokens, 8000),
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        # 429 = rate limit — deixa cair para Ollama
        if e.code == 429:
            return None
        # outros erros do Groq → retorna mensagem de erro
        return f"[Erro Groq {e.code}] {body[:200]}"
    except Exception:
        return None


# ── Backend 2: Ollama local ────────────────────────────────────────
def _call_ollama(messages: List[Dict], system: str, max_tokens: int) -> str | None:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1) as r:
            available = [
                m["name"].split(":")[0]
                for m in json.loads(r.read()).get("models", [])
            ]
    except Exception:
        return None

    if not available:
        return None

    ollama_model = _ENV.get("OLLAMA_MODEL", "gemma2:2b").split(":")[0]
    if ollama_model not in available:
        ollama_model = available[0]

    all_msgs: List[Dict] = []
    if system:
        all_msgs.append({"role": "system", "content": system})
    all_msgs.extend(messages)

    payload = json.dumps({
        "model":   ollama_model,
        "messages": all_msgs,
        "stream":  False,
        "options": {"num_predict": min(max_tokens, 8192)},
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["message"]["content"].strip()
    except Exception:
        return None


# ── Backend 3: Google Gemini ───────────────────────────────────────
def _call_gemini(messages: List[Dict], system: str, max_tokens: int, temperature: float) -> str | None:
    gem_key = _ENV.get("GEMINI_API_KEY", "")
    if not gem_key or gem_key in ("COLE_SUA_CHAVE_AQUI", ""):
        return None

    try:
        import requests as _req
    except ImportError:
        return None

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    GEMINI_MODEL   = "gemini-2.0-flash"

    gemini_contents = []
    if system:
        gemini_contents.append({"role": "user",  "parts": [{"text": f"[Instruções]: {system}"}]})
        gemini_contents.append({"role": "model", "parts": [{"text": "Entendido."}]})
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "contents": gemini_contents,
        "generationConfig": {
            "maxOutputTokens": min(max_tokens, 8192),
            "temperature":     temperature,
        },
    }

    for attempt in range(3):
        try:
            resp = _req.post(
                GEMINI_API_URL.format(model=GEMINI_MODEL, key=gem_key),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if resp.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
    return None


# ── Chamada principal (síncrona) ───────────────────────────────────
def call_grok(
    messages:      List[Dict[str, str]],
    system:        str   = "",
    max_tokens:    int   = 8000,
    temperature:   float = 0.7,
    model:         str   = "",
    prefer_ollama: bool  = False,
) -> str:
    """
    Tenta os backends nesta ordem:
      Padrão:        1. Groq  2. Ollama local  3. Gemini  4. erro
      prefer_ollama: 1. Ollama local (DeepSeek Coder V2)  2. Groq  3. Gemini  4. erro

    prefer_ollama=True é usado pelo modo "NOX AI Developer Edition"
    (criação de sites/apps), para garantir que o DeepSeek Coder V2
    rodando localmente via Ollama seja usado antes de qualquer API
    online.
    """
    _check_rate()

    if prefer_ollama:
        # 1. Ollama local (DeepSeek Coder V2)
        result = _call_ollama(messages, system, max_tokens)
        if result is not None:
            return result

        # 2. Groq / OpenAI-compatible (fallback se Ollama não estiver rodando)
        result = _call_groq(messages, system, max_tokens, temperature, model)
        if result is not None:
            return result
    else:
        # 1. Groq / OpenAI-compatible
        result = _call_groq(messages, system, max_tokens, temperature, model)
        if result is not None:
            return result

        # 2. Ollama local
        result = _call_ollama(messages, system, max_tokens)
        if result is not None:
            return result

    # 3. Gemini
    result = _call_gemini(messages, system, max_tokens, temperature)
    if result is not None:
        return result

    # 4. Fallback informativo
    return (
        "[NOX AI] Nenhum backend de IA disponível. Verifique:\n"
        "  • Ollama rodando localmente (ollama serve) com deepseek-coder-v2 baixado\n"
        "  • NOX_API_KEY no .env (Groq)\n"
        "  • GEMINI_API_KEY no .env (Google)"
    )


# ── Chamada assíncrona ─────────────────────────────────────────────
async def call_grok_async(
    messages:      List[Dict[str, str]],
    system:        str   = "",
    max_tokens:    int   = 8000,
    temperature:   float = 0.7,
    prefer_ollama: bool  = False,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: call_grok(messages, system, max_tokens, temperature, prefer_ollama=prefer_ollama),
    )


# ── Helper rápido ──────────────────────────────────────────────────
async def quick_prompt(prompt: str, system: str = "", max_tokens: int = 4000, prefer_ollama: bool = False) -> str:
    return await call_grok_async(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
        prefer_ollama=prefer_ollama,
    )
