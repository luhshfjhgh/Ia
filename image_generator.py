# -*- coding: utf-8 -*-
"""
image_generator.py — Geração de Imagens via Replicate (FLUX / SDXL)
=====================================================================
Módulo standalone. Não altera nenhuma outra parte do projeto.
Funciona mesmo sem token configurado (falha silenciosa com mensagem clara).

CONFIGURAÇÃO:
    Adicione no arquivo .env do projeto:
        REPLICATE_API_TOKEN=seu_token_aqui

    Obtenha seu token GRATUITO em:
        https://replicate.com/account/api-tokens

COMO FUNCIONA:
    1. Envia o prompt para a API REST da Replicate
    2. Fica em polling até a predição terminar (async API)
    3. Baixa a imagem gerada e salva em PNG na pasta output/
    4. Retorna o caminho do arquivo salvo

COMANDO NO SISTEMA:
    /imagine um gato astronauta na lua, estilo cartoon
"""

import os
import sys
import time
import datetime
import requests
from pathlib import Path

# ── Constantes ───────────────────────────────────────────────────────────────
_ENV_KEY     = "REPLICATE_API_TOKEN"
_API_BASE    = "https://api.replicate.com/v1"

# Modelo FLUX schnell — rápido, gratuito no tier free da Replicate, sem filtro agressivo
# Alternativa: "stability-ai/sdxl:39ed52f2319f9bf9b9f6a..." (se FLUX indisponível)
_MODEL       = "black-forest-labs/flux-schnell"

_TIMEOUT_REQ = 30    # timeout de cada request HTTP
_TIMEOUT_GEN = 180   # tempo máximo total para geração (3 min)
_POLL_DELAY  = 2.0   # intervalo entre checagens de status

_HERE        = Path(__file__).parent
_OUTPUT_DIR  = _HERE / "output"


# ══════════════════════════════════════════════════════════════════════════════
#  EXCEÇÃO PÚBLICA
# ══════════════════════════════════════════════════════════════════════════════

class ImageGeneratorError(Exception):
    """Erro ao gerar imagem. Capturado pelo /imagine sem quebrar o sistema."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  FUNÇÃO PRINCIPAL (interface pública — não mude a assinatura)
# ══════════════════════════════════════════════════════════════════════════════

def generate_image(
    prompt:     str,
    output_dir: str | None = None,
) -> str:
    """
    Gera uma imagem a partir de um prompt de texto usando a Replicate API.

    Parâmetros:
      prompt     — descrição da imagem desejada (português funciona bem)
      output_dir — pasta onde salvar (usa output/ se None)

    Retorna:
      Caminho absoluto da imagem PNG salva (str).

    Lança:
      ImageGeneratorError — em caso de falha (token inválido, timeout, etc.)
    """
    token = _get_token()

    out_dir = Path(output_dir) if output_dir else _OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"nox_{ts}.png"

    print(f"  [IMG] Enviando prompt para Replicate ({_MODEL})...", flush=True)

    # 1) Cria a predição
    prediction_url = _create_prediction(token, prompt)

    # 2) Aguarda o resultado em polling
    image_url = _wait_for_result(token, prediction_url)

    # 3) Baixa e salva a imagem
    _download_image(image_url, out_path)

    print(f"  [IMG] ✅ Salvo em: {out_path}", flush=True)
    return str(out_path)


# ══════════════════════════════════════════════════════════════════════════════
#  ETAPAS INTERNAS
# ══════════════════════════════════════════════════════════════════════════════

def _create_prediction(token: str, prompt: str) -> str:
    """
    Cria uma predição na Replicate e retorna a URL para acompanhar o status.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Prefer":        "wait",   # Replicate tenta retornar síncrono se < 60s
    }

    payload = {
        "input": {
            "prompt":              prompt,
            "num_outputs":         1,
            "output_format":       "png",
            "output_quality":      90,
            "num_inference_steps": 4,
        },
    }

    # Para modelos com "owner/name" sem versão fixa, usa o endpoint /models
    endpoint = f"{_API_BASE}/models/{_MODEL}/predictions"

    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=_TIMEOUT_REQ,
        )
    except requests.exceptions.Timeout:
        raise ImageGeneratorError(
            "Timeout ao conectar à API da Replicate. "
            "Verifique sua conexão com a internet."
        )
    except requests.exceptions.ConnectionError:
        raise ImageGeneratorError(
            "Sem conexão com a internet. "
            "Verifique sua rede e tente novamente."
        )

    _check_http_error(resp, "criar predição")

    data = resp.json()

    # Se o Prefer:wait retornou resultado imediato, pega a URL direto
    if data.get("status") == "succeeded":
        return _extract_image_url_from_output(data)

    # Caso contrário, retorna a URL de polling
    poll_url = data.get("urls", {}).get("get") or data.get("url")
    if not poll_url:
        raise ImageGeneratorError(
            f"Resposta inesperada da Replicate (sem URL de polling):\n{data}"
        )
    return poll_url


