# -*- coding: utf-8 -*-
"""
local_llm.py — Motor LLM local para Nox AI v3.1
─────────────────────────────────────────────────
• Usa llama-cpp-python para rodar .gguf direto no Python
• Sem Ollama, sem instalação externa — só pip install
• Modelo fica em nox_v3/models/
• Recomendado: gemma-2-2b-it-Q4_K_M.gguf (~1.6GB)
"""

import os, sys, json
from pathlib import Path

MODELS_DIR   = Path(__file__).parent / "models"
# Modelo padrão — usuário coloca este arquivo em nox_v3/models/
DEFAULT_MODEL = "gemma-2-2b-it-Q4_K_M.gguf"
MODEL_URL     = "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf"

_llm_instance = None   # singleton — carrega só uma vez

# ── Instalação automática do llama-cpp-python ─────────────────
def _ensure_llama_cpp():
    try:
        import llama_cpp
        return True
    except (ImportError, OSError, Exception):
        print("  📦 Instalando llama-cpp-python (só na primeira vez)...")
        ret = os.system(
            f'"{sys.executable}" -m pip install llama-cpp-python '
            f'--break-system-packages -q '
            f'--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu'
        )
        try:
            import llama_cpp
            return True
        except (ImportError, OSError, Exception):
            return False

# ── Verificação / download do modelo ─────────────────────────
def get_model_path(model_name: str = DEFAULT_MODEL) -> Path | None:
    """Retorna o caminho do modelo se existir."""
    MODELS_DIR.mkdir(exist_ok=True)
    path = MODELS_DIR / model_name
    return path if path.exists() else None


def list_available_models() -> list[str]:
    """Lista todos os .gguf disponíveis em models/."""
    MODELS_DIR.mkdir(exist_ok=True)
    return [f.name for f in MODELS_DIR.glob("*.gguf")]


def download_model(model_name: str = DEFAULT_MODEL, print_fn=print) -> bool:
    """Baixa o modelo do HuggingFace se não existir."""
    path = MODELS_DIR / model_name
    if path.exists():
        return True

    MODELS_DIR.mkdir(exist_ok=True)
    print_fn(f"📥 Baixando {model_name} (~1.6GB)...")
    print_fn(f"   Fonte: {MODEL_URL}")
    print_fn("   Isso pode demorar alguns minutos na primeira vez.")

    try:
        import urllib.request

        def _progress(count, block, total):
            if total > 0:
                pct = min(int(count * block / total * 100), 100)
                mb  = count * block / 1024 / 1024
                print(f"\r  {pct}% ({mb:.1f} MB)... ", end="", flush=True)

        urllib.request.urlretrieve(MODEL_URL, path, reporthook=_progress)
        print()
        print_fn(f"✅ Modelo salvo em: {path}")
        return True
    except Exception as e:
        if path.exists():
            path.unlink()
        print_fn(f"❌ Erro ao baixar: {e}")
        print_fn(f"   Baixe manualmente em: {MODEL_URL}")
        print_fn(f"   E coloque em: {MODELS_DIR}/")
        return False


# ── Carregamento do modelo ────────────────────────────────────
def load_model(model_name: str = DEFAULT_MODEL, print_fn=print):
    """Carrega o modelo na memória (singleton)."""
    global _llm_instance

    if _llm_instance is not None:
        return _llm_instance

    if not _ensure_llama_cpp():
        raise RuntimeError("Não foi possível instalar llama-cpp-python.")

    from llama_cpp import Llama

    path = get_model_path(model_name)
    if path is None:
        raise FileNotFoundError(
            f"Modelo não encontrado: {MODELS_DIR / model_name}\n"
            f"Baixe em: {MODEL_URL}\n"
            f"E coloque em: {MODELS_DIR}/"
        )

    print_fn(f"🧠 Carregando modelo local: {model_name}...")
    _llm_instance = Llama(
        model_path   = str(path),
        n_ctx        = 2048,      # contexto — reduz se travar
        n_threads    = os.cpu_count() or 4,
        n_gpu_layers = 0,         # CPU apenas (PC fraco)
        verbose      = False,
    )
    print_fn("✅ Modelo carregado! Modo offline ativo.")
    return _llm_instance


# ── Inferência ────────────────────────────────────────────────
def chat(
    messages:    list[dict],
    model_name:  str   = DEFAULT_MODEL,
    temperature: float = 0.85,
    max_tokens:  int   = 512,
    print_fn     = print,
) -> str:
    """
    Envia mensagens e retorna resposta do LLM local.
    messages: [{"role": "system/user/assistant", "content": "..."}]
    """
    llm = load_model(model_name, print_fn)

    # Formata no padrão ChatML / Gemma
    prompt = _format_prompt(messages)

    output = llm(
        prompt,
        max_tokens  = max_tokens,
        temperature = temperature,
        stop        = ["<end_of_turn>", "<|user|>", "\nVOCÊ:", "\n[NOX]"],
        echo        = False,
    )
    text = output["choices"][0]["text"].strip()
    # Limpa tags residuais do Gemma
    for tag in ["<start_of_turn>", "<end_of_turn>", "model\n", "user\n"]:
        text = text.replace(tag, "")
    return text.strip()


def _format_prompt(messages: list[dict]) -> str:
    """Formata mensagens no template do Gemma 2."""
    prompt = ""
    for msg in messages:
        role    = msg["role"]
        content = msg["content"]
        if role == "system":
            # Gemma não tem system nativo — coloca como primeiro user
            prompt += f"<start_of_turn>user\n{content}<end_of_turn>\n"
            prompt += "<start_of_turn>model\nEntendido.<end_of_turn>\n"
        elif role == "user":
            prompt += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role == "assistant":
            prompt += f"<start_of_turn>model\n{content}<end_of_turn>\n"
    prompt += "<start_of_turn>model\n"
    return prompt


# ── Status ────────────────────────────────────────────────────
def status() -> dict:
    models = list_available_models()
    return {
        "loaded":   _llm_instance is not None,
        "models":   models,
        "has_model": bool(models),
        "models_dir": str(MODELS_DIR),
    }
