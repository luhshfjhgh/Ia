# -*- coding: utf-8 -*-
"""
ollama_client.py — Integração Ollama local para Nox AI v3.1
────────────────────────────────────────────────────────────
• Roda modelos LLM 100% offline via Ollama
• Detecta automaticamente se Ollama está rodando
• Baixa o modelo automaticamente na primeira vez
• Recomendado para PC fraco: gemma2:2b
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from typing import Generator

OLLAMA_URL   = "http://localhost:11434"
DEFAULT_MODEL = "gemma2:2b"


def is_ollama_running() -> bool:
    """Verifica se o Ollama está rodando localmente."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def is_model_available(model: str = DEFAULT_MODEL) -> bool:
    """Verifica se o modelo já foi baixado."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return any(model.split(":")[0] in m for m in models)
    except Exception:
        return False


def pull_model(model: str = DEFAULT_MODEL, print_fn=print) -> bool:
    """Baixa o modelo se ainda não estiver disponível."""
    if is_model_available(model):
        return True
    print_fn(f"📥 Baixando modelo {model}... (pode demorar na primeira vez)")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/pull",
        data=json.dumps({"name": model}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            while True:
                line = r.readline()
                if not line:
                    break
                try:
                    d = json.loads(line)
                    status = d.get("status", "")
                    if "pulling" in status or "downloading" in status:
                        total     = d.get("total", 0)
                        completed = d.get("completed", 0)
                        if total > 0:
                            pct = int(completed / total * 100)
                            print(f"\r  {pct}% baixado... ", end="", flush=True)
                    elif d.get("status") == "success":
                        print()
                        print_fn(f"✅ Modelo {model} pronto!")
                        return True
                except Exception:
                    pass
    except Exception as e:
        print_fn(f"❌ Erro ao baixar modelo: {e}")
        return False
    return True


def start_ollama() -> bool:
    """Tenta iniciar o Ollama em background."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        import time
        for _ in range(10):
            time.sleep(1)
            if is_ollama_running():
                return True
        return False
    except FileNotFoundError:
        return False  # Ollama não instalado


def is_ollama_installed() -> bool:
    """Verifica se o Ollama está instalado no sistema."""
    try:
        subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            timeout=3,
        )
        return True
    except (FileNotFoundError, Exception):
        return False


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.85,
    max_tokens: int = 1024,
) -> str:
    """
    Envia mensagens para o Ollama e retorna a resposta.
    messages: lista no formato [{"role": "user/assistant/system", "content": "..."}]
    """
    payload = {
        "model":   model,
        "messages": messages,
        "stream":  False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama não acessível: {e}")
    except Exception as e:
        raise RuntimeError(f"Erro Ollama: {e}")


def ensure_ready(model: str = DEFAULT_MODEL, print_fn=print) -> tuple[bool, str]:
    """
    Garante que o Ollama está pronto para uso.
    Retorna (sucesso, mensagem).
    """
    if not is_ollama_installed():
        return False, (
            "Ollama não está instalado.\n"
            "  Instale em: https://ollama.com/download\n"
            "  Depois rode: ollama pull " + model
        )

    if not is_ollama_running():
        print_fn("⚡ Iniciando Ollama...")
        if not start_ollama():
            return False, "Não foi possível iniciar o Ollama."

    if not is_model_available(model):
        ok = pull_model(model, print_fn)
        if not ok:
            return False, f"Não foi possível baixar o modelo {model}."

    return True, f"Ollama pronto com {model}."
