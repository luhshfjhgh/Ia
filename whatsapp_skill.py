# -*- coding: utf-8 -*-
"""
NOX AI — WhatsApp Skill (whatsapp_skill.py)
===========================================
Detecta intenções de WhatsApp na fala do usuário e executa ações:
  • Conectar / desconectar WhatsApp via QR Code
  • Ativar / desativar resposta automática (auto-reply com IA)
  • Enviar mensagem para contato (com confirmação por voz)
  • Ler mensagens recebidas e enviadas por voz
  • Ver status da conexão

Coloque este arquivo em:  nox_output/whatsapp_skill.py

Dependências:
  pip install qrcode pillow
  (whatsapp-web.js já é gerenciado pelo whatsapp_bot.py)
"""

import os
import re
import sys
import time
import base64
import io
import threading
import unicodedata

# ── Garante que communication/ esteja no path ──────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
_COMM = os.path.join(_BASE, "communication")
for _p in (_COMM, _BASE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import whatsapp_bot as wpp


# ══════════════════════════════════════════════════════════════════════════
#  DETECÇÃO DE INTENÇÕES
# ══════════════════════════════════════════════════════════════════════════
#
# IMPORTANTE: a detecção é baseada em PALAVRAS-CHAVE (não em regex rígido de
# adjacência), porque a fala transcrita por voz quase sempre tem palavras de
# preenchimento entre o verbo e o assunto — por exemplo:
#   "conecta meu whatsapp"        (tem "meu" no meio)
#   "pode ligar o whatsapp pra mim"
#   "ei nox, ativa o whatsapp aí"
# Um regex de adjacência (`conectar\s+whatsapp`) falha em todos esses casos
# e a frase acaba caindo na IA genérica, que responde com instruções
# inúteis de "baixe o aplicativo do WhatsApp..." em vez de chamar a ação.
# ══════════════════════════════════════════════════════════════════════════

# Enviar mensagem — captura TUDO após "para/pro/pra" como `rest`.
# A separação entre nome-do-contato e mensagem é feita em _act_send(),
# APÓS buscar os contatos reais do WhatsApp, para não cortar nomes
# compostos como "Viva a Vida" no meio e não rejeitar números com traços.
_PAT_SEND = re.compile(
    r"(?:mand[ae]|envi[ae]r?|envi(?:e|ou)|diz(?:er|e)?|fala(?:r)?|"
    r"escrev[ae]r?|escrev[ae]|pass[ae]r?|coloc[ae]r?)\b"
    r"(?:.{0,50}?)\b(?:para|pro|pra|ao?|à)\s+"
    r"(?P<rest>.{3,})",
    re.I | re.DOTALL
)


def _normalize(text: str) -> str:
    """Minúsculas + remove acentos, para comparação tolerante de palavras-chave."""
    t = text.lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t


def _has_any(t: str, words: tuple[str, ...]) -> bool:
    return any(w in t for w in words)


# ══════════════════════════════════════════════════════════════════════════
#  ENVIO DE ARQUIVOS (fotos, vídeos, documentos do PC) — busca + detecção
# ══════════════════════════════════════════════════════════════════════════

# Palavra de tipo de arquivo → categoria + extensões aceitas
_FILE_TYPE_WORDS = {
    "foto": "image", "fotos": "image", "imagem": "image", "imagens": "image",
    "print": "image", "prints": "image", "captura": "image", "screenshot": "image",
    "video": "video", "vídeo": "video", "vídeos": "video", "videos": "video",
    "documento": "document", "documentos": "document", "arquivo": "document",
    "arquivos": "document", "pdf": "document", "planilha": "document",
    "audio": "audio", "áudio": "audio", "audios": "audio", "áudios": "audio",
    "musica": "audio", "música": "audio",
}

_EXT_BY_TYPE = {
    "image":    (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"),
    "video":    (".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"),
    "document": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                 ".txt", ".csv", ".rtf"),
    "audio":    (".mp3", ".wav", ".ogg", ".m4a", ".flac"),
}

_TIPO_LABEL = {
    "image": "a foto", "video": "o vídeo",
    "document": "o arquivo", "audio": "o áudio",
}

_RECENT_WORDS = ("ultimo", "ultima", "últimos", "ultimas", "mais recente",
                  "recente", "recém", "novo", "nova", "que tirei", "que baixei",
                  "que gravei", "que salvei")

# Pastas comuns onde o usuário guarda arquivos (cobre nomes em inglês e
# português, já que o Windows traduz as pastas pessoais conforme o idioma)
def _common_media_dirs() -> list:
    from pathlib import Path
    home = Path.home()
    nomes = [
        "Downloads",
        "Pictures", "Imagens",
        "Videos", "Vídeos",
        "Documents", "Documentos",
        "Desktop", "Área de Trabalho",
        "Music", "Músicas",
    ]
    candidatos = [home / n for n in nomes]
    # também tenta dentro do OneDrive, comum em instalações Windows recentes
    onedrive = home / "OneDrive"
    if onedrive.exists():
        candidatos += [onedrive / n for n in nomes]
    vistos = set()
    pastas = []
    for c in candidatos:
        try:
            if c.exists() and c.is_dir() and str(c) not in vistos:
                vistos.add(str(c))
                pastas.append(c)
        except Exception:
            continue
    return pastas


def find_files(keyword: str = "", file_type: str | None = None,
               most_recent: bool = False, limit: int = 5) -> list:
    """
    Procura arquivos nas pastas comuns do usuário (Downloads, Imagens,
    Vídeos, Documentos, Desktop, Músicas — incluindo nomes em português).
    Não entra em subpastas (mantém rápido e previsível).

    keyword     — texto pra bater com o NOME do arquivo (sem acento, sem case)
    file_type   — "image" | "video" | "document" | "audio" | None (qualquer tipo)
    most_recent — se True, prioriza o arquivo modificado mais recentemente
    limit       — máximo de resultados retornados

    Retorna lista de objetos Path, ordenada do mais recente pro mais antigo.
    """
    exts = _EXT_BY_TYPE.get(file_type) if file_type else None
    kw   = _normalize(keyword) if keyword else ""

    matches = []
    for pasta in _common_media_dirs():
        try:
            for f in pasta.iterdir():
                if not f.is_file():
                    continue
                if exts and f.suffix.lower() not in exts:
                    continue
                if kw and kw not in _normalize(f.stem):
                    continue
                matches.append(f)
        except Exception:
            continue

    matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return matches[:limit]


# Verbos de envio aceitos — captura tudo após "para/pro/pra" como `rest`
# (mesma estratégia do _PAT_SEND; a separação contato/legenda é feita depois)
_PAT_SEND_FILE = re.compile(
    r"(?:mand[ae]|envi[ae]r?|envi(?:e|ou))\b"
    r"(?P<middle>.{0,60}?)\b(?:para|pro|pra|ao?|à)\s+"
    r"(?P<rest>.{2,})",
    re.I | re.DOTALL
)

# Palavras que não fazem parte do termo de busca do arquivo (artigos,
# conectores, e as próprias palavras de tipo/recência)
_FILE_STOPWORDS = set(_FILE_TYPE_WORDS.keys()) | {
    "a", "o", "as", "os", "da", "do", "das", "dos", "de", "um", "uma",
    "uns", "umas", "esse", "essa", "esses", "essas", "esta", "este",
    "que", "ultimo", "ultima", "ultimos", "ultimas", "mais", "recente",
    "recem", "novo", "nova", "no", "na", "nos", "nas", "whatsapp", "zap",
    "tirei", "baixei", "gravei", "salvei", "minha", "meu", "minhas", "meus",
}


def _detect_send_file(raw: str) -> dict | None:
    """
    Detecta pedidos de ENVIO DE ARQUIVO (foto/vídeo/documento/áudio do PC),
    diferenciando de um simples envio de mensagem de texto.
    Ex.: "manda a foto da praia para o joão"
         "envia o último vídeo que eu gravei para a maria"
         "manda o arquivo relatorio.pdf pro chefe"
    """
    m = _PAT_SEND_FILE.search(raw)
    if not m:
        return None

    middle_raw = m.group("middle") or ""
    middle     = _normalize(middle_raw)

    file_type = None
    for palavra, tipo in _FILE_TYPE_WORDS.items():
        if palavra in middle:
            file_type = tipo
            break

    if not file_type:
        return None  # não é pedido de arquivo — deixa cair pro envio de texto normal

    most_recent = any(w in middle for w in _RECENT_WORDS)

    palavras = [w for w in middle.split() if w not in _FILE_STOPWORDS]
    keyword  = " ".join(palavras).strip()

    rest    = (m.group("rest") or "").strip()
    # Legenda: tudo após "dizendo|falando|legenda" dentro de rest
    caption = ""
    legend_m = re.search(r"\b(?:dizendo|falando|com a legenda|legenda)\s+(.+)$", rest, re.I)
    if legend_m:
        caption = legend_m.group(1).strip()
        rest    = rest[:legend_m.start()].strip()

    if not rest:
        return None

    return {
        "intent":      "send_file",
        "rest":        rest,       # contato (separado em _act_send_file)
        "file_type":   file_type,
        "keyword":     keyword,
        "most_recent": most_recent,
        "caption":     caption,
    }


def detect_intent(text: str) -> dict | None:
    """
    Analisa o texto do usuário (transcrito por voz ou digitado) e retorna
    a intenção de WhatsApp, ou None se não for um comando de WhatsApp.

    Retornos possíveis:
      {"intent": "connect"}
      {"intent": "disconnect"}
      {"intent": "auto_reply_on"}
      {"intent": "auto_reply_off"}
      {"intent": "read_messages"}
      {"intent": "status"}
      {"intent": "send", "contact": str, "message": str}
      {"intent": "send_file", "contact": str, "file_type": str,
       "keyword": str, "most_recent": bool, "caption": str}
    """
    raw = text.strip()
    if not raw:
        return None
    t = _normalize(raw)

    # ── 1) Resposta automática (checar ANTES de whatsapp on/off, pois
    #       "ativar"/"desativar" também aparecem em frases de conectar) ──
    if _has_any(t, ("automatic", "automat", "auto resposta", "autoresposta", "auto reply")):
        if _has_any(t, ("desativ", "desliga", "desabilit", "para de responder",
                        "pare de responder", "cancela")):
            return {"intent": "auto_reply_off"}
        if _has_any(t, ("ativ", "liga", "habilit", "comeca", "começa")):
            return {"intent": "auto_reply_on"}

    # ── 2) Detecta se a frase é sobre WhatsApp de modo geral ────────────
    has_wpp = (
        "whatsapp" in t
        or "watsap" in t
        or "uatzap" in t
        or "uotsap" in t
        or re.search(r"\bzap\b", t) is not None
        or "zap zap" in t
    )

    if has_wpp:
        # Status — checar PRIMEIRO: frases como "o whatsapp está conectado"
        # ou "ta desconectado" contêm a substring "conect" e seriam
        # erroneamente classificadas como comando de conectar/desconectar
        # se checadas depois. Frases de status normalmente têm "está/tá/é"
        # antes do adjetivo "conectado/desconectado", então checamos isso
        # primeiro.
        if _has_any(t, ("status", "esta conectado", "ta conectado",
                        "e conectado", "esta desconectado", "ta desconectado",
                        "esta funcionando", "ta funcionando", "online",
                        "situacao do whatsapp", "estado do whatsapp",
                        "como esta o whatsapp", "como ta o whatsapp")):
            return {"intent": "status"}

        # Desconectar (checar ANTES de conectar: "desconectar" contém "conectar")
        if _has_any(t, ("desconect", "desliga", "fecha o whatsapp", "fecha whatsapp",
                        "encerra", "sair do whatsapp", "log out", "logout", "deslogar")):
            return {"intent": "disconnect"}

        # Conectar / abrir QR Code
        if _has_any(t, ("conect", "liga", "inicia", "ativ", "abr", "escane",
                        "qrcode", "qr code", "codigo qr", "gera o qr",
                        "mostra o qr", "ler o qr")):
            return {"intent": "connect"}

        # Ler mensagens
        if _has_any(t, ("ler mensage", "ver mensage", "mostra mensage",
                        "checa mensage", "verifica mensage", "tem mensage",
                        "mensagem nova", "mensagens novas", "mensagem nao lida",
                        "mensagens nao lidas")):
            return {"intent": "read_messages"}

    # ── 3) Enviar ARQUIVO (foto/vídeo/documento/áudio do PC) — checar
    #       ANTES do envio de texto puro, pois "manda a foto da praia
    #       para joão" não pode virar mensagem de texto com "a foto da
    #       praia" como nome de contato ──────────────────────────────
    file_intent = _detect_send_file(raw)
    if file_intent:
        return file_intent

    # ── 4) Enviar mensagem de texto (funciona mesmo sem a palavra
    #       "whatsapp", ex.: "manda pro joão bom dia") ────────────────
    m = _PAT_SEND.search(raw)
    if m:
        rest = m.group("rest").strip()
        if len(rest) >= 3:
            return {"intent": "send", "rest": rest}

    # ── 5) Se mencionou WhatsApp mas nenhuma ação específica bateu,
    #       trata como pedido de status (fallback seguro, evita cair
    #       na IA genérica e ela "inventar" instruções de instalação) ──
    if has_wpp:
        return {"intent": "status"}

    return None


# ══════════════════════════════════════════════════════════════════════════
#  EXECUTOR DE INTENÇÕES
# ══════════════════════════════════════════════════════════════════════════

def handle_intent(
    intent: dict,
    nox,
    speak_fn,
    listen_fn,
    qr_callback=None,
) -> str:
    """
    Executa a intenção de WhatsApp detectada.

    Parâmetros:
      intent      — dict retornado por detect_intent()
      nox         — instância do NoxAI (main.py)
      speak_fn    — função para falar (nox._speak_blocking)
      listen_fn   — função para ouvir (nox.listen_vad)
      qr_callback — fn(qr_data_str) chamada quando QR chegar (para exibir na UI)

    Retorna string com a resposta para ser falada/exibida.
    """
    action = intent.get("intent")

    if action == "connect":
        return _act_connect(speak_fn, qr_callback)
    if action == "disconnect":
        return _act_disconnect()
    if action == "auto_reply_on":
        return _act_auto_reply_on(nox)
    if action == "auto_reply_off":
        return _act_auto_reply_off()
    if action == "read_messages":
        return _act_read_messages()
    if action == "status":
        return wpp.status_str()
    if action == "send":
        return _act_send(
            intent["rest"],
            speak_fn, listen_fn
        )
    if action == "send_file":
        return _act_send_file(
            intent["rest"], intent["file_type"], intent["keyword"],
            intent["most_recent"], intent.get("caption", ""),
            speak_fn, listen_fn
        )

    return "Desculpe, não entendi a ação do WhatsApp."


# ══════════════════════════════════════════════════════════════════════════
#  AÇÕES INDIVIDUAIS
# ══════════════════════════════════════════════════════════════════════════

def _act_connect(speak_fn, qr_callback=None) -> str:
    if wpp.is_connected():
        return "WhatsApp já está conectado!"
    if wpp.is_connecting():
        return "WhatsApp está sendo conectado. Aguarde o QR Code aparecer."

    # Registra callback de QR antes de conectar
    if qr_callback:
        wpp.add_qr_callback(qr_callback)

    # Avisa se é a primeira vez (vai instalar whatsapp-web.js via npm,
    # o que pode levar de um a três minutos)
    first_time = not wpp._check_packages()
    if first_time:
        speak_fn(
            "Primeira conexão. Vou instalar os componentes do WhatsApp agora, "
            "isso pode levar de um a três minutos. Aguarde, o QR Code vai "
            "aparecer assim que terminar."
        )
    else:
        speak_fn("Iniciando WhatsApp. O QR Code vai aparecer em instantes. Escaneie com seu celular.")

    ok, msg = wpp.connect()
    return msg


def _act_disconnect() -> str:
    if not wpp.is_connected() and not wpp.is_connecting():
        return "WhatsApp não estava conectado."
    return wpp.disconnect()


def _act_auto_reply_on(nox) -> str:
    if not wpp.is_connected():
        return ("WhatsApp não está conectado. "
                "Diga 'conectar WhatsApp' primeiro.")

    def _on_msg(msg_obj: dict):
        if msg_obj.get("type") != "message":
            return
        body   = msg_obj.get("body", "").strip()
        from_id = msg_obj.get("reply_to") or msg_obj.get("from", "")
        name    = msg_obj.get("name", from_id)
        if not body or not from_id:
            return
        try:
            prompt  = f"[Mensagem WhatsApp de {name}]: {body}"
            resposta = nox._process_and_respond(prompt)
            if resposta:
                wpp.send_message(from_id, resposta)
        except Exception as e:
            print(f"[WPP-AutoReply] Erro ao responder {name}: {e}")

    wpp.add_message_callback(_on_msg)
    # Guarda ref para poder remover depois
    wpp._nox_auto_reply_cb = _on_msg
    return ("Resposta automática ativada! "
            "Vou responder todas as mensagens do WhatsApp usando a IA.")


def _act_auto_reply_off() -> str:
    cb = getattr(wpp, "_nox_auto_reply_cb", None)
    if cb:
        wpp.remove_message_callback(cb)
        wpp._nox_auto_reply_cb = None
    return "Resposta automática desativada."


def _act_read_messages() -> str:
    if not wpp.is_connected():
        return "WhatsApp não está conectado."

    wpp.request_chats()
    time.sleep(2.5)
    msgs = wpp.get_pending(timeout=3.0)

    chat_data = next((m for m in msgs if m.get("type") == "chats"), None)
    if not chat_data:
        return ("Não consegui buscar as conversas agora. "
                "Verifique se o WhatsApp está conectado e tente novamente.")

    chats  = chat_data.get("data", [])
    unread = [c for c in chats if c.get("unread", 0) > 0]

    if not unread:
        return "Não há mensagens não lidas no WhatsApp."

    partes = [f"Você tem {len(unread)} conversa{'s' if len(unread) > 1 else ''} com mensagens não lidas:"]
    for i, c in enumerate(unread[:6], 1):
        nome   = c.get("name") or c.get("id", "desconhecido")
        qtd    = c.get("unread", 0)
        partes.append(f"{i}. {nome}: {qtd} mensagem{'ns' if qtd > 1 else ''}.")

    return " ".join(partes)


def _resolve_contact_or_number(contact_name: str) -> tuple[str | None, str | None]:
    """
    Resolve um nome de contato (fuzzy) ou, se for um número puro com pelo
    menos 8 dígitos, usa o número diretamente. Retorna (contact_id, nome)
    ou (None, None) se não encontrou nada utilizável.
    """
    contact_id, matched_name = _resolve_contact(contact_name)
    if contact_id:
        return contact_id, matched_name

    clean = re.sub(r"[^\d]", "", contact_name)
    if len(clean) >= 8:
        return clean + "@c.us", clean

    return None, None


def _split_rest(rest: str, contacts: list[dict]) -> tuple[str, str]:
    """
    Dado o texto bruto após "para/pro/pra" (ex: "Viva a Vida oi tudo bem"),
    tenta separar em (nome_do_contato, mensagem) usando os contatos reais
    do WhatsApp como referência.

    Estratégia:
    1. Se começa com dígitos/traço/parêntese → extrai número como contato
    2. Tenta cada contato como prefixo de `rest` (do mais longo pro mais curto)
    3. Heurística: primeira palavra(s) que antecedem um "inicio de frase"
       típico (oi, olá, bom, quando, preciso, etc.)
    4. Fallback: primeira palavra = contato, resto = mensagem
    """
    rest = rest.strip()

    # ── 1) Número de telefone ────────────────────────────────────────
    num_m = re.match(r'^([\d\s\-\(\)\+]{7,20})\s+(.+)$', rest)
    if num_m:
        num   = re.sub(r'[^\d]', '', num_m.group(1))
        msg   = num_m.group(2).strip()
        if len(num) >= 8 and msg:
            return num, msg

    # ── 2) Match com contatos reais (do nome mais longo pro mais curto) ──
    rest_norm = _normalize(rest)
    cands = sorted(contacts, key=lambda c: len(c.get("name") or ""), reverse=True)
    for c in cands:
        cname = (c.get("name") or "").strip()
        if not cname:
            continue
        cname_norm = _normalize(cname)
        if rest_norm.startswith(cname_norm):
            after = rest[len(cname):].strip()
            # limpa conectores no início da mensagem
            after = re.sub(r'^(?:dizendo|falando|que|:)\s*', '', after, flags=re.I).strip()
            if after:
                return cname, after

    # ── 3) Heurística: encontra início de frase típico de mensagem ────
    # Palavras que provavelmente começam a mensagem (não são nome de pessoa)
    MSG_STARTS = re.compile(
        r'\b(?:oi|olá|ola|bom\s+dia|boa\s+tarde|boa\s+noite|tudo|como|quando|'
        r'onde|por\s+que|porque|preciso|pode|vou|vim|estou|to\s+|to$|'
        r'me\s+|te\s+|quero|consegue|faz\s+favor|por\s+favor|obrigado|'
        r'qual|quem|já|ja|ainda|não|nao|sim|ok|opa|eai|e\s+aí|'
        r'saudades|feliz|parabéns|parabens|boa|bora|vamos|segue)\b',
        re.I
    )
    words = rest.split()
    for i in range(1, min(len(words), 6)):
        candidate_contact = " ".join(words[:i])
        candidate_msg     = " ".join(words[i:])
        if candidate_msg and MSG_STARTS.match(candidate_msg):
            return candidate_contact, candidate_msg

    # ── 4) Fallback: primeira palavra = contato, resto = mensagem ────
    if len(words) >= 2:
        return words[0], " ".join(words[1:])

    return rest, ""


def _act_send(rest: str, speak_fn, listen_fn) -> str:
    """
    Separa contato e mensagem de `rest` (ex: "Viva a Vida oi como vai"),
    confirma por voz e envia. Busca os contatos reais para fazer o split
    corretamente mesmo com nomes compostos como "Viva a Vida".
    """
    if not wpp.is_connected():
        return ("WhatsApp não está conectado. "
                "Diga 'conectar WhatsApp' primeiro.")

    # Busca contatos reais para fazer o split inteligente
    wpp.request_contacts()
    time.sleep(2.5)
    msgs     = wpp.get_pending(timeout=3.0)
    cdata    = next((m for m in msgs if m.get("type") == "contacts"), None)
    contacts = cdata.get("data", []) if cdata else []

    contact_name, message = _split_rest(rest, contacts)
    contact_name = contact_name.strip().rstrip(" ,.")

    if not message:
        speak_fn(
            f"Entendi que você quer mandar mensagem para {contact_name}, "
            "mas não entendi o texto. O que você quer dizer?"
        )
        message = listen_fn() or ""
        if not message:
            return "Envio cancelado — nenhuma mensagem informada."

    contact_id, matched_name = _resolve_contact_or_number(contact_name)
    if not contact_id:
        return (f"Não encontrei o contato '{contact_name}'. "
                "Verifique o nome ou fale o número.")

    confirm_text = (
        f"Vou enviar para {matched_name}: {message}. "
        "Confirma? Diga sim ou não."
    )
    speak_fn(confirm_text)

    if listen_fn:
        resposta = listen_fn() or ""
        if any(w in resposta.lower()
               for w in ["sim", "yes", "confirma", "pode", "manda", "ok", "envia"]):
            wpp.send_message(contact_id, message)
            return f"Mensagem enviada para {matched_name}!"
        else:
            return "Envio cancelado."

    return confirm_text


def _act_send_file(
    rest: str,
    file_type: str,
    keyword: str,
    most_recent: bool,
    caption: str,
    speak_fn,
    listen_fn,
) -> str:
    if not wpp.is_connected():
        return ("WhatsApp não está conectado. "
                "Diga 'conectar WhatsApp' primeiro.")

    candidatos = find_files(
        keyword=keyword, file_type=file_type,
        most_recent=most_recent, limit=5,
    )

    tipo_label = _TIPO_LABEL.get(file_type, "o arquivo")

    if not candidatos:
        alvo = f"chamado(a) '{keyword}'" if keyword else "recente"
        return (f"Não encontrei nenhum(a) "
                f"{tipo_label.replace('a ', '').replace('o ', '')} "
                f"{alvo} nas pastas do seu computador.")

    escolhido = candidatos[0]

    # Resolve contato (usa contatos reais para split inteligente)
    wpp.request_contacts()
    time.sleep(2.5)
    msgs     = wpp.get_pending(timeout=3.0)
    cdata    = next((m for m in msgs if m.get("type") == "contacts"), None)
    contacts = cdata.get("data", []) if cdata else []

    contact_name, _ = _split_rest(rest, contacts)
    contact_name = contact_name.strip().rstrip(" ,.")

    contact_id, matched_name = _resolve_contact_or_number(contact_name)
    if not contact_id:
        return (f"Não encontrei o contato '{contact_name}'. "
                "Verifique o nome ou fale o número.")

    confirm_text = (
        f"Vou enviar para {matched_name} {tipo_label} '{escolhido.name}'. "
        "Confirma? Diga sim ou não."
    )
    speak_fn(confirm_text)

    if listen_fn:
        resposta = listen_fn() or ""
        if any(w in resposta.lower()
               for w in ["sim", "yes", "confirma", "pode", "manda", "ok", "envia"]):
            wpp.send_media(contact_id, str(escolhido), caption)
            time.sleep(1.0)
            pendentes = wpp.get_pending(timeout=10.0)
            erro = next((m for m in pendentes if m.get("type") == "error"), None)
            if erro:
                return f"Não consegui enviar: {erro.get('data', 'erro desconhecido')}"
            return f"{escolhido.name} enviado para {matched_name}!"
        else:
            return "Envio cancelado."

    return confirm_text


def _resolve_contact(name: str) -> tuple[str | None, str]:
    """
    Busca um contato por nome (fuzzy matching) via whatsapp-web.js.
    Retorna (contact_id, display_name) ou (None, name).
    """
    wpp.request_contacts()
    time.sleep(2.5)
    msgs = wpp.get_pending(timeout=3.0)

    contacts_data = next((m for m in msgs if m.get("type") == "contacts"), None)
    if not contacts_data:
        return (None, name)

    contacts  = contacts_data.get("data", [])
    name_low  = name.lower().strip()
    words     = [w for w in name_low.split() if len(w) > 2]

    best       = None
    best_score = 0

    for c in contacts:
        cname = (c.get("name") or c.get("number") or "").lower()
        # Pontuação: quantas palavras do nome estão no contato
        score = sum(1 for w in words if w in cname)
        # Bônus: nome exato contido
        if name_low in cname:
            score += 2
        if score > best_score:
            best_score = score
            best = c

    if best and best_score > 0:
        display = best.get("name") or best.get("number") or name
        return (best["id"], display)

    return (None, name)


# ══════════════════════════════════════════════════════════════════════════
#  MONITOR DE MENSAGENS (thread que ouve mensagens e fala por voz)
# ══════════════════════════════════════════════════════════════════════════

_monitor_thread: threading.Thread | None = None
_monitor_running: bool = False


def start_message_monitor(speak_fn, log_fn, nox=None):
    """
    Inicia uma thread que monitora mensagens recebidas do WhatsApp
    e as lê em voz alta quando auto-reply está desativado.

    Parâmetros:
      speak_fn — função para falar (nox._speak_blocking)
      log_fn   — função para logar na UI (api.push_log)
      nox      — instância NoxAI (opcional, usado para contexto)
    """
    global _monitor_thread, _monitor_running

    if _monitor_running:
        return

    _monitor_running = True

    def _worker():
        import queue as _queue
        global _monitor_running

        # Fila local para receber mensagens sem drenar a _incoming_q principal
        local_q: _queue.Queue = _queue.Queue()

        def _on_msg(msg_obj: dict):
            if msg_obj.get("type") == "message":
                local_q.put(msg_obj)

        wpp.add_message_callback(_on_msg)

        try:
            while _monitor_running:
                try:
                    obj = local_q.get(timeout=0.5)
                except _queue.Empty:
                    continue

                name  = obj.get("name") or obj.get("from", "alguém")
                body  = obj.get("body", "").strip()
                if not body:
                    continue

                short = body if len(body) <= 60 else body[:57] + "..."
                log_fn(f"› 📱 WPP [{name}]: {short}")

                # Fala a mensagem se auto-reply estiver desligado
                auto_on = getattr(wpp, "_nox_auto_reply_cb", None) is not None
                if not auto_on:
                    fala = f"Nova mensagem do WhatsApp de {name}: {body}"
                    speak_fn(fala)

        finally:
            wpp.remove_message_callback(_on_msg)
            _monitor_running = False

    _monitor_thread = threading.Thread(target=_worker, daemon=True, name="wpp-monitor")
    _monitor_thread.start()


def stop_message_monitor():
    """Para o monitor de mensagens."""
    global _monitor_running
    _monitor_running = False


# ══════════════════════════════════════════════════════════════════════════
#  GERAR QR CODE COMO BASE64 PNG (para exibir na UI webview)
# ══════════════════════════════════════════════════════════════════════════

def qr_data_to_base64_png(qr_data: str) -> str | None:
    """
    Converte dados brutos do QR Code em imagem PNG base64.
    Retorna string "data:image/png;base64,..." ou None se qrcode não disponível.
    """
    try:
        import qrcode                     # pip install qrcode pillow
        from PIL import Image

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=3,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img: Image.Image = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    except ImportError:
        return None
    except Exception:
        return None
