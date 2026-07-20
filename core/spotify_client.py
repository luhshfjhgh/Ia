# -*- coding: utf-8 -*-
"""
core/spotify_client.py — Controle real do Spotify (Web API)
────────────────────────────────────────────────────────────────────
Permite pedir "toca [música] no Spotify" e ela tocar de verdade no
seu dispositivo, sem precisar abrir nada na tela, pesquisar ou clicar.

CONFIGURAÇÃO (só precisa fazer 1 vez):
  1. Crie um app em https://developer.spotify.com/dashboard
  2. Em "Redirect URI", adicione exatamente:
       http://127.0.0.1:8888/callback
     (é só um endereço local do seu PC — não precisa de site nenhum)
  3. Copie o Client ID e o Client Secret pro seu .env:
       SPOTIFY_CLIENT_ID=...
       SPOTIFY_CLIENT_SECRET=...
  4. Rode o comando /spotify_login dentro da Nox — isso abre o
     navegador UMA vez pra você autorizar, e salva um refresh_token
     no .env. Depois disso nunca mais precisa logar de novo.

Só usa "requests" (já é dependência do projeto) + biblioteca padrão
do Python pro servidor local temporário (http.server).
"""

from __future__ import annotations
import os
import time
import base64
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
import requests

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-modify-playback-state user-read-playback-state user-read-currently-playing"

_ENV_PATH_CANDIDATES = (".env", os.path.join(os.path.dirname(__file__), "..", ".env"))


def _load_env() -> dict:
    env = {}
    for path in _ENV_PATH_CANDIDATES:
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


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _load_env().get(key, default)


def _save_to_env(key: str, value: str) -> None:
    """Adiciona ou substitui uma variável no .env real do projeto."""
    path = ".env"
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "..", ".env")
    lines = []
    found = False
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.environ[key] = value


CLIENT_ID     = _get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = _get("SPOTIFY_CLIENT_SECRET")


def is_app_configured() -> bool:
    return bool(CLIENT_ID) and bool(CLIENT_SECRET)


def is_logged_in() -> bool:
    return is_app_configured() and bool(_get("SPOTIFY_REFRESH_TOKEN"))


# ── Passo único: login via navegador (loopback local) ──────────────────
_captured_code: dict = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        code = query.get("code", [None])[0]
        if code:
            _captured_code["code"] = code
            body = "<h2>Login com Spotify concluído! Pode fechar essa aba e voltar ao terminal.</h2>"
        else:
            body = "<h2>Não recebi o código de autorização. Tente de novo pelo terminal.</h2>"
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):
        pass  # silencia o log padrão do http.server


def run_oauth_setup(progress_cb=None) -> tuple[bool, str]:
    if not is_app_configured():
        return False, "Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no .env primeiro."

    _captured_code.clear()
    server = HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    if progress_cb:
        progress_cb("Abrindo o navegador para você autorizar o Spotify...")
    webbrowser.open(auth_url)

    t.join(timeout=120)
    server.server_close()

    code = _captured_code.get("code")
    if not code:
        return False, "Tempo esgotado ou login cancelado. Tente /spotify_login de novo."

    if progress_cb:
        progress_cb("Trocando o código por um token de acesso...")

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        timeout=15,
    )
    if resp.status_code != 200:
        return False, f"Spotify recusou a troca de token (HTTP {resp.status_code}): {resp.text[:200]}"

    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return False, "Não recebi refresh_token na resposta do Spotify."

    _save_to_env("SPOTIFY_REFRESH_TOKEN", refresh_token)
    return True, "Login com Spotify concluído! Já pode pedir músicas por voz."


# ── Token de acesso (renovado automaticamente) ───────────────────────────
_access_token_cache = {"token": None, "expires_at": 0}


def _get_access_token() -> str | None:
    if _access_token_cache["token"] and time.time() < _access_token_cache["expires_at"] - 30:
        return _access_token_cache["token"]

    refresh_token = _get("SPOTIFY_REFRESH_TOKEN")
    if not (is_app_configured() and refresh_token):
        return None

    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    _access_token_cache["token"] = data["access_token"]
    _access_token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _access_token_cache["token"]


# ── Buscar e tocar uma música específica ─────────────────────────────────
def search_and_play(query: str) -> str:
    token = _get_access_token()
    if not token:
        return ("⚠️ Spotify ainda não está logado. Rode /spotify_login primeiro "
                "(ou eu abro a busca no navegador mesmo — só falar de novo).")

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers, params={"q": query, "type": "track", "limit": 1}, timeout=15,
    )
    if r.status_code != 200:
        return f"❌ Erro ao buscar no Spotify (HTTP {r.status_code})."
    items = r.json().get("tracks", {}).get("items", [])
    if not items:
        return f"❌ Não achei '{query}' no Spotify."
    track = items[0]
    uri = track["uri"]
    nome = track["name"]
    artista = ", ".join(a["name"] for a in track.get("artists", []))

    devices_r = requests.get("https://api.spotify.com/v1/me/player/devices", headers=headers, timeout=15)
    devices = devices_r.json().get("devices", []) if devices_r.status_code == 200 else []
    if not devices:
        return ("⚠️ Achei a música, mas não encontrei nenhum dispositivo Spotify ativo. "
                "Abre o app do Spotify (pode ser minimizado) e tenta de novo.")
    device_id = next((d["id"] for d in devices if d.get("is_active")), devices[0]["id"])

    play_r = requests.put(
        f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
        headers=headers, json={"uris": [uri]}, timeout=15,
    )
    if play_r.status_code in (200, 204):
        return f"🎵 Tocando: {nome} — {artista}"
    return f"❌ Não consegui iniciar a reprodução (HTTP {play_r.status_code})."