def _wait_for_result(token: str, poll_url: str) -> str:
    """
    Faz polling até a predição terminar. Retorna a URL da imagem gerada.
    """
    # Se já veio como URL de imagem direto (Prefer:wait resolveu)
    if poll_url.startswith("https://") and not "api.replicate.com" in poll_url:
        return poll_url

    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + _TIMEOUT_GEN

    while time.time() < deadline:
        try:
            resp = requests.get(poll_url, headers=headers, timeout=_TIMEOUT_REQ)
        except requests.exceptions.RequestException as e:
            raise ImageGeneratorError(f"Erro ao verificar status da geração: {e}")

        _check_http_error(resp, "verificar status")
        data   = resp.json()
        status = data.get("status", "")

        if status == "succeeded":
            return _extract_image_url_from_output(data)

        if status == "failed":
            erro = data.get("error") or "motivo desconhecido"
            raise ImageGeneratorError(f"Replicate falhou na geração: {erro}")

        if status == "canceled":
            raise ImageGeneratorError("Geração cancelada pela Replicate.")

        # status "starting" ou "processing" — aguarda
        print(f"  [IMG] Aguardando... ({status})", flush=True)
        time.sleep(_POLL_DELAY)

    raise ImageGeneratorError(
        f"Timeout: a geração demorou mais de {_TIMEOUT_GEN}s. "
        "Tente novamente ou use um prompt mais simples."
    )


def _extract_image_url_from_output(data: dict) -> str:
    """Extrai a URL da imagem do campo output da resposta."""
    output = data.get("output")
    if isinstance(output, list) and output:
        return output[0]
    if isinstance(output, str) and output.startswith("http"):
        return output
    raise ImageGeneratorError(
        f"Resposta inesperada da Replicate (sem output):\n{data}"
    )


def _download_image(url: str, out_path: Path):
    """Baixa a imagem da URL e salva em disco."""
    try:
        resp = requests.get(url, timeout=60, stream=True)
    except requests.exceptions.RequestException as e:
        raise ImageGeneratorError(f"Erro ao baixar a imagem gerada: {e}")

    if resp.status_code != 200:
        raise ImageGeneratorError(
            f"Erro HTTP {resp.status_code} ao baixar a imagem."
        )

    out_path.write_bytes(resp.content)


# ══════════════════════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def _check_http_error(resp: requests.Response, acao: str):
    """Lança ImageGeneratorError para respostas de erro HTTP."""
    if resp.status_code in (200, 201):
        return

    detail = ""
    try:
        j      = resp.json()
        detail = j.get("detail") or j.get("message") or str(j)
    except Exception:
        detail = resp.text[:300] if resp.text else f"status {resp.status_code}"

    if resp.status_code == 401:
        raise ImageGeneratorError(
            "Token inválido ou expirado.\n"
            "  1. Acesse: https://replicate.com/account/api-tokens\n"
            "  2. Crie um novo token\n"
            "  3. Cole no .env: REPLICATE_API_TOKEN=r8_..."
        )
    if resp.status_code == 402:
        raise ImageGeneratorError(
            "Créditos insuficientes na conta Replicate.\n"
            "Acesse https://replicate.com/billing para recarregar."
        )
    if resp.status_code == 422:
        raise ImageGeneratorError(
            f"Parâmetros inválidos enviados à Replicate: {detail}"
        )
    if resp.status_code == 429:
        raise ImageGeneratorError(
            "Rate limit atingido. Aguarde alguns segundos e tente novamente."
        )

    raise ImageGeneratorError(
        f"Erro HTTP {resp.status_code} ao {acao}: {detail}"
    )


def _get_token() -> str:
    """
    Lê o token da variável de ambiente REPLICATE_API_TOKEN
    ou do arquivo .env do projeto.
    """
    token = os.environ.get(_ENV_KEY, "").strip()
    if token and token not in ("COLE_SEU_TOKEN_AQUI", "seu_token_replicate_aqui"):
        return token

    # Tenta carregar do .env sem depender de python-dotenv
    env_paths = [_HERE / ".env", _HERE.parent / ".env"]
    for env_file in env_paths:
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith(_ENV_KEY + "="):
                        t = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if t and t not in ("COLE_SEU_TOKEN_AQUI", "seu_token_replicate_aqui"):
                            os.environ[_ENV_KEY] = t   # cacheia para a sessão
                            return t
            except Exception:
                pass

    raise ImageGeneratorError(
        "Token da Replicate não configurado.\n\n"
        "  COMO CONFIGURAR:\n"
        "  1. Acesse: https://replicate.com/account/api-tokens\n"
        "  2. Crie uma conta gratuita (não precisa de cartão)\n"
        "  3. Clique em 'Create token'\n"
        "  4. Abra o arquivo .env na pasta do projeto\n"
        "  5. Substitua a linha:\n"
        "       REPLICATE_API_TOKEN=COLE_SEU_TOKEN_AQUI\n"
        "     pelo seu token real:\n"
        "       REPLICATE_API_TOKEN=r8_xxxxxxxxxxxxxx"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  TESTE DIRETO (python image_generator.py "seu prompt aqui")
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "a cat astronaut on the moon, cartoon style"
    print(f"Gerando: {prompt!r}")
    try:
        path = generate_image(prompt)
        print(f"✅ Salvo em: {path}")
    except ImageGeneratorError as e:
        print(f"❌ {e}")
