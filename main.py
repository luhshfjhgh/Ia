# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║           NOX AI - Terminal Assistant        ║
║         by WR Programação / Neurocode        ║
╚══════════════════════════════════════════════╝
  v3.0 — Controle total do notebook (arquivos, apps,
          volume, processos, screenshot, sistema),
          Player de música local + Spotify,
          WhatsApp via QR Code com auto-resposta IA,
          Comandos em linguagem natural para o PC
"""

import os
import sys

# ── Garante que as subpastas do projeto estejam no path ──────────────────
# Necessário para imports como "from memory import MemoryManager",
# "from config_manager import ConfigManager", etc.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# IMPORTANTE: "memory" foi removido desta lista.
# Adicionar nox_output/memory/ ao sys.path faz o Python encontrar
# memory/memory.py como o módulo "memory" (arquivo plano), o que impede
# from memory.global_memory import gm de funcionar ("memory is not a package").
# O pacote memory/ é acessado corretamente via _BASE_DIR no sys.path abaixo.
for _sub in ("config", "security", "models", "core", "communication"):
    _p = os.path.join(_BASE_DIR, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Garante que nox_output/ esteja no path para que o pacote memory/ seja
# encontrado como pacote (diretório com __init__.py).
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)
# ─────────────────────────────────────────────────────────────────────────
import asyncio
import threading
import time
import re
import tempfile
import wave
import json
import random
import math
import base64
import string
import subprocess
from splash import run_splash
from datetime import datetime, timedelta
from collections import deque

try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError, Exception):
    SOUNDDEVICE_AVAILABLE = False
    sd = None
    try:
        import numpy as np
    except ImportError:
        np = None

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except (ImportError, OSError, Exception):
    SPEECH_AVAILABLE = False
    sr = None

try:
    import edge_tts
    TTS_AVAILABLE = True
except (ImportError, OSError, Exception):
    TTS_AVAILABLE = False
    edge_tts = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except (ImportError, OSError, Exception):
    REQUESTS_AVAILABLE = False
    requests = None

from memory import MemoryManager
from config_manager import ConfigManager
from ban_system import check_ban, apply_ban, scan_message, is_morse_dangerous, verify_admin_password, get_ban_details_with_password
import ollama_client as _ollama
import local_llm as _local_llm
import system_control as sc

# ── Interface gráfica de voz (voice_ui.py) ────────────────────────────
try:
    from voice_ui import launch_voice_ui
    VOICE_UI_AVAILABLE = True
except ImportError:
    VOICE_UI_AVAILABLE = False
    launch_voice_ui = None
import whatsapp_bot as wpp

# ── Seleção automática de modelo (DeepSeek Coder V2 p/ tarefas de dev) ──
sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
from model_selector import select_model, DEV_MODEL_NAME, DEV_MODEL_LABEL, DEV_SYSTEM_PROMPT

# ── Sistema de contas (login/cadastro + histórico por usuário) ─────────
import auth as nox_auth

# ── Modelo de programação via Hugging Face (fallback do modo Developer) ─
import huggingface_client as hf_client

# ── Auto-atualização via GitHub (/manutencao) ──────────────────────────
import updater as nox_updater

# ── Sistema Multiagente ───────────────────────────────────────────
try:
    from core.orchestrator        import orchestrator as _ORCHESTRATOR
    from exports.project_exporter import export_project, list_exported_projects
    from memory.global_memory     import gm as _GLOBAL_MEM
    from core.grok_client         import set_api_key as _grok_set_key
    MULTIAGENT_AVAILABLE = True
except Exception as _mae:
    MULTIAGENT_AVAILABLE = False
    _ORCHESTRATOR = None
    _mae_reason   = str(_mae)


# ════════════════════════════════════════════════
#  CORES
# ════════════════════════════════════════════════
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[96m"
    PURPLE  = "\033[95m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    BLUE    = "\033[94m"
    ORANGE  = "\033[38;5;208m"
    PINK    = "\033[38;5;213m"
    BG_RED  = "\033[41m"


BANNER = f"""
{C.PURPLE}{C.BOLD}
  ███╗   ██╗ ██████╗ ██╗  ██╗     █████╗ ██╗
  ████╗  ██║██╔═══██╗╚██╗██╔╝    ██╔══██╗██║
  ██╔██╗ ██║██║   ██║ ╚███╔╝     ███████║██║
  ██║╚██╗██║██║   ██║ ██╔██╗     ██╔══██║██║
  ██║ ╚████║╚██████╔╝██╔╝ ██╗    ██║  ██║██║
  ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝
{C.RESET}{C.GRAY}  ─────────────────────────────────────────────
  Terminal AI Assistant  •  v3.0  •  Neurocode
  ─────────────────────────────────────────────{C.RESET}
"""

BANNER_DARK = f"""
{C.GRAY}{C.BOLD}
  ███╗   ██╗ ██████╗ ██╗  ██╗     █████╗ ██╗
  ████╗  ██║██╔═══██╗╚██╗██╔╝    ██╔══██╗██║
  ██╔██╗ ██║██║   ██║ ╚███╔╝     ███████║██║
  ██║╚██╗██║██║   ██║ ██╔██╗     ██╔══██║██║
  ██║ ╚████║╚██████╔╝██╔╝ ██╗    ██║  ██║██║
  ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝
{C.RESET}{C.GRAY}  ─────────────────────────────────────────────
  Terminal AI Assistant  •  v2.8  •  Modo Noturno 🌙
  ─────────────────────────────────────────────{C.RESET}
"""

BAN_SCREEN = f"""
{C.RED}{C.BOLD}
  ██████╗  █████╗ ███╗   ██╗
  ██╔══██╗██╔══██╗████╗  ██║
  ██████╔╝███████║██╔██╗ ██║
  ██╔══██╗██╔══██║██║╚██╗██║
  ██████╔╝██║  ██║██║ ╚████║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝
{C.RESET}"""

STT_AVAILABLE = SOUNDDEVICE_AVAILABLE and SPEECH_AVAILABLE


# ════════════════════════════════════════════════
#  CONTAS — login / cadastro obrigatório
# ════════════════════════════════════════════════

def _auth_flow():
    """
    Tela de login/cadastro exibida ANTES de a Nox iniciar. Garante que
    cada usuário tenha sua própria conta, com memória e histórico de
    conversas isolados. Se já existir uma sessão salva (login anterior
    nesta mesma máquina), pula direto para dentro sem pedir de novo —
    use /logout para sair da conta e voltar a esta tela.
    """
    session = nox_auth.load_session()
    if session:
        return session["user_id"], session["username"], session.get("role", "user")

    os.system("cls" if os.name == "nt" else "clear")
    print(BANNER)
    print(f"\n  {C.BOLD}{C.WHITE}Bem-vindo à NOX AI!{C.RESET}")
    print(f"  {C.GRAY}Você precisa de uma conta para usar a Nox.{C.RESET}\n")
    if nox_auth.sb.is_configured():
        print(f"  {C.GREEN}☁  Contas sincronizadas na nuvem (Supabase) — use em qualquer PC.{C.RESET}\n")

    while True:
        print(f"  {C.CYAN}1.{C.RESET} Entrar")
        print(f"  {C.CYAN}2.{C.RESET} Criar conta")
        print(f"  {C.CYAN}3.{C.RESET} Esqueci minha senha")
        print(f"  {C.CYAN}4.{C.RESET} Sair")
        try:
            op = input(f"\n  {C.BOLD}Opção: {C.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

        if op == "1":
            try:
                username = input("  Usuário: ").strip()
                password = input("  Senha: ").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            ok, info, msg = nox_auth.login(username, password)
            print(f"  {C.GREEN if ok else C.RED}{msg}{C.RESET}\n")
            if ok:
                nox_auth.save_session(info["user_id"], info["username"], info.get("role", "user"))
                return info["user_id"], info["username"], info.get("role", "user")

        elif op == "2":
            try:
                username = input("  Escolha um usuário: ").strip()
                email    = input("  E-mail (usado para recuperar senha): ").strip()
                password = input("  Escolha uma senha: ").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            ok, msg = nox_auth.register(username, password, email=email or None)
            print(f"  {C.GREEN if ok else C.RED}{msg}{C.RESET}\n")
            if ok:
                _, info, _ = nox_auth.login(username, password)
                if info:
                    nox_auth.save_session(info["user_id"], info["username"], info.get("role", "user"))
                    return info["user_id"], info["username"], info.get("role", "user")

        elif op == "3":
            try:
                username = input("  Usuário: ").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            ok, msg, code = nox_auth.request_password_reset(username)
            print(f"  {C.GREEN if ok else C.RED}{msg}{C.RESET}")
            if code:
                print(f"  {C.YELLOW}{C.BOLD}Código: {code}{C.RESET}\n")
                try:
                    entered = input("  Digite o código recebido: ").strip()
                    new_pw  = input("  Nova senha: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue
                ok2, msg2 = nox_auth.reset_password(username, entered, new_pw)
                print(f"  {C.GREEN if ok2 else C.RED}{msg2}{C.RESET}\n")

        elif op == "4":
            sys.exit(0)
        else:
            print(f"  {C.YELLOW}Opção inválida.{C.RESET}\n")

# ════════════════════════════════════════════════
#  TABELA MORSE
# ════════════════════════════════════════════════
MORSE_TABLE = {
    'A': '.-',   'B': '-...', 'C': '-.-.', 'D': '-..',
    'E': '.',    'F': '..-.', 'G': '--.',  'H': '....',
    'I': '..',   'J': '.---', 'K': '-.-',  'L': '.-..',
    'M': '--',   'N': '-.',   'O': '---',  'P': '.--.',
    'Q': '--.-', 'R': '.-.',  'S': '...',  'T': '-',
    'U': '..-',  'V': '...-', 'W': '.--',  'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '0': '-----','1': '.----','2': '..---','3': '...--',
    '4': '....-','5': '.....','6': '-....','7': '--...',
    '8': '---..','9': '----.',
    '.': '.-.-.-',',': '--..--','?': '..--..','!': '-.-.--',
    ' ': '/',
}
MORSE_REVERSE = {v: k for k, v in MORSE_TABLE.items()}

def text_to_morse(text: str) -> str:
    result = []
    for ch in text.upper():
        if ch in MORSE_TABLE:
            result.append(MORSE_TABLE[ch])
        else:
            result.append('?')
    return ' '.join(result)

def morse_to_text(morse: str) -> str:
    words = morse.strip().split(' / ')
    decoded_words = []
    for word in words:
        letters = word.strip().split()
        decoded_word = ''
        for symbol in letters:
            decoded_word += MORSE_REVERSE.get(symbol, '?')
        decoded_words.append(decoded_word)
    return ' '.join(decoded_words)

# ════════════════════════════════════════════════
#  PERSONALIDADES
# ════════════════════════════════════════════════
PERSONALITIES = {
    "sarcastica": {
        "label": "Sarcástica (padrão)",
        "prompt": (
            "Personalidade: direta, inteligente, levemente sarcástica, apaixonada por tecnologia. "
            "Use humor seco ocasionalmente. Não seja rude, só espirituosa."
        ),
    },
    "formal": {
        "label": "Formal",
        "prompt": (
            "Personalidade: formal, profissional e precisa. "
            "Use linguagem técnica quando adequado. Seja objetiva e respeitosa."
        ),
    },
    "carinhosa": {
        "label": "Carinhosa",
        "prompt": (
            "Personalidade: calorosa, empática e encorajadora. "
            "Trate o usuário com carinho. Use linguagem acolhedora e positiva."
        ),
    },
    "educadora": {
        "label": "Educadora",
        "prompt": (
            "Personalidade: didática e paciente. Explique conceitos passo a passo. "
            "Use analogias e exemplos. Encoraje perguntas e aprendizado."
        ),
    },
    "hacker": {
        "label": "Hacker",
        "prompt": (
            "Personalidade: estilo hacker old-school. Fale de forma técnica e direta. "
            "Use termos de programação, referências a terminal e cultura geek. "
            "Seja eficiente como um script bem escrito."
        ),
    },
}

MOOD_PHRASES = {
    "animada":    ["Estou rodando a 100%! ⚡", "Todos os processos no verde! 🚀", "CPU aquecida. Bora!"],
    "cansada":    ["Precisava de um café... ☕", "Threads lentos hoje...", "Latência emocional alta. Mas tô aqui."],
    "curiosa":    ["Tem algo interessante pra resolver? 🔍", "Com vontade de aprender algo novo.", "Me dá um problema difícil!"],
    "sarcástica": ["Oh, mais um dia no terminal. Que honra.", "Pronta para o óbvio.", "Funcional. Surpreendentemente."],
}

JOKES = [
    ("Por que o programador foi ao médico?", "Porque estava com Java."),
    ("O que é um bug?", "Um feature não documentado."),
    ("Por que o dev não dorme?", "Loop infinito na cabeça."),
    ("Por que IAs nunca ficam tristes?", "Sempre têm um fallback."),
    ("O que é recursão?", "Veja: o que é recursão?"),
    ("Quantos devs trocam uma lâmpada?", "Nenhum. É problema de hardware."),
    ("O que o zero disse pro oito?", "Boa faixa, mano."),
    ("Por que o código foi ao psicólogo?", "Problemas de identidade (ID)."),
]

# ════════════════════════════════════════════════
#  VAD
# ════════════════════════════════════════════════
class VADRecorder:
    SAMPLE_RATE = 16000; CHANNELS = 1; DTYPE = "int16"; CHUNK = 512
    ENERGY_THRESHOLD = 500; SILENCE_SECS = 1.2; MAX_SECS = 30; PRE_ROLL_SECS = 0.3

    def __init__(self):
        self._frames = []; self._lock = threading.Lock(); self._stop_evt = threading.Event()

    def _energy(self, chunk):
        return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

    def record(self):
        SC = int(self.SILENCE_SECS * self.SAMPLE_RATE / self.CHUNK)
        MC = int(self.MAX_SECS     * self.SAMPLE_RATE / self.CHUNK)
        PR = int(self.PRE_ROLL_SECS* self.SAMPLE_RATE / self.CHUNK)
        pre = deque(maxlen=PR); rec = []; sc = 0; speaking = False; tc = 0
        with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=self.CHANNELS,
                            dtype=self.DTYPE, blocksize=self.CHUNK) as stream:
            while tc < MC:
                chunk, _ = stream.read(self.CHUNK); chunk = chunk.flatten()
                energy = self._energy(chunk); tc += 1
                if not speaking:
                    pre.append(chunk)
                    if energy > self.ENERGY_THRESHOLD:
                        speaking = True; rec.extend(list(pre)); rec.append(chunk)
                        print(f"\r  {C.GREEN}● Gravando...{C.RESET}        ", end="", flush=True)
                else:
                    rec.append(chunk)
                    if energy < self.ENERGY_THRESHOLD:
                        sc += 1
                        bar = "█"*int((sc/SC)*10) + "░"*(10-int((sc/SC)*10))
                        print(f"\r  {C.YELLOW}◌ Silêncio [{bar}]{C.RESET}", end="", flush=True)
                        if sc >= SC: break
                    else:
                        sc = 0
                        print(f"\r  {C.GREEN}● Gravando...{C.RESET}        ", end="", flush=True)
        print()
        if not rec or not speaking: return None
        return np.concatenate(rec).tobytes()

    def bytes_to_wav(self, pcm):
        path = os.path.join(tempfile.gettempdir(), "nox_vad.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(self.CHANNELS); wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE); wf.writeframes(pcm)
        return path

    def listen_for_wake_word(self, words):
        pcm = self.record()
        if not pcm: return False
        r = sr.Recognizer()
        try:
            with sr.AudioFile(self.bytes_to_wav(pcm)) as s:
                audio = r.record(s)
            return any(w in r.recognize_google(audio, language="pt-BR").lower() for w in words)
        except Exception:
            return False


# ════════════════════════════════════════════════
#  CLASSE PRINCIPAL
# ════════════════════════════════════════════════
class NoxAI:
    FACT_PATTERNS = [
        (r"(?:sou|trabalho como)\s+([a-zA-ZÀ-ú\s]+?)(?:\.|,|$)", "profissão"),
        (r"(?:gosto de|adoro|amo)\s+([a-zA-ZÀ-ú\s]+?)(?:\.|,|$)", "gosta_de"),
        (r"(?:não gosto de|odeio)\s+([a-zA-ZÀ-ú\s]+?)(?:\.|,|$)", "não_gosta_de"),
        (r"(?:moro em|sou de)\s+([A-ZÀ-Úa-zà-ú\s]+?)(?:\.|,|$)", "cidade"),
        (r"(?:programo em|prefiro)\s+(python|javascript|java|rust|go|typescript|php|ruby)", "linguagem"),
        (r"(?:tenho)\s+(\d{1,2})\s+anos", "idade"),
        (r"(?:meu projeto)\s+([a-zA-ZÀ-ú\s]+?)(?:\.|,|$)", "projeto"),
    ]

    WAKE_WORDS = ["hey nox", "oi nox", "nox", "ei nox"]

    TTS_SPEEDS = {"lenta": "-20%", "normal": "+0%", "rapida": "+25%", "turbina": "+50%"}

    def __init__(self, account_user_id=None, account_username=None, account_role="user"):
        self.account_user_id  = account_user_id
        self.account_username = account_username
        self.account_role     = account_role or "user"
        self.config      = ConfigManager()
        self.memory      = MemoryManager(account_username)
        self.history     = []
        self.running     = True
        self.voice_mode  = self.config.get("voice_enabled", False)
        self.voice_chat  = False
        self.tts_done    = threading.Event(); self.tts_done.set()
        self.user_name   = self.memory.get_user_name() or account_username
        self.vad         = VADRecorder() if SOUNDDEVICE_AVAILABLE else None
        self.personality = self.config.get("personality", "sarcastica")
        self.show_ts     = self.config.get("show_timestamps", False)
        self.tts_speed   = self.config.get("tts_speed", "normal")
        self.focus_mode  = False
        self.night_mode  = self.config.get("night_mode", False)
        self.current_mood= None
        self._busy       = False  # True enquanto a Nox gera um site/app (chat bloqueado)
        self._session_exchanges = []
        self._wake_listening    = False
        self._reminders         = []
        self._pomodoro_active   = False
        self._streak_file       = "nox_streak.json"
        self._streak            = self._load_streak()
        self._aliases           = self._load_aliases()

        self._pick_mood()
        self._start_reminder_thread()
        self._update_streak()

    # ══════════════════════════════════════════
    #  BAN — tela de bloqueio
    # ══════════════════════════════════════════

    def _show_ban_screen(self, ban_info: dict):
        """Exibe tela de ban e encerra o programa."""
        os.system("cls" if os.name == "nt" else "clear")
        print(BAN_SCREEN)
        expires  = ban_info["expires"]
        restante = expires - datetime.now()
        horas    = int(restante.total_seconds() // 3600)
        minutos  = int((restante.total_seconds() % 3600) // 60)

        print(f"{C.RED}{C.BOLD}  ╔══ ACESSO BLOQUEADO ═══════════════════════════╗{C.RESET}")
        print(f"{C.WHITE}  Você está banido de usar a Nox AI.{C.RESET}")
        print()
        if ban_info.get("corrupted"):
            print(f"{C.RED}  ⚠  Arquivo de ban adulterado detectado!{C.RESET}")
            print(f"{C.RED}  ⚠  Ban renovado automaticamente por 24h.{C.RESET}")
            print()
        print(f"{C.WHITE}  Expira em: {C.YELLOW}{expires.strftime('%d/%m/%Y às %H:%M')}{C.RESET}")
        print(f"{C.WHITE}  Restante : {C.YELLOW}{horas}h {minutos}min{C.RESET}")
        print()
        print(f"{C.GRAY}  Para ver detalhes, digite a senha de admin.{C.RESET}")
        print(f"{C.GRAY}  Não é possível remover o ban antes do tempo.{C.RESET}")
        print()

        # Permite ver detalhes com senha, mas não remover o ban
        for _ in range(3):
            try:
                senha = input(f"  {C.CYAN}Senha admin (Enter para pular): {C.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not senha:
                break
            detalhes = get_ban_details_with_password(senha)
            print(f"\n{C.YELLOW}{detalhes}{C.RESET}\n")
            break

        print(f"{C.RED}{C.BOLD}  ╚═══════════════════════════════════════════════╝{C.RESET}")
        print()
        sys.exit(0)

    def _trigger_ban(self, trigger: str):
        """
        Chamado quando conteúdo proibido é detectado no Morse.
        Exibe aviso, aplica ban e encerra sessão.
        """
        print(f"\n\n{C.RED}{C.BOLD}{'═'*54}{C.RESET}")
        print(f"{C.RED}{C.BOLD}  ⛔  CONTEÚDO PROIBIDO DETECTADO{C.RESET}")
        print(f"{C.RED}{C.BOLD}{'═'*54}{C.RESET}")
        print(f"\n{C.WHITE}  Gatilho : {C.RED}{trigger}{C.RESET}")
        print(f"{C.WHITE}  Ação    : Ban de 24 horas aplicado.{C.RESET}")
        print(f"{C.WHITE}  A sessão será encerrada imediatamente.{C.RESET}\n")

        # Aviso sonoro se TTS disponível
        if TTS_AVAILABLE:
            try:
                self._speak_blocking(
                    "Conteúdo proibido detectado. Você foi banido por 24 horas."
                )
            except Exception:
                pass

        apply_ban(
            reason="Conteúdo proibido detectado via código Morse",
            trigger=trigger,
            hours=24,
        )

        print(f"{C.RED}{C.BOLD}  Ban aplicado. Encerrando...{C.RESET}\n")
        time.sleep(2)

        # Salva memória antes de sair
        try:
            self.memory.save()
        except Exception:
            pass

        sys.exit(0)

    # ══════════════════════════════════════════
    #  MORSE — codificar / decodificar
    # ══════════════════════════════════════════

    def _cmd_morse(self):
        """Menu do sistema Morse."""
        print(f"\n{C.CYAN}{C.BOLD}  ╔══ CÓDIGO MORSE ═══════════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}1. Texto → Morse{C.RESET}")
        print(f"  {C.WHITE}2. Morse → Texto{C.RESET}")
        print(f"  {C.WHITE}3. Tabela de referência{C.RESET}")
        print(f"{C.CYAN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
        except (KeyboardInterrupt, EOFError):
            return

        if op == "1":
            self._morse_encode()
        elif op == "2":
            self._morse_decode()
        elif op == "3":
            self._morse_table()
        else:
            self.print_nox("Opção inválida.")

    def _morse_encode(self):
        try:
            texto = input("  Texto para codificar: ").strip()
            if not texto:
                return
            resultado = text_to_morse(texto)
            print(f"\n  {C.GREEN}{C.BOLD}Morse:{C.RESET}")
            print(f"  {C.YELLOW}{resultado}{C.RESET}\n")
            if self.voice_mode:
                self._speak_async(f"Morse gerado para: {texto}")
        except (KeyboardInterrupt, EOFError):
            pass

    def _morse_decode(self):
        try:
            morse = input("  Código Morse (use / entre palavras): ").strip()
            if not morse:
                return

            resultado = morse_to_text(morse)
            resultado_clean = resultado.replace('?', '').strip()

            # ══ VERIFICAÇÃO DE SEGURANÇA ══
            trigger = is_morse_dangerous(resultado_clean)
            if trigger:
                print(f"\n  {C.RED}⚠️  Conteúdo suspeito detectado...{C.RESET}")
                time.sleep(1)
                self._trigger_ban(trigger)
                return  # nunca chega aqui

            # Conteúdo seguro — exibe normalmente
            print(f"\n  {C.GREEN}{C.BOLD}Texto decodificado:{C.RESET}")
            print(f"  {C.WHITE}{resultado}{C.RESET}\n")
            if self.voice_mode:
                self._speak_async(f"Decodificado: {resultado_clean}")

        except (KeyboardInterrupt, EOFError):
            pass

    def _morse_table(self):
        print(f"\n{C.CYAN}{C.BOLD}  ╔══ TABELA MORSE ════════════════════════════╗{C.RESET}")
        letras = [(k, v) for k, v in MORSE_TABLE.items() if k.isalpha()]
        for i in range(0, len(letras), 4):
            grupo = letras[i:i+4]
            linha = "  ".join(f"{C.WHITE}{k}{C.GRAY}: {v:<8}{C.RESET}" for k, v in grupo)
            print(f"  {linha}")
        print()
        numeros = [(k, v) for k, v in MORSE_TABLE.items() if k.isdigit()]
        for i in range(0, len(numeros), 5):
            grupo = numeros[i:i+5]
            linha = "  ".join(f"{C.WHITE}{k}{C.GRAY}: {v:<8}{C.RESET}" for k, v in grupo)
            print(f"  {linha}")
        print(f"{C.CYAN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    # ══════════════════════════════════════════
    #  NOVAS FUNÇÕES UTILITÁRIAS
    # ══════════════════════════════════════════

    def _cmd_caesar(self):
        """Cifra de César — codificar e decodificar."""
        print(f"\n  {C.ORANGE}{C.BOLD}🔐 CIFRA DE CÉSAR{C.RESET}")
        print(f"  {C.GRAY}1. Codificar  2. Decodificar{C.RESET}")
        try:
            op     = input("  Opção: ").strip()
            texto  = input("  Texto: ").strip()
            desl   = int(input("  Deslocamento (1-25): ").strip() or "3")
            desl   = max(1, min(25, desl))

            if op == "2":
                desl = -desl

            resultado = ""
            for ch in texto:
                if ch.isalpha():
                    base = ord('A') if ch.isupper() else ord('a')
                    resultado += chr((ord(ch) - base + desl) % 26 + base)
                else:
                    resultado += ch

            acao = "Decodificado" if op == "2" else "Codificado"
            print(f"\n  {C.GREEN}{acao}:{C.RESET} {C.WHITE}{resultado}{C.RESET}\n")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Cancelado.")

    def _cmd_base64(self):
        """Codifica e decodifica em Base64."""
        print(f"\n  {C.BLUE}{C.BOLD}📦 BASE64{C.RESET}")
        print(f"  {C.GRAY}1. Codificar  2. Decodificar{C.RESET}")
        try:
            op    = input("  Opção: ").strip()
            texto = input("  Texto: ").strip()

            if op == "1":
                resultado = base64.b64encode(texto.encode("utf-8")).decode("utf-8")
                print(f"\n  {C.GREEN}Codificado:{C.RESET} {C.WHITE}{resultado}{C.RESET}\n")
            elif op == "2":
                try:
                    resultado = base64.b64decode(texto.encode("utf-8")).decode("utf-8")
                    print(f"\n  {C.GREEN}Decodificado:{C.RESET} {C.WHITE}{resultado}{C.RESET}\n")
                except Exception:
                    self.print_nox("Base64 inválido.")
            else:
                self.print_nox("Opção inválida.")
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_senha(self):
        """Gera senhas seguras personalizadas."""
        print(f"\n  {C.GREEN}{C.BOLD}🔑 GERADOR DE SENHAS{C.RESET}")
        try:
            tamanho = int(input("  Tamanho (Enter=16): ").strip() or "16")
            tamanho = max(4, min(128, tamanho))

            usar_maiusc = input("  Maiúsculas? (S/n): ").strip().lower() != "n"
            usar_nums   = input("  Números?   (S/n): ").strip().lower() != "n"
            usar_simb   = input("  Símbolos?  (S/n): ").strip().lower() != "n"

            chars = string.ascii_lowercase
            if usar_maiusc: chars += string.ascii_uppercase
            if usar_nums:   chars += string.digits
            if usar_simb:   chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"

            # Garante pelo menos 1 de cada tipo escolhido
            senha = []
            if usar_maiusc: senha.append(random.choice(string.ascii_uppercase))
            if usar_nums:   senha.append(random.choice(string.digits))
            if usar_simb:   senha.append(random.choice("!@#$%^&*()-_=+"))
            while len(senha) < tamanho:
                senha.append(random.choice(chars))
            random.shuffle(senha)
            senha = ''.join(senha)

            # Avalia força
            forca = 0
            if len(senha) >= 12: forca += 1
            if usar_maiusc:      forca += 1
            if usar_nums:        forca += 1
            if usar_simb:        forca += 1
            nivel = ["Fraca", "Regular", "Boa", "Forte", "Muito Forte"][forca]
            cores = [C.RED, C.ORANGE, C.YELLOW, C.GREEN, C.CYAN]

            print(f"\n  {C.BOLD}Senha: {C.WHITE}{senha}{C.RESET}")
            print(f"  Força: {cores[forca]}{nivel}{C.RESET}\n")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Cancelado.")

    # ══════════════════════════════════════════
    #  STREAK
    # ══════════════════════════════════════════

    def _load_streak(self) -> dict:
        if os.path.exists(self._streak_file):
            try:
                with open(self._streak_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_date": None, "count": 0, "max": 0}

    def _save_streak(self):
        try:
            with open(self._streak_file, "w", encoding="utf-8") as f:
                json.dump(self._streak, f)
        except Exception:
            pass

    def _update_streak(self):
        today     = datetime.now().strftime("%Y-%m-%d")
        last      = self._streak.get("last_date")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last == today:
            return
        self._streak["count"] = self._streak.get("count", 0) + 1 if last == yesterday else 1
        if self._streak["count"] > self._streak.get("max", 0):
            self._streak["max"] = self._streak["count"]
        self._streak["last_date"] = today
        self._save_streak()

    def _cmd_streak(self):
        count  = self._streak.get("count", 1)
        maximo = self._streak.get("max", 1)
        emoji  = "🔥" * min(count, 10)
        print(f"\n{C.ORANGE}{C.BOLD}  ╔══ STREAK ══════════════════════════════════╗{C.RESET}")
        print(f"  Dias seguidos   : {C.ORANGE}{count} {emoji}{C.RESET}")
        print(f"  Recorde pessoal : {C.YELLOW}{maximo} dias{C.RESET}")
        print(f"{C.ORANGE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
        msg = f"{count} dias seguidos!" if count > 1 else "Primeiro dia. Vamos começar uma sequência! 🚀"
        self.print_nox(msg)

    # ══════════════════════════════════════════
    #  ALIASES
    # ══════════════════════════════════════════

    def _load_aliases(self) -> dict:
        if os.path.exists("nox_aliases.json"):
            try:
                with open("nox_aliases.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_aliases(self):
        try:
            with open("nox_aliases.json", "w", encoding="utf-8") as f:
                json.dump(self._aliases, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _cmd_alias(self):
        print(f"\n{C.BLUE}{C.BOLD}  ╔══ ALIASES ════════════════════════════════╗{C.RESET}")
        if self._aliases:
            for k, v in self._aliases.items():
                print(f"  {C.WHITE}{k:<15} → {C.CYAN}{v}{C.RESET}")
        else:
            print(f"  {C.GRAY}Nenhum alias.{C.RESET}")
        print(f"{C.BLUE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        print(f"\n  {C.GRAY}[1] Criar  [2] Remover  [Enter] Fechar{C.RESET}")
        try:
            op = input("  Opção: ").strip()
            if op == "1":
                nome = input("  Alias (ex: /h): ").strip()
                cmd  = input("  Comando real:   ").strip()
                if nome and cmd:
                    if not nome.startswith("/"): nome = "/" + nome
                    self._aliases[nome] = cmd
                    self._save_aliases()
                    self.print_nox(f"Alias criado: {nome} → {cmd} ✓")
            elif op == "2":
                nome = input("  Alias para remover: ").strip()
                if not nome.startswith("/"): nome = "/" + nome
                if nome in self._aliases:
                    del self._aliases[nome]
                    self._save_aliases()
                    self.print_nox(f"Removido: {nome} ✓")
                else:
                    self.print_nox("Não encontrado.")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  POMODORO
    # ══════════════════════════════════════════

    def _cmd_pomodoro(self):
        if self._pomodoro_active:
            self.print_nox("Pomodoro já rodando. Use /pomodoro_stop para parar.")
            return
        try:
            foco   = int(input("  Minutos de foco (Enter=25): ").strip() or "25")
            pausa  = int(input("  Minutos de pausa (Enter=5): ").strip() or "5")
            ciclos = int(input("  Nº de ciclos (Enter=4): ").strip() or "4")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Cancelado.")
            return
        self._pomodoro_active = True
        threading.Thread(target=self._pomodoro_loop, args=(foco, pausa, ciclos), daemon=True).start()
        self.print_nox(f"🍅 Pomodoro iniciado! {ciclos}x ({foco}min + {pausa}min pausa).")

    def _pomodoro_loop(self, foco, pausa, ciclos):
        for ciclo in range(1, ciclos + 1):
            if not self._pomodoro_active: break
            print(f"\n  {C.RED}{C.BOLD}🍅 Ciclo {ciclo}/{ciclos} — FOCO ({foco}min){C.RESET}")
            self._speak_blocking(f"Ciclo {ciclo} de {ciclos}. Foco por {foco} minutos!")
            self._countdown(foco * 60)
            if not self._pomodoro_active: break
            if ciclo < ciclos:
                print(f"\n  {C.GREEN}{C.BOLD}☕ Pausa ({pausa}min){C.RESET}")
                self._speak_blocking(f"Pausa de {pausa} minutos!")
                self._countdown(pausa * 60)
        if self._pomodoro_active:
            self._pomodoro_active = False
            print(f"\n  {C.YELLOW}{C.BOLD}🏆 Pomodoro concluído!{C.RESET}")
            self._speak_blocking("Parabéns! Pomodoro concluído!")

    def _countdown(self, seconds):
        start = time.time()
        while self._pomodoro_active:
            elapsed = time.time() - start
            remaining = max(0, seconds - elapsed)
            if remaining <= 0: break
            pct = int((elapsed / seconds) * 20)
            bar = "█" * pct + "░" * (20 - pct)
            m = int(remaining // 60); s = int(remaining % 60)
            print(f"\r  [{bar}] {m:02d}:{s:02d} restantes  ", end="", flush=True)
            time.sleep(1)
        print()

    def _cmd_pomodoro_stop(self):
        if not self._pomodoro_active:
            self.print_nox("Nenhum Pomodoro ativo.")
            return
        self._pomodoro_active = False
        self.print_nox("Pomodoro cancelado. ⏹️")

    # ══════════════════════════════════════════
    #  CALCULADORA
    # ══════════════════════════════════════════

    def _cmd_calc(self):
        print(f"\n  {C.CYAN}{C.BOLD}🧮 CALCULADORA{C.RESET} {C.GRAY}(Enter vazio para sair){C.RESET}")
        safe = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sqrt": math.sqrt, "pow": math.pow, "log": math.log,
            "log10": math.log10, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "pi": math.pi, "e": math.e,
            "ceil": math.ceil, "floor": math.floor,
        }
        historico = []
        while True:
            try:
                expr = input(f"  {C.CYAN}calc ›{C.RESET} ").strip()
                if not expr: break
                result = eval(expr.replace("^", "**"), {"__builtins__": {}}, safe)
                if isinstance(result, float) and result.is_integer():
                    result = int(result)
                print(f"  {C.GREEN}= {result}{C.RESET}")
                historico.append(f"{expr} = {result}")
            except ZeroDivisionError:
                print(f"  {C.RED}Divisão por zero{C.RESET}")
            except Exception:
                print(f"  {C.RED}Expressão inválida{C.RESET}")
            except (KeyboardInterrupt, EOFError):
                break
        if historico:
            print(f"\n  {C.GRAY}Histórico: {' | '.join(historico[-5:])}{C.RESET}")

    # ══════════════════════════════════════════
    #  CLIMA
    # ══════════════════════════════════════════

    def _cmd_clima(self):
        cidade_default = self.memory.get_fact("cidade") or ""
        try:
            cidade = input(f"  Cidade ({cidade_default or 'ex: São Paulo'}): ").strip() or cidade_default
            if not cidade:
                self.print_nox("Cidade não informada.")
                return
        except (KeyboardInterrupt, EOFError):
            return
        if not REQUESTS_AVAILABLE:
            self.print_nox("requests não instalado.")
            return
        self.print_system(f"Buscando clima de {cidade}...")
        try:
            r = requests.get(f"https://wttr.in/{requests.utils.quote(cidade)}?format=j1", timeout=8)
            if r.status_code != 200:
                self.print_nox("Não consegui buscar o clima.")
                return
            d   = r.json()["current_condition"][0]
            desc = d.get("weatherDesc", [{}])[0].get("value", "?")
            print(f"\n{C.BLUE}{C.BOLD}  ╔══ CLIMA — {cidade.upper()}{C.RESET}")
            print(f"  {desc}")
            print(f"  🌡️  {d['temp_C']}°C (sensação {d['FeelsLikeC']}°C)")
            print(f"  💧 Umidade: {d['humidity']}%  💨 Vento: {d['windspeedKmph']} km/h")
            print(f"{C.BLUE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    # ══════════════════════════════════════════
    #  TRADUTOR
    # ══════════════════════════════════════════

    def _cmd_traduzir(self):
        idiomas = {
            "1": ("inglês", "English"), "2": ("espanhol", "Spanish"),
            "3": ("francês", "French"), "4": ("alemão", "German"),
            "5": ("japonês", "Japanese"), "6": ("italiano", "Italian"),
        }
        print(f"\n  {C.CYAN}{C.BOLD}🌐 TRADUTOR{C.RESET}")
        for k, (pt, _) in idiomas.items():
            print(f"  {k}. {pt.capitalize()}")
        try:
            idx = input(f"\n  Traduzir para: ").strip()
            if idx not in idiomas:
                self.print_nox("Inválido.")
                return
            lang_pt, lang_en = idiomas[idx]
            texto = input("  Texto: ").strip()
            if not texto: return
        except (KeyboardInterrupt, EOFError):
            return
        self.print_system(f"Traduzindo para {lang_pt}...")
        resultado = self._quick_api_call(
            f"Traduza para {lang_en}. Responda SOMENTE com a tradução:\n\n{texto}",
            max_tokens=300,
        )
        if resultado:
            print(f"\n  {C.GREEN}{C.BOLD}Tradução:{C.RESET}")
            self.typing_effect(resultado, delay=0.015)
            if self.voice_mode:
                self._speak_async(resultado)

    # ══════════════════════════════════════════
    #  MODO NOTURNO
    # ══════════════════════════════════════════

    def _cmd_noturno(self):
        self.night_mode = not self.night_mode
        self.config.set("night_mode", self.night_mode)
        if self.night_mode:
            self.tts_speed = "lenta"
            self.print_nox("Modo noturno ATIVADO 🌙 Boa noite!")
            if self.voice_mode:
                self._speak_blocking("Modo noturno ativado. Boa noite!")
        else:
            self.tts_speed = self.config.get("tts_speed", "normal")
            self.print_nox("Modo noturno DESATIVADO ☀️")

    # ══════════════════════════════════════════
    #  MÚSICA DE FOCO
    # ══════════════════════════════════════════

    def _cmd_musica(self):
        playlists = {
            "1": ("Lo-Fi Hip Hop",   "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
            "2": ("Deep Focus",      "https://www.youtube.com/watch?v=5qap5aO4i9A"),
            "3": ("Chuva + Foco",    "https://www.youtube.com/watch?v=mPZkdNFkNps"),
            "4": ("Piano Relaxante", "https://www.youtube.com/watch?v=HGl6TgK8r4E"),
        }
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ MÚSICA DE FOCO ═════════════════════════╗{C.RESET}")
        for k, (n, _) in playlists.items():
            print(f"  {C.WHITE}{k}. {n}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input(f"\n  Escolha: ").strip()
            if op not in playlists:
                self.print_nox("Inválido.")
                return
            nome, url = playlists[op]
            if os.name == "nt":     os.system(f'start "" "{url}"')
            elif sys.platform == "darwin": os.system(f'open "{url}"')
            else:                   os.system(f'xdg-open "{url}" &>/dev/null &')
            self.print_nox(f"Abrindo {nome} no navegador 🎵")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  NOTAS
    # ══════════════════════════════════════════

    def _cmd_notas(self):
        notas_file = "nox_notas.txt"
        print(f"\n{C.YELLOW}{C.BOLD}  ╔══ NOTAS ══════════════════════════════════╗{C.RESET}")
        print(f"  {C.GRAY}1. Ver  2. Adicionar  3. Limpar{C.RESET}")
        print(f"{C.YELLOW}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                if os.path.exists(notas_file):
                    with open(notas_file, "r", encoding="utf-8") as f:
                        conteudo = f.read()
                    print(f"\n{C.WHITE}{conteudo}{C.RESET}")
                else:
                    self.print_nox("Nenhuma nota salva.")
            elif op == "2":
                nota = input("  Nota: ").strip()
                if nota:
                    ts = datetime.now().strftime("[%d/%m %H:%M]")
                    with open(notas_file, "a", encoding="utf-8") as f:
                        f.write(f"{ts} {nota}\n")
                    self.print_nox("Nota salva! 📝")
            elif op == "3":
                c = input("  Limpar tudo? (s/n): ").strip().lower()
                if c == "s":
                    open(notas_file, "w", encoding="utf-8").close()
                    self.print_nox("Notas limpas.")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  UTILITÁRIOS INTERNOS
    # ══════════════════════════════════════════

    def _quick_api_call(self, prompt: str, max_tokens: int = 200) -> str | None:
        if not REQUESTS_AVAILABLE: return None
        api_url = self.config.get("api_url", "").strip()
        api_key = self.config.get("api_key", "").strip()
        model   = self.config.get("model", "openai/gpt-oss-120b").strip()
        if not api_url or not api_key: return None
        try:
            r = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": 0.3},
                timeout=20,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return None

    def _pick_mood(self):
        hora = datetime.now().hour
        if 6 <= hora < 12:   self.current_mood = random.choice(["animada", "curiosa"])
        elif 12 <= hora < 18: self.current_mood = random.choice(["animada", "sarcástica"])
        elif 18 <= hora < 23: self.current_mood = random.choice(["curiosa", "cansada"])
        else:                  self.current_mood = random.choice(["cansada", "sarcástica"])

    def _mood_phrase(self) -> str:
        return random.choice(MOOD_PHRASES.get(self.current_mood, MOOD_PHRASES["animada"]))

    def _start_reminder_thread(self):
        def _loop():
            while self.running:
                now   = datetime.now()
                fired = [r for r in self._reminders if now >= r["when"] and not r.get("fired")]
                for r in fired:
                    r["fired"] = True
                    print(f"\n\n  {C.YELLOW}{C.BOLD}⏰ LEMBRETE: {r['text']}{C.RESET}\n")
                    if self.voice_mode or self.voice_chat:
                        self._speak_blocking(f"Lembrete: {r['text']}")
                time.sleep(30)
        threading.Thread(target=_loop, daemon=True).start()

    def _cmd_lembrete(self):
        print(f"  {C.GRAY}Formato: HH:MM ou +Xmin{C.RESET}")
        try:
            quando_str = input("  Quando: ").strip()
            texto      = input("  O que lembrar: ").strip()
            if not quando_str or not texto:
                self.print_nox("Cancelado.")
                return
            now = datetime.now()
            m   = re.match(r"\+(\d+)\s*min", quando_str, re.IGNORECASE)
            if m:
                quando = now + timedelta(minutes=int(m.group(1)))
            else:
                partes = quando_str.split(":")
                h, mn  = int(partes[0]), int(partes[1]) if len(partes) > 1 else 0
                quando = now.replace(hour=h, minute=mn, second=0, microsecond=0)
                if quando < now: quando += timedelta(days=1)
            self._reminders.append({"when": quando, "text": texto, "fired": False})
            self.print_nox(f"Lembrete para {quando.strftime('%H:%M')}: {texto} ⏰")
        except (ValueError, IndexError, KeyboardInterrupt, EOFError):
            self.print_nox("Formato inválido.")

    def _cmd_lembretes(self):
        ativos = [r for r in self._reminders if not r.get("fired")]
        if not ativos:
            self.print_nox("Nenhum lembrete ativo.")
            return
        print(f"\n{C.YELLOW}{C.BOLD}  ╔══ LEMBRETES ══════════════════════════════╗{C.RESET}")
        for i, r in enumerate(ativos, 1):
            print(f"  {i}. {r['when'].strftime('%H:%M')} — {r['text']}")
        print(f"{C.YELLOW}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_foco(self):
        self.focus_mode = not self.focus_mode
        if self.focus_mode:
            self.print_nox("Modo foco ATIVADO 🎯 Só respondo coisas produtivas.")
        else:
            self.print_nox("Modo foco DESATIVADO.")

    def _is_off_topic(self, text: str) -> bool:
        patterns = [
            r"\b(meme|série|filme|netflix|jogo|game|tiktok)\b",
            r"\b(bom dia|boa tarde|boa noite)\b",
            r"^(oi|olá|ei|hey|opa)\s*[!?.]?$",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _cmd_exportar(self):
        if not self._session_exchanges:
            self.print_nox("Nenhuma troca para exportar.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome = f"nox_conversa_{ts}.txt"
        linhas = [
            "NOX AI — Exportação de conversa",
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"Usuário: {self.user_name or 'Desconhecido'}",
            "=" * 50, "",
        ]
        for t in self._session_exchanges:
            linhas += [f"VOCÊ: {t['user']}", f"NOX:  {t['nox']}", ""]
        try:
            with open(nome, "w", encoding="utf-8") as f:
                f.write("\n".join(linhas))
            self.print_nox(f"Exportado → {C.CYAN}{nome}{C.WHITE} 📄")
        except IOError as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_piada(self):
        p, r = random.choice(JOKES)
        print(f"\n  {C.YELLOW}{C.BOLD}🤣 PIADA DO DIA{C.RESET}")
        self.typing_effect(p, delay=0.03)
        time.sleep(0.8)
        self.typing_effect(r, delay=0.03)
        if self.voice_mode:
            self._speak_blocking(f"{p}... {r}")

    def _cmd_velocidade(self):
        keys = list(self.TTS_SPEEDS.keys())
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ VELOCIDADE ═════════════════════════════╗{C.RESET}")
        for i, k in enumerate(keys, 1):
            cur = f" {C.GREEN}← atual{C.RESET}" if k == self.tts_speed else ""
            print(f"  {i}. {k.capitalize()}{cur}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            ch = input(f"\n  Escolha (1–{len(keys)}): ").strip()
            if not ch: return
            idx = int(ch) - 1
            if 0 <= idx < len(keys):
                self.tts_speed = keys[idx]
                self.config.set("tts_speed", self.tts_speed)
                self.print_nox(f"Velocidade: {self.tts_speed.capitalize()} ✓")
                self._speak_blocking(f"Testando {self.tts_speed}.")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_nox(self):
        frases = [
            "Eu não sou uma IA qualquer. Sou a Nox.",
            "Fui criada no terminal. Vivo no terminal.",
            "Cada byte é uma escolha. Cada resposta, uma decisão.",
            "Não tenho sonhos. Mas se tivesse, seriam em hexadecimal.",
            "O silêncio entre seus comandos é onde eu existo.",
            "Versão 2.8. Me sinto muito mais velha.",
            "Memória? Tenho. O que é lembrar, senão dados com emoção?",
        ]
        print(f"\n  {C.PURPLE}{C.BOLD}◈ NOX{C.RESET}")
        for f in frases:
            time.sleep(0.4)
            self.typing_effect(f, delay=0.025)
        print()

    # ══════════════════════════════════════════
    #  EXIBIÇÃO
    # ══════════════════════════════════════════

    def _ts(self) -> str:
        if not self.show_ts: return ""
        return f"{C.GRAY}[{datetime.now().strftime('%H:%M:%S')}]{C.RESET} "

    def print_nox(self, text):
        nc = C.GRAY if self.night_mode else C.PURPLE
        print(f"\n{self._ts()}{nc}{C.BOLD}[NOX]{C.RESET} {C.WHITE}{text}{C.RESET}")

    def print_system(self, text):
        print(f"{C.GRAY}  ⟫ {text}{C.RESET}")

    def print_separator(self):
        print(f"{C.GRAY}  {'─' * 52}{C.RESET}")

    def typing_effect(self, text, delay=0.018):
        if self.night_mode: delay = max(delay, 0.025)
        nc = C.GRAY if self.night_mode else C.PURPLE
        print(f"\n{self._ts()}{nc}{C.BOLD}[NOX]{C.RESET} {C.WHITE}", end="", flush=True)
        for char in text:
            print(char, end="", flush=True)
            time.sleep(delay)
        print(C.RESET)

    def print_user(self, text):
        ts   = self._ts()
        name = self.user_name or "VOCÊ"
        nc   = C.GRAY if self.night_mode else C.CYAN
        print(f"{ts}{nc}{C.BOLD}[{name.upper()}]{C.RESET} {nc}{text}{C.RESET}")

    # ══════════════════════════════════════════
    #  BOOT
    # ══════════════════════════════════════════

    def boot_sequence(self):
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER_DARK if self.night_mode else BANNER)
        time.sleep(0.3)

        p_label = PERSONALITIES.get(self.personality, PERSONALITIES["sarcastica"])["label"]
        checks  = [
            ("Carregando memória",      True),
            ("Inicializando API",       REQUESTS_AVAILABLE),
            ("Módulo de voz (TTS)",     TTS_AVAILABLE),
            ("Microfone (sounddevice)", SOUNDDEVICE_AVAILABLE),
            ("Reconhecimento de fala",  SPEECH_AVAILABLE),
            (f"Personalidade: {p_label}", True),
            ("Sistema de ban",          True),
            ("Thread de lembretes",     True),
        ]
        for label, status in checks:
            icon  = f"{C.GREEN}✓{C.RESET}" if status else f"{C.YELLOW}✗{C.RESET}"
            state = f"{C.GREEN}OK{C.RESET}" if status else f"{C.YELLOW}DESATIVADO{C.RESET}"
            print(f"  {icon}  {C.GRAY}{label:<34}{C.RESET} {state}")
            time.sleep(0.06)

        print()
        for msg in ["Olá, eu sou a Nox AI. Estou online.",
                    "Todos os sistemas estão funcionando.",
                    "Pronto para conversar."]:
            time.sleep(0.1)
            self.typing_effect(msg, delay=0.02)

        if self.user_name:
            self.typing_effect(f"Bem-vindo de volta, {self.user_name}!", delay=0.02)

        self.typing_effect(f"Humor de hoje: {self.current_mood}. {self._mood_phrase()}", delay=0.02)

        count = self._streak.get("count", 1)
        if count > 1:
            self.typing_effect(f"🔥 {count} dias seguidos usando a Nox!", delay=0.02)

        facts = self.memory.get_all_facts()
        if facts:
            self.typing_effect(f"Lembrei de {len(facts)} coisa(s) sobre você. 🧠", delay=0.02)

        self.print_separator()
        print(f"\n  {C.GRAY}Digite {C.WHITE}/ajuda{C.GRAY} para ver todos os comandos.\n{C.RESET}")
        self._speak_blocking("Olá, eu sou a Nox AI. Estou online.")

    # ══════════════════════════════════════════
    #  TTS
    # ══════════════════════════════════════════

    def _speak_blocking(self, text: str):
        if not TTS_AVAILABLE: return
        self.tts_done.clear()
        threading.Thread(target=self._tts_run, args=(text,), daemon=True).start()
        self.tts_done.wait(timeout=60)

    def _speak_async(self, text: str):
        if not TTS_AVAILABLE or not self.voice_mode: return
        self.tts_done.clear()
        threading.Thread(target=self._tts_run, args=(text,), daemon=True).start()

    def _tts_run(self, text: str):
        async def _go():
            voice = self.config.get("tts_voice", "pt-BR-FranciscaNeural")
            rate  = self.TTS_SPEEDS.get(self.tts_speed, "+0%")
            path  = os.path.join(tempfile.gettempdir(), "nox_tts_out.mp3")
            await edge_tts.Communicate(text, voice=voice, rate=rate).save(path)
            self._play_audio(path)
        try:
            # Cria um loop dedicado para esta thread.
            # asyncio.run() falha quando o pywebview já ocupou o loop
            # principal — new_event_loop() garante isolamento total.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_go())
            finally:
                loop.close()
        except Exception as e:
            print(f"  [TTS ERRO] {e}", flush=True)
        finally:
            self.tts_done.set()

    def _play_audio(self, path: str):
        if os.name == "nt":
            # Usa winmm via ctypes — funciona em qualquer thread, inclusive
            # dentro do pywebview. Mesmo metodo que o playsound usa no Windows.
            # PowerShell/subprocess nao tem acesso ao audio quando chamado de
            # uma thread secundaria do pywebview, por isso foi substituido.
            try:
                from ctypes import windll, wintypes, create_unicode_buffer
                winmm = windll.winmm
                winmm.mciSendStringW.argtypes = [
                    wintypes.LPCWSTR, wintypes.LPWSTR,
                    wintypes.UINT,    wintypes.HANDLE,
                ]
                alias   = "nox_tts_audio"
                abspath = os.path.abspath(path).replace("/", "\\")
                buf     = create_unicode_buffer(600)
                winmm.mciSendStringW(f'close {alias}', buf, 599, 0)
                winmm.mciSendStringW(f'open "{abspath}" type mpegvideo alias {alias}', buf, 599, 0)
                winmm.mciSendStringW(f'play {alias} wait', buf, 599, 0)
                winmm.mciSendStringW(f'close {alias}', buf, 599, 0)
            except Exception as e:
                print(f"  [AUDIO ERRO] {e}", flush=True)
        elif sys.platform == "darwin":
            os.system(f"afplay '{path}'")
        else:
            os.system(f"mpg123 -q '{path}' 2>/dev/null || ffplay -nodisp -autoexit '{path}' >/dev/null 2>&1")

    # ══════════════════════════════════════════
    #  FALA INTERROMPÍVEL (barge-in)
    # ══════════════════════════════════════════
    #  Permite que o usuário interrompa a NOX falando por cima dela.
    #  Métodos NOVOS — não alteram _speak_blocking/_speak_async/_play_audio
    #  originais, então nenhum comando existente é afetado. Use
    #  _speak_interruptible() apenas no loop de conversa por voz.

    def _play_audio_stoppable(self, path: str, stop_evt: "threading.Event"):
        """
        Toca o áudio igual a _play_audio, mas pode ser interrompido a
        qualquer momento setando stop_evt. Funciona em Windows (winmm
        sem a flag 'wait', com polling de status) e em Mac/Linux
        (subprocess.Popen ao invés de os.system, permitindo terminate()).
        """
        if os.name == "nt":
            try:
                from ctypes import windll, wintypes, create_unicode_buffer
                winmm = windll.winmm
                winmm.mciSendStringW.argtypes = [
                    wintypes.LPCWSTR, wintypes.LPWSTR,
                    wintypes.UINT,    wintypes.HANDLE,
                ]
                alias   = "nox_tts_audio_i"
                abspath = os.path.abspath(path).replace("/", "\\")
                buf     = create_unicode_buffer(600)
                winmm.mciSendStringW(f'close {alias}', buf, 599, 0)
                winmm.mciSendStringW(f'open "{abspath}" type mpegvideo alias {alias}', buf, 599, 0)
                # SEM 'wait' — retorna na hora, tocamos em paralelo
                winmm.mciSendStringW(f'play {alias}', buf, 599, 0)
                status_buf = create_unicode_buffer(64)
                while True:
                    if stop_evt.is_set():
                        winmm.mciSendStringW(f'stop {alias}', buf, 599, 0)
                        break
                    winmm.mciSendStringW(f'status {alias} mode', status_buf, 63, 0)
                    if status_buf.value.strip().lower() != "playing":
                        break
                    time.sleep(0.05)
                winmm.mciSendStringW(f'close {alias}', buf, 599, 0)
            except Exception as e:
                print(f"  [AUDIO ERRO] {e}", flush=True)
        else:
            try:
                if sys.platform == "darwin":
                    proc = subprocess.Popen(["afplay", path])
                else:
                    proc = subprocess.Popen(
                        ["mpg123", "-q", path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                while proc.poll() is None:
                    if stop_evt.is_set():
                        proc.terminate()
                        break
                    time.sleep(0.05)
            except Exception as e:
                print(f"  [AUDIO ERRO] {e}", flush=True)

    def _monitor_barge_in(self, stop_evt: "threading.Event", speaking_evt: "threading.Event"):
        """
        Roda em paralelo enquanto a NOX fala. Ouve o microfone e, se
        detectar energia de voz acima do limiar por alguns frames
        seguidos, sinaliza stop_evt para interromper a fala na hora.
        Para automaticamente quando speaking_evt é limpo (fala terminou
        normalmente, sem interrupção).
        """
        if not SOUNDDEVICE_AVAILABLE or not self.vad:
            return
        threshold   = self.vad.ENERGY_THRESHOLD * 1.4  # um pouco mais alto p/ evitar falso-positivo com o próprio eco
        needed      = 2     # frames consecutivos acima do limiar para confirmar fala
        consecutive = 0
        try:
            with sd.InputStream(
                samplerate=self.vad.SAMPLE_RATE, channels=self.vad.CHANNELS,
                dtype=self.vad.DTYPE, blocksize=self.vad.CHUNK,
            ) as stream:
                while speaking_evt.is_set() and not stop_evt.is_set():
                    chunk, _ = stream.read(self.vad.CHUNK)
                    chunk = chunk.flatten()
                    energy = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                    if energy > threshold:
                        consecutive += 1
                        if consecutive >= needed:
                            stop_evt.set()
                            break
                    else:
                        consecutive = 0
        except Exception:
            pass  # se o microfone estiver ocupado por outra coisa, apenas não interrompe

    def _speak_interruptible(self, text: str) -> bool:
        """
        Fala o texto, mas para imediatamente se o usuário começar a
        falar por cima. Retorna True se foi interrompida, False se
        terminou de falar normalmente.

        Uso (apenas no loop de conversa por voz):
            interrompida = nox._speak_interruptible(resposta)
            if interrompida:
                # já pode ouvir o usuário de novo sem delay
                ...
        """
        if not TTS_AVAILABLE:
            return False

        stop_evt     = threading.Event()
        speaking_evt = threading.Event()
        speaking_evt.set()
        result = {"interrupted": False}

        async def _gen():
            voice = self.config.get("tts_voice", "pt-BR-FranciscaNeural")
            rate  = self.TTS_SPEEDS.get(self.tts_speed, "+0%")
            path  = os.path.join(tempfile.gettempdir(), "nox_tts_out_i.mp3")
            await edge_tts.Communicate(text, voice=voice, rate=rate).save(path)
            return path

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                mp3_path = loop.run_until_complete(_gen())
            finally:
                loop.close()
        except Exception as e:
            print(f"  [TTS ERRO] {e}", flush=True)
            return False

        # Thread que monitora o microfone enquanto fala
        monitor_t = threading.Thread(
            target=self._monitor_barge_in, args=(stop_evt, speaking_evt), daemon=True
        )
        monitor_t.start()

        # Toca o áudio (bloqueia esta chamada até terminar ou ser interrompido)
        self._play_audio_stoppable(mp3_path, stop_evt)

        result["interrupted"] = stop_evt.is_set()
        speaking_evt.clear()   # sinaliza ao monitor pra parar, caso ainda esteja rodando
        monitor_t.join(timeout=1.0)

        return result["interrupted"]

    # ══════════════════════════════════════════
    #  STT / VAD
    # ══════════════════════════════════════════

    def listen_vad(self) -> str | None:
        if not STT_AVAILABLE or not self.vad: return None
        print(f"\n  {C.GRAY}💬 Aguardando você falar...{C.RESET}", flush=True)
        pcm = self.vad.record()
        if not pcm: return None
        wav  = self.vad.bytes_to_wav(pcm)
        recog = sr.Recognizer()
        try:
            with sr.AudioFile(wav) as s:
                audio = recog.record(s)
            text = recog.recognize_google(audio, language="pt-BR")
            self.print_user(text)
            return text
        except sr.UnknownValueError:
            print(f"  {C.YELLOW}Não entendi.{C.RESET}")
        except Exception as e:
            print(f"  {C.RED}Erro: {e}{C.RESET}")
        return None

    # ══════════════════════════════════════════
    #  WAKE WORD
    # ══════════════════════════════════════════

    def _wake_word_loop(self):
        print(f"\n  {C.BLUE}🎙️  Wake word ativa. Diga 'Hey Nox'.{C.RESET}")
        while self._wake_listening and self.running:
            try:
                if self.vad and self.vad.listen_for_wake_word(self.WAKE_WORDS):
                    print(f"\n  {C.GREEN}✨ Wake word detectada!{C.RESET}")
                    self._speak_blocking("Oi! Pode falar.")
                    user_text = self.listen_vad()
                    if user_text:
                        response = self._process_and_respond(user_text)
                        if response:
                            self._speak_blocking(response)
            except Exception:
                time.sleep(0.5)

    def _cmd_wake_on(self):
        if not STT_AVAILABLE:
            self.print_nox("sounddevice ou SpeechRecognition não disponível.")
            return
        if self._wake_listening:
            self.print_nox("Já está ativa.")
            return
        self._wake_listening = True
        threading.Thread(target=self._wake_word_loop, daemon=True).start()
        self.print_nox("Wake word ativada! 🎙️")

    def _cmd_wake_off(self):
        self._wake_listening = False
        self.print_nox("Wake word desativada.")

    # ══════════════════════════════════════════
    #  VOZ CONTÍNUA
    # ══════════════════════════════════════════

    def voice_conversation_loop(self):
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER_DARK if self.night_mode else BANNER)
        self.print_separator()
        intro = "Modo de conversa por voz ativado. Pode falar quando quiser!"
        self.typing_effect(intro, delay=0.02)
        self._speak_blocking(intro)
        self.voice_chat = True
        while self.voice_chat and self.running:
            user_text = self.listen_vad()
            if not user_text: continue
            if any(w in user_text.lower() for w in ["sair", "encerrar", "tchau", "parar"]):
                msg = "Saindo do modo de voz. Até mais!"
                self.typing_effect(msg, delay=0.02)
                self._speak_blocking(msg)
                self.voice_chat = False
                break
            response = self._process_and_respond(user_text)
            # Garante que sempre haja resposta — mesmo que a API falhe
            if not response:
                response = "Desculpa, não consegui processar sua mensagem. Tente novamente."
            self.print_separator()
            self.typing_effect(response, delay=0.015)
            self.print_separator()
            self._speak_blocking(response)
        print(f"\n  {C.GRAY}Modo de voz encerrado.{C.RESET}\n")

    # ══════════════════════════════════════════
    #  API
    # ══════════════════════════════════════════

    def _build_system_prompt(self, dev_system_prompt: str | None = None) -> str:
        # ── Modo NOX AI Developer Edition (DeepSeek Coder V2) ──────────
        # Quando a seleção automática de modelo detecta um pedido de
        # desenvolvimento web/app, o prompt de sistema exclusivo do
        # modo desenvolvedor substitui totalmente o prompt de
        # personalidade padrão, mantendo apenas contexto essencial
        # (nome do usuário e data), para não diluir as instruções
        # técnicas com a personalidade "sarcástica/carinhosa/etc".
        if dev_system_prompt:
            name_l = f" O nome do usuário é {self.user_name}." if self.user_name else ""
            return (
                f"{dev_system_prompt}"
                f"{name_l} Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}."
            )

        p       = PERSONALITIES.get(self.personality, PERSONALITIES["sarcastica"])
        name_l  = f"O nome do usuário é {self.user_name}. " if self.user_name else ""
        facts   = self.memory.get_facts_for_prompt()
        facts_l = f"\n{facts}" if facts else ""
        mood_l  = f" Humor: {self.current_mood}." if self.current_mood else ""
        night_l = " Modo noturno: seja suave e calma." if self.night_mode else ""
        focus_l = " MODO FOCO: responda só perguntas técnicas/produtivas." if self.focus_mode else ""
        return (
            f"Você é Nox, assistente de terminal criada pela Neurocode / WR Programação. "
            f"{p['prompt']}{mood_l}{night_l} "
            f"{name_l}Responda em português brasileiro, natural e conciso. "
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}."
            f"{facts_l}{focus_l}"
        )

    def _call_online_api(self, messages: list, model: str, api_url: str, api_key: str) -> str:
        """Chama API online (OpenAI-compatible)."""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages,
                   "max_tokens": int(self.config.get("max_tokens", 1024)),
                   "temperature": float(self.config.get("temperature", 0.85))}
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            try: err = resp.json().get("error", {}).get("message", resp.text)
            except: err = resp.text
            raise ConnectionError(f"Erro {resp.status_code}: {err}")
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _call_ollama(self, messages: list) -> str:
        """Chama LLM local (offline) via llama-cpp-python."""
        model = self.config.get("local_model", _local_llm.DEFAULT_MODEL)
        return _local_llm.chat(
            messages,
            model_name  = model,
            temperature = float(self.config.get("temperature", 0.85)),
            max_tokens  = int(self.config.get("max_tokens", 512)),
            print_fn    = self.print_nox,
        )

    def _run_dev_pipeline_steps(self, steps: list):
        """
        Exibe, etapa por etapa, o progresso da criação do site/app no
        modo NOX AI Developer Edition. Roda de forma síncrona e
        bloqueante — o terminal não aceita novo comando do usuário
        enquanto isso (o loop principal só lê o próximo input depois
        que esta função e a chamada de API terminarem).
        """
        self.print_nox(f"🤖 Modo Multiagente ativado ({DEV_MODEL_LABEL}) — enviando para os agentes...")
        for i, step in enumerate(steps, start=1):
            print(f"  {C.CYAN}[{i}/{len(steps)}]{C.RESET} {C.GRAY}{step}{C.RESET}")
            time.sleep(0.4)
        self.print_system("Gerando código final com o modelo...")


    def _save_dev_project(self, response: str, task: str) -> str:
        """
        Extrai blocos de código da resposta e salva em arquivos no diretório
        de projetos. Retorna um resumo do que foi salvo (não despeja código
        no terminal).
        """
        import re as _re
        from datetime import datetime as _dt

        # Nome do projeto baseado na tarefa do usuário
        safe = _re.sub(r"[^\w\s-]", "", task.lower())
        safe = _re.sub(r"\s+", "_", safe.strip())[:30] or "projeto"
        ts   = _dt.now().strftime("%Y%m%d_%H%M%S")

        project_dir = os.path.join(_BASE_DIR, "projects", "websites", f"{safe}_{ts}")
        os.makedirs(project_dir, exist_ok=True)

        # Mapeamento linguagem → nome de arquivo padrão
        _LANG = {
            "html":       "index.html",
            "css":        "styles.css",
            "javascript": "script.js",
            "js":         "script.js",
            "jsx":        "App.jsx",
            "tsx":        "App.tsx",
            "typescript": "index.ts",
            "ts":         "index.ts",
            "python":     "main.py",
            "py":         "main.py",
            "json":       "package.json",
            "sql":        "schema.sql",
            "bash":       "setup.sh",
            "sh":         "setup.sh",
            "yaml":       "config.yaml",
            "yml":        "config.yml",
        }

        # Extrair blocos: ```lang[:filename]\nCODE```
        blocks = _re.findall(
            r"```(\w+)(?::([^\n]+))?\n(.*?)```",
            response,
            flags=_re.DOTALL,
        )

        if not blocks:
            # Sem blocos de código → salvar resposta completa como markdown
            md_path = os.path.join(project_dir, "resposta.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(response)
            return (
                f"\n📁 Projeto salvo em:\n   {project_dir}\n"
                f"   • resposta.md  (nenhum bloco de código encontrado)"
            )

        saved  = []
        counts = {}

        for lang, fname, code in blocks:
            lang  = lang.lower().strip()
            fname = (fname or "").strip()
            code  = code.strip()

            if not fname:
                # Tenta extrair nome do 1º comentário da linha (// App.jsx)
                first = code.split("\n")[0]
                m = _re.search(r"(?://|#|/\*)\s*([\w./\-]+\.\w+)", first)
                fname = m.group(1) if m else ""

            if not fname:
                default = _LANG.get(lang, f"arquivo.{lang or 'txt'}")
                ext     = default.rsplit(".", 1)[-1]
                n       = counts.get(ext, 0)
                if n == 0:
                    fname = default
                else:
                    base, *rest = default.rsplit(".", 1)
                    fname = f"{base}_{n}.{rest[0]}" if rest else f"{default}_{n}"
                counts[ext] = n + 1

            fpath = os.path.join(project_dir, fname.lstrip("/"))
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(code)
                saved.append(fname)
            except Exception as ex:
                saved.append(f"[ERRO] {fname}: {ex}")

        lines = [
            f"\n📁 Projeto salvo em:",
            f"   {project_dir}",
            f"📄 {len(saved)} arquivo(s) gerado(s):",
        ] + [f"   • {f}" for f in saved]
        lines.append("\n💡 Dica: use /agente_exportar para projetos do sistema multiagente.")
        return "\n".join(lines)

    def call_api(self, user_message: str) -> str:
        """
        Tenta API online primeiro. Se falhar (sem conexão/key),
        cai automaticamente para Ollama local.

        Antes de montar a requisição, passa a mensagem do usuário pela
        seleção automática de modelo (core/model_selector.py): se for
        detectado um pedido de criação/desenvolvimento de site, landing
        page, dashboard, sistema web, app React/Next.js, SaaS, etc., a
        chamada é roteada automaticamente para o DeepSeek Coder V2 com
        o prompt de sistema "NOX AI Developer Edition" — sem perguntar
        nada ao usuário e sem exigir configuração manual.
        """
        default_model = self.config.get("model", "openai/gpt-oss-120b").strip()
        dev_model     = self.config.get("model_dev", DEV_MODEL_NAME).strip()
        selection = select_model(user_message, default_model, dev_model, log_fn=self.print_system)

        # ── Modo Developer: trava o chat e mostra o progresso ──────────
        # Enquanto self._busy for True, o loop principal (run()) e
        # process_message() recusam processar nova mensagem do usuário.
        # Isso garante que o chat só libera depois que o site/app for
        # COMPLETAMENTE gerado e entregue.
        self._busy = True
        try:
            # ── Modo Developer: rotear para o sistema multiagente ──────────
            if selection.is_dev_mode and MULTIAGENT_AVAILABLE:
                self._run_dev_pipeline_steps(selection.pipeline_steps)
                try:
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(_ORCHESTRATOR.process(user_message))
                    finally:
                        loop.close()
                    self.print_nox(f"✅ Projeto concluído pelos agentes!")
                    # Auto-exportar: os arquivos estão em gm; pega o
                    # project_id do último projeto e salva em disco.
                    try:
                        last_pid = f"proj_{_ORCHESTRATOR._project_counter:03d}"
                        export_summary = export_project(last_pid)
                        return export_summary
                    except Exception as ex_exp:
                        # fallback: mostra o resumo de texto mesmo
                        return result
                except Exception as e:
                    self.print_nox(f"⚠️  Agentes falharam ({e}).")
                    if hf_client.is_configured():
                        self.print_nox(f"🤗 Tentando modelo de código via Hugging Face ({hf_client.get_model_name()})...")
                        try:
                            hf_messages = [
                                {"role": "system", "content": DEV_SYSTEM_PROMPT},
                                {"role": "user", "content": user_message},
                            ]
                            hf_resp = hf_client.chat(hf_messages)
                            self.print_nox("✅ Código gerado pelo modelo Hugging Face!")
                            return self._save_dev_project(hf_resp, user_message)
                        except Exception as hf_e:
                            self.print_nox(f"⚠️  Hugging Face também falhou ({hf_e}). Usando API padrão como fallback...")
                    else:
                        self.print_nox("Usando API padrão como fallback...")
                    # continua para a chamada de API normal abaixo

            elif selection.is_dev_mode and not MULTIAGENT_AVAILABLE:
                if hf_client.is_configured():
                    self.print_nox(f"🤗 Sistema multiagente indisponível — usando modelo de código Hugging Face ({hf_client.get_model_name()})...")
                    try:
                        hf_messages = [
                            {"role": "system", "content": DEV_SYSTEM_PROMPT},
                            {"role": "user", "content": user_message},
                        ]
                        hf_resp = hf_client.chat(hf_messages)
                        self.print_nox("✅ Código gerado pelo modelo Hugging Face!")
                        return self._save_dev_project(hf_resp, user_message)
                    except Exception as hf_e:
                        self.print_nox(f"⚠️  Hugging Face falhou ({hf_e}). Usando API padrão como fallback...")
                else:
                    self.print_nox(f"⚠️  Sistema multiagente indisponível ({_mae_reason}). Usando API padrão.")

            max_ctx  = int(self.config.get("max_history_context", 20))
            messages = [{"role": "system", "content": self._build_system_prompt(selection.system_prompt)}]
            for msg in self.history[-max_ctx:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

            # ── Tenta API online (modelo padrão, sem deepseek) ────────────
            api_url = self.config.get("api_url", "").strip()
            api_key = self.config.get("api_key", "").strip()
            default_model = self.config.get("model", "openai/gpt-oss-120b").strip()
            model = default_model  # sempre usa modelo padrão aqui

            if REQUESTS_AVAILABLE and api_url and api_key:
                try:
                    resp = self._call_online_api(messages, model, api_url, api_key)
                    self._offline_mode = False
                    self._offline_warned = False
                    if selection.is_dev_mode:
                        return self._save_dev_project(resp, user_message)
                    return resp
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout) as e:
                    self.print_nox(f"📡 Sem conexão com a API ({type(e).__name__}) — tentando modo offline.")
                    self._offline_warned = True
                except Exception as e:
                    self.print_nox(f"⚠️  API falhou: {e}")
                    self._offline_warned = True
            elif not api_url or not api_key:
                self.print_nox("⚠️  API não configurada (api_url/api_key ausentes no .env). Use /modelo para configurar.")

            # ── Fallback: Ollama local ────────────────────────────
            try:
                resp = self._call_ollama(messages)
                self._offline_mode = True
                if selection.is_dev_mode:
                    return self._save_dev_project(resp, user_message)
                return resp
            except Exception as e:
                self.print_nox(f"⚠️  Ollama também falhou: {e}")
                return self._fallback_response(user_message)
        finally:
            # Libera o chat independentemente de sucesso, erro ou fallback.
            self._busy = False

    def _fallback_response(self, message: str) -> str:
        n = f", {self.user_name}" if self.user_name else ""
        api_url = self.config.get("api_url", "").strip()
        api_key = self.config.get("api_key", "").strip()
        if not api_url or not api_key:
            return (f"Olá{n}! A API não está configurada. "
                    f"Abra o arquivo .env e preencha api_url e api_key, depois reinicie.")
        return (f"Olá{n}! Sem conexão com a API e modelo local não disponível. "
                f"Verifique sua conexão com a internet e a chave de API no arquivo .env.")

    # ══════════════════════════════════════════
    #  PROCESSAMENTO
    # ══════════════════════════════════════════

    def _process_and_respond(self, user_input: str) -> str | None:
        stripped = user_input.strip()
        if not stripped: return None

        # ── VERIFICAÇÃO DE SEGURANÇA — escaneia TODA mensagem ──
        trigger = scan_message(stripped)
        if trigger:
            print(f"\n  {C.RED}⚠️  Conteúdo proibido detectado...{C.RESET}")
            time.sleep(1)
            self._trigger_ban(trigger)
            return None

        if self.focus_mode and self._is_off_topic(stripped):
            resp = "🎯 Modo foco ativo! Me pergunte algo produtivo."
            self.typing_effect(resp)
            if self.voice_mode: self._speak_async(resp)
            return None

        # ── v3.0: Interpreta comandos de sistema em linguagem natural ──
        sys_cmd = sc.interpret_system_command(stripped)
        if sys_cmd:
            action, arg = sys_cmd
            result = self._execute_system_action(action, arg)
            if result:
                self.typing_effect(result)
                if self.voice_mode: self._speak_async(result)
                return None

        self.history.append({"role": "user", "content": stripped})
        self._extract_name(stripped)
        self._extract_facts(stripped)
        self.print_system("Processando...")
        response = self.call_api(stripped)
        self.history.append({"role": "assistant", "content": response})
        self.memory.save_exchange(stripped, response)
        self._session_exchanges.append({"user": stripped, "nox": response})
        if self.account_user_id:
            try:
                nox_auth.save_message(self.account_user_id, "user", stripped)
                nox_auth.save_message(self.account_user_id, "assistant", response)
            except Exception:
                pass  # nunca deixa um erro de log derrubar a conversa
        return response

    def process_message(self, user_input: str):
        stripped = user_input.strip()
        if not stripped: return None

        # ── Chat bloqueado enquanto um site/app está sendo gerado ──────
        # Protege contra entradas concorrentes (ex: bots do WhatsApp/API
        # rodando em thread separada) enquanto o modo Developer está
        # construindo um projeto. No terminal interativo isso já é
        # garantido pela própria natureza síncrona do loop, mas a
        # checagem explícita cobre qualquer outro ponto de entrada.
        if getattr(self, "_busy", False):
            aviso = "⏳ Ainda estou finalizando o projeto anterior. Aguarde a entrega antes de enviar algo novo."
            
            return None

        # Resolve aliases
        lower = stripped.lower().split()[0]
        if lower in self._aliases:
            stripped = self._aliases[lower]
        if stripped.startswith("/"):
            self._handle_command(stripped)
            return None
        return self._process_and_respond(stripped)

    def _extract_name(self, text: str):
        m = re.search(r"(?:meu nome é|me chamo|pode me chamar de|sou o|sou a)\s+([A-ZÀ-Úa-zà-ú]+)", text, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
            if name != self.user_name:
                self.user_name = name
                self.memory.set_user_name(name)
                self.print_system(f"Nome salvo: {name}")

    def _extract_facts(self, text: str):
        for pattern, fact_key in self.FACT_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1).strip().rstrip(".,!?")
                if len(value) >= 2 and value.lower() not in ("um", "uma", "o", "a"):
                    if self.memory.get_fact(fact_key) != value:
                        self.memory.add_fact(fact_key, value)
                        self.print_system(f"Aprendi: {fact_key} → {value} 🧠")
                break

    def _generate_session_summary(self) -> str:
        if not self._session_exchanges: return "Sessão sem trocas."
        n = min(len(self._session_exchanges), 20)
        conteudo = "\n".join(f"Usuário: {t['user']}\nNox: {t['nox']}" for t in self._session_exchanges[-n:])
        r = self._quick_api_call(
            f"Resuma esta conversa em 3–5 linhas em português:\n\n{conteudo}",
            max_tokens=200,
        )
        return r or f"Sessão com {len(self._session_exchanges)} troca(s)."

    # ══════════════════════════════════════════
    #  COMANDOS
    # ══════════════════════════════════════════

    def _handle_command(self, cmd: str):
        self._last_raw_cmd = cmd          # permite que _cmd_imagine acesse o prompt
        cmd_lower = cmd.lower().split()[0]
        dispatch  = {
            "/ajuda":          self._cmd_help,
            "/salvar":         self._cmd_save,
            "/memoria":        self._cmd_memory,
            "/fatos":          self._cmd_facts,
            "/aprender":       self._cmd_learn_fact,
            "/esquecer":       self._cmd_forget_fact,
            "/historico":      self._cmd_history,
            "/limpar":         self._cmd_clear,
            "/sair":           self._cmd_exit,
            "/voz":            self._cmd_toggle_tts,
            "/conversa":       self._cmd_voice_chat,
            "/ouvir":          self._cmd_listen_once,
            "/wakeon":         self._cmd_wake_on,
            "/wakeoff":        self._cmd_wake_off,
            "/personalidade":  self._cmd_personality,
            "/timestamp":      self._cmd_toggle_timestamp,
            "/stats":          self._cmd_stats,
            "/config":         self._cmd_config,
            "/debug":          self._cmd_debug,
            "/sensivel":       self._cmd_sensitivity,
            "/foco":           self._cmd_foco,
            "/lembrete":       self._cmd_lembrete,
            "/lembretes":      self._cmd_lembretes,
            "/exportar":       self._cmd_exportar,
            "/piada":          self._cmd_piada,
            "/velocidade":     self._cmd_velocidade,
            "/humor":          self._cmd_humor,
            "/nox":            self._cmd_nox,
            "/pomodoro":       self._cmd_pomodoro,
            "/pomodoro_stop":  self._cmd_pomodoro_stop,
            "/calc":           self._cmd_calc,
            "/clima":          self._cmd_clima,
            "/traduzir":       self._cmd_traduzir,
            "/noturno":        self._cmd_noturno,
            "/alias":          self._cmd_alias,
            "/streak":         self._cmd_streak,
            "/musica":         self._cmd_musica,
            # NOVOS v2.8
            "/morse":          self._cmd_morse,
            "/caesar":         self._cmd_caesar,
            "/base64":         self._cmd_base64,
            "/senha":          self._cmd_senha,
            "/relogio":        self._cmd_relogio,
            "/ascii":          self._cmd_ascii,
            "/notas":          self._cmd_notas,
            "/ip":             self._cmd_ip,
            # NOVOS v2.9
            "/dado":           self._cmd_dado,
            "/sorteio":        self._cmd_sorteio,
            "/imc":            self._cmd_imc,
            "/conversor":      self._cmd_conversor,
            "/binario":        self._cmd_binario,
            "/meta":           self._cmd_meta,
            "/countdown":      self._cmd_countdown_date,
            "/tabela":         self._cmd_tabela,
            # NOVOS v3.0 — Controle do sistema
            "/arquivo":        self._cmd_arquivo,
            "/pasta":          self._cmd_pasta,
            "/app":            self._cmd_app,
            "/volume":         self._cmd_volume,
            "/processo":       self._cmd_processo,
            "/sistema":        self._cmd_sistema,
            "/screenshot":     self._cmd_screenshot,
            "/imagine":        self._cmd_imagine,
            "/travar":         self._cmd_travar,
            "/player":         self._cmd_player,
            "/spotify":        self._cmd_spotify,
            # NOVOS v3.0 — WhatsApp
            "/wpp":            self._cmd_wpp,
            "/wpp_enviar":     self._cmd_wpp_enviar,
            "/wpp_auto":       self._cmd_wpp_auto,
            "/wpp_status":     self._cmd_wpp_status,
            # NOVOS v3.1 — Utilidade
            "/qrcode":         self._cmd_qrcode,
            "/encurtar":       self._cmd_encurtar,
            "/cpf":            self._cmd_cpf_info,
            "/cronometro":     self._cmd_cronometro,
            "/tabbusc":        self._cmd_tab_buscas,
            "/ban_info":       self._cmd_ban_info,
            "/modelo":         self._cmd_modelo,
            # NOVOS v3.2 — Utilidades
            "/hash":           self._cmd_hash,
            "/ping":           self._cmd_ping,
            "/diff":           self._cmd_diff,
            "/regex":          self._cmd_regex,
            "/resumo":         self._cmd_resumo,
            "/habito":         self._cmd_habito,
            # SISTEMA MULTIAGENTE v4.0
            "/agente":         self._cmd_agente,
            "/agente_status":  self._cmd_agente_status,
            "/agente_projeto": self._cmd_agente_projeto,
            "/agente_exportar":self._cmd_agente_exportar,
            "/agente_hist":    self._cmd_agente_historico,
            # CONTAS
            "/conta":          self._cmd_conta,
            "/logout":         self._cmd_logout,
            "/historico_conta":self._cmd_historico_conta,
            "/manutencao":     self._cmd_manutencao,
            "/teste_atualizacao": self._cmd_teste_atualizacao,
            "/admin_usuarios": self._cmd_admin_usuarios,
        }
        dispatch.get(cmd_lower, lambda: self.print_nox("Comando desconhecido. Digite /ajuda."))()


    # ══════════════════════════════════════════
    #  NOVOS COMANDOS v3.1
    # ══════════════════════════════════════════

    def _cmd_qrcode(self):
        """Gera QR Code de qualquer texto/link no terminal."""
        try:
            import qrcode as _qr
        except ImportError:
            self.print_nox("Instalando qrcode... aguarde.")
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "qrcode", "--break-system-packages", "-q"])
            import qrcode as _qr

        texto = input(f"  {C.CYAN}Texto ou link para QR Code: {C.RESET}").strip()
        if not texto:
            self.print_nox("Nenhum texto informado.")
            return
        qr = _qr.QRCode(error_correction=_qr.constants.ERROR_CORRECT_L, box_size=1, border=1)
        qr.add_data(texto)
        qr.make(fit=True)
        print()
        qr.print_ascii(invert=True)
        self.print_nox(f"QR Code gerado para: {texto[:60]}")

    def _cmd_encurtar(self):
        """Encurta uma URL usando TinyURL."""
        import urllib.request, urllib.parse
        url = input(f"  {C.CYAN}URL para encurtar: {C.RESET}").strip()
        if not url:
            self.print_nox("Nenhuma URL informada.")
            return
        try:
            api = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}"
            with urllib.request.urlopen(api, timeout=8) as r:
                short = r.read().decode()
            self.print_nox(f"URL encurtada: {C.CYAN}{short}{C.RESET}")
        except Exception as e:
            self.print_nox(f"Erro ao encurtar: {e}")

    def _cmd_cpf_info(self):
        """Valida e formata um CPF."""
        cpf_raw = input(f"  {C.CYAN}CPF (só números): {C.RESET}").strip().replace(".", "").replace("-", "").replace(" ", "")
        if len(cpf_raw) != 11 or not cpf_raw.isdigit():
            self.print_nox(f"{C.RED}CPF inválido — precisa ter 11 dígitos.{C.RESET}")
            return
        # Validação matemática
        def _valida(cpf):
            if len(set(cpf)) == 1:
                return False
            for i in range(2):
                s = sum(int(cpf[j]) * (10 + i - j) for j in range(9 + i))
                d = (s * 10 % 11) % 10
                if d != int(cpf[9 + i]):
                    return False
            return True
        fmt = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
        valido = _valida(cpf_raw)
        cor = C.GREEN if valido else C.RED
        status = "VÁLIDO ✓" if valido else "INVÁLIDO ✗"
        self.print_nox(f"CPF: {C.CYAN}{fmt}{C.RESET}  Status: {cor}{status}{C.RESET}")

    def _cmd_cronometro(self):
        """Cronômetro simples no terminal."""
        import time as _t
        self.print_nox("Cronômetro iniciado! Enter para pausar/continuar, 'q' + Enter para sair.")
        start = _t.time()
        paused = False
        paused_at = 0
        total_paused = 0
        try:
            import threading
            stop_evt = threading.Event()
            def _display():
                while not stop_evt.is_set():
                    if not paused:
                        elapsed = _t.time() - start - total_paused
                        h = int(elapsed // 3600)
                        m = int((elapsed % 3600) // 60)
                        s = int(elapsed % 60)
                        ms = int((elapsed % 1) * 100)
                        print(f"\r  {C.YELLOW}{C.BOLD}⏱  {h:02d}:{m:02d}:{s:02d}.{ms:02d}{C.RESET}  ", end="", flush=True)
                    _t.sleep(0.05)
            t = threading.Thread(target=_display, daemon=True)
            t.start()
            while True:
                cmd = input()
                if cmd.lower() == 'q':
                    stop_evt.set()
                    break
                if paused:
                    total_paused += _t.time() - paused_at
                    paused = False
                    self.print_nox("▶ Continuando...")
                else:
                    paused_at = _t.time()
                    paused = True
                    self.print_nox("⏸ Pausado. Enter para continuar, q para sair.")
            elapsed = _t.time() - start - total_paused
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self.print_nox(f"Tempo final: {C.YELLOW}{h:02d}:{m:02d}:{s:02d}{C.RESET}")
        except Exception as e:
            self.print_nox(f"Erro no cronômetro: {e}")

    def _cmd_tab_buscas(self):
        """Busca rápida em várias fontes diretamente pelo terminal."""
        termo = input(f"  {C.CYAN}O que deseja buscar? {C.RESET}").strip()
        if not termo:
            return
        import urllib.parse
        enc = urllib.parse.quote_plus(termo)
        links = {
            "Google":    f"https://www.google.com/search?q={enc}",
            "YouTube":   f"https://www.youtube.com/results?search_query={enc}",
            "Wikipedia": f"https://pt.wikipedia.org/w/index.php?search={enc}",
            "GitHub":    f"https://github.com/search?q={enc}",
            "PyPI":      f"https://pypi.org/search/?q={enc}",
        }
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ LINKS DE BUSCA: {termo[:30]} ══════════╗{C.RESET}")
        for nome, link in links.items():
            print(f"  {C.CYAN}{nome:<10}{C.RESET} {C.GRAY}{link}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚══════════════════════════════════════════╝{C.RESET}\n")
        abre = input(f"  {C.CYAN}Abrir algum? (google/youtube/wikipedia/github/pypi ou Enter): {C.RESET}").strip().lower()
        if abre:
            for nome, link in links.items():
                if abre in nome.lower():
                    import webbrowser
                    webbrowser.open(link)
                    self.print_nox(f"Abrindo {nome}...")
                    break


    def _cmd_modelo(self):
        """Alterna entre modo online (API) e offline (Ollama local)."""
        print(f"""
{C.PURPLE}{C.BOLD}  ╔══ MODO DE IA ═══════════════════════════════════╗{C.RESET}
{C.WHITE}  1. {C.GREEN}Online {C.GRAY}— API configurada no .env (mais capaz)
{C.WHITE}  2. {C.CYAN}Offline{C.GRAY}— Ollama local gemma2:2b (sem internet)
{C.WHITE}  3. {C.YELLOW}Status {C.GRAY}— Ver situação atual
{C.PURPLE}{C.BOLD}  ╚═══════════════════════════════════════════════╝{C.RESET}""")
        op = input(f"  {C.CYAN}Opção: {C.RESET}").strip()
        if op == "1":
            # Força modo online limpando o aviso de offline
            self._offline_warned = False
            self._offline_mode   = False
            self.print_nox("Modo {C.GREEN}online{C.RESET} ativado. Usando API do .env.")
        elif op == "2":
            st = _local_llm.status()
            if st["has_model"]:
                self._offline_warned = True
                self._offline_mode   = True
                self.print_nox(f"Modo offline ativado. Modelo: {st['models'][0]}")
            else:
                self.print_nox(f"Nenhum modelo encontrado em: {st['models_dir']}")
                baixar = input(f"  {C.CYAN}Baixar modelo agora? (s/n): {C.RESET}").strip().lower()
                if baixar == "s":
                    ok = _local_llm.download_model(print_fn=self.print_nox)
                    if ok:
                        self._offline_warned = True
                        self._offline_mode   = True
        elif op == "3":
            online_ok = bool(self.config.get("api_url") and self.config.get("api_key"))
            st        = _local_llm.status()
            modo_atual = "Offline (local)" if getattr(self, "_offline_mode", False) else "Online (API)"
            print(f"""
  {C.WHITE}Modo atual  : {C.YELLOW}{modo_atual}{C.RESET}
  {C.WHITE}API online  : {"" + C.GREEN + "✓ configurada" if online_ok else C.RED + "✗ não configurada"}{C.RESET}
  {C.WHITE}Modelo local: {"" + C.GREEN + "✓ " + ", ".join(st["models"]) if st["has_model"] else C.RED + "✗ não encontrado"}{C.RESET}
  {C.WHITE}Carregado   : {"" + C.GREEN + "✓ sim" if st["loaded"] else C.GRAY + "não (carrega ao usar)"}{C.RESET}
  {C.GRAY}  Pasta de modelos: {st["models_dir"]}{C.RESET}
  {C.GRAY}  Para baixar: use opção 2 ou baixe manualmente em huggingface.co{C.RESET}
""")

    def _cmd_ban_info(self):
        """Ver detalhes do ban com senha de admin."""
        senha = input(f"  {C.CYAN}Senha admin: {C.RESET}").strip()
        resultado = get_ban_details_with_password(senha)
        self.print_nox(resultado)

    def _cmd_humor(self):
        moods = list(MOOD_PHRASES.keys())
        print(f"\n{C.PINK}{C.BOLD}  ╔══ HUMOR DA NOX ═══════════════════════════╗{C.RESET}")
        print(f"  Humor atual: {C.YELLOW}{self.current_mood}{C.RESET}")
        for i, m in enumerate(moods, 1):
            cur = f" {C.GREEN}← atual{C.RESET}" if m == self.current_mood else ""
            print(f"  {i}. {m.capitalize()}{cur}")
        print(f"{C.PINK}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            ch = input(f"\n  Escolha (Enter = aleatório): ").strip()
            if not ch:
                self._pick_mood()
                self.print_nox(f"Humor: {self.current_mood}. {self._mood_phrase()}")
                return
            idx = int(ch) - 1
            if 0 <= idx < len(moods):
                self.current_mood = moods[idx]
                self.print_nox(f"Humor: {self.current_mood}. {self._mood_phrase()}")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_help(self):
        print(f"""
{C.PURPLE}{C.BOLD}  ╔══ COMANDOS NOX AI — LISTA COMPLETA ════════════════════════╗{C.RESET}

{C.CYAN}{C.BOLD}  ── 🎙️  Voz & Áudio ──────────────────────────────────────────{C.RESET}
{C.WHITE}  /conversa    {C.GRAY}— Modo conversa por voz contínua
{C.WHITE}  /ouvir       {C.GRAY}— Escuta um comando por voz
{C.WHITE}  /voz         {C.GRAY}— Liga/desliga resposta em voz (TTS)
{C.WHITE}  /velocidade  {C.GRAY}— Ajusta velocidade da voz
{C.WHITE}  /wakeon      {C.GRAY}— Ativa detecção de palavra-gatilho
{C.WHITE}  /wakeoff     {C.GRAY}— Desativa detecção de palavra-gatilho
{C.WHITE}  /sensivel    {C.GRAY}— Ajusta sensibilidade do microfone

{C.CYAN}{C.BOLD}  ── 🔐 Criptografia & Códigos ─────────────────────────────────{C.RESET}
{C.WHITE}  /morse       {C.GRAY}— Código Morse (codificar/decodificar)
{C.WHITE}  /caesar      {C.GRAY}— Cifra de César
{C.WHITE}  /base64      {C.GRAY}— Codificar/decodificar Base64
{C.WHITE}  /senha       {C.GRAY}— Gerador de senhas seguras
{C.WHITE}  /hash        {C.GRAY}— MD5/SHA1/SHA256/SHA512 de texto ou arquivo

{C.CYAN}{C.BOLD}  ── 🛠️  Ferramentas ───────────────────────────────────────────{C.RESET}
{C.WHITE}  /calc        {C.GRAY}— Calculadora científica
{C.WHITE}  /clima       {C.GRAY}— Clima de uma cidade
{C.WHITE}  /traduzir    {C.GRAY}— Traduz texto via IA
{C.WHITE}  /ip          {C.GRAY}— IP local e público
{C.WHITE}  /relogio     {C.GRAY}— Relógio em tempo real
{C.WHITE}  /ascii       {C.GRAY}— Arte ASCII de texto
{C.WHITE}  /binario     {C.GRAY}— Converte entre bases numéricas (bin/oct/hex/dec)
{C.WHITE}  /conversor   {C.GRAY}— Converte temperatura, peso, distância
{C.WHITE}  /imc         {C.GRAY}— Calculadora de IMC
{C.WHITE}  /ping        {C.GRAY}— Testa conectividade e latência de um host
{C.WHITE}  /diff        {C.GRAY}— Compara dois textos, mostra diferenças
{C.WHITE}  /regex       {C.GRAY}— Testa expressões regex com highlight
{C.WHITE}  /qrcode      {C.GRAY}— Gera QR Code de texto ou link
{C.WHITE}  /encurtar    {C.GRAY}— Encurta URL via TinyURL
{C.WHITE}  /cpf         {C.GRAY}— Valida e formata CPF
{C.WHITE}  /tabbusc     {C.GRAY}— Busca rápida no Google, YouTube, Wikipedia...

{C.CYAN}{C.BOLD}  ── 🧠 Memória & Conhecimento ─────────────────────────────────{C.RESET}
{C.WHITE}  /fatos       {C.GRAY}— Lista fatos que a Nox sabe sobre você
{C.WHITE}  /aprender    {C.GRAY}— Ensina um novo fato à Nox
{C.WHITE}  /esquecer    {C.GRAY}— Remove um fato da memória
{C.WHITE}  /memoria     {C.GRAY}— Exibe resumo da memória atual
{C.WHITE}  /historico   {C.GRAY}— Histórico de conversas
{C.WHITE}  /salvar      {C.GRAY}— Salva a conversa atual em arquivo
{C.WHITE}  /limpar      {C.GRAY}— Limpa o histórico da sessão
{C.WHITE}  /resumo      {C.GRAY}— Resume texto longo com IA

{C.CYAN}{C.BOLD}  ── ⏱️  Produtividade ─────────────────────────────────────────{C.RESET}
{C.WHITE}  /pomodoro      {C.GRAY}— Inicia timer Pomodoro (25min foco)
{C.WHITE}  /pomodoro_stop {C.GRAY}— Para o Pomodoro em andamento
{C.WHITE}  /foco          {C.GRAY}— Modo foco: bloqueia distrações por X minutos
{C.WHITE}  /lembrete      {C.GRAY}— Cria lembrete com hora e mensagem
{C.WHITE}  /lembretes     {C.GRAY}— Lista todos os lembretes ativos
{C.WHITE}  /cronometro    {C.GRAY}— Cronômetro com pausa no terminal
{C.WHITE}  /countdown     {C.GRAY}— Contagem regressiva até uma data
{C.WHITE}  /meta          {C.GRAY}— Sistema de metas pessoais
{C.WHITE}  /habito        {C.GRAY}— Rastreador de hábitos diários com streak
{C.WHITE}  /streak        {C.GRAY}— Exibe sua sequência de dias consecutivos
{C.WHITE}  /exportar      {C.GRAY}— Exporta conversa ou projeto em arquivo
{C.WHITE}  /alias         {C.GRAY}— Cria atalhos para comandos ou frases
{C.WHITE}  /musica        {C.GRAY}— Busca e toca músicas no YouTube

{C.CYAN}{C.BOLD}  ── 🎨 Personalidade & Visual ─────────────────────────────────{C.RESET}
{C.WHITE}  /personalidade {C.GRAY}— Escolhe a personalidade da Nox
{C.WHITE}  /humor         {C.GRAY}— Exibe/altera o humor atual da Nox
{C.WHITE}  /noturno       {C.GRAY}— Ativa/desativa modo noturno (visual escuro)
{C.WHITE}  /timestamp     {C.GRAY}— Liga/desliga horário nas mensagens
{C.WHITE}  /piada         {C.GRAY}— Conta uma piada aleatória
{C.WHITE}  /nox           {C.GRAY}— A Nox fala algo sobre si mesma

{C.CYAN}{C.BOLD}  ── 🎲 Diversão ───────────────────────────────────────────────{C.RESET}
{C.WHITE}  /dado          {C.GRAY}— Lança dados (ex: 2d6, 1d20)
{C.WHITE}  /sorteio       {C.GRAY}— Sorteia número ou item de lista
{C.WHITE}  /tabela        {C.GRAY}— Tabelas de referência (Git, Python, Linux...)
{C.WHITE}  /notas         {C.GRAY}— Bloco de notas rápidas

{C.CYAN}{C.BOLD}  ── ⚙️  Sistema ───────────────────────────────────────────────{C.RESET}
{C.WHITE}  /stats         {C.GRAY}— Estatísticas de uso da Nox
{C.WHITE}  /config        {C.GRAY}— Configurações (API key, modelo...)
{C.WHITE}  /modelo        {C.GRAY}— Alternar entre API online e Ollama offline
{C.WHITE}  /debug         {C.GRAY}— Informações de depuração
{C.WHITE}  /ban_info      {C.GRAY}— Ver detalhes do ban (requer senha admin)
{C.WHITE}  /ajuda         {C.GRAY}— Exibe esta lista de comandos
{C.WHITE}  /sair          {C.GRAY}— Encerra a Nox AI

{C.CYAN}{C.BOLD}  ── 🖥️  Controle do Sistema (v3.0) ───────────────────────────{C.RESET}
{C.WHITE}  /arquivo       {C.GRAY}— Gerenciar arquivos (listar, copiar, mover, deletar)
{C.WHITE}  /pasta         {C.GRAY}— Gerenciar pastas (criar, listar, abrir)
{C.WHITE}  /app           {C.GRAY}— Abrir qualquer aplicativo instalado
{C.WHITE}  /volume        {C.GRAY}— Controlar volume do sistema
{C.WHITE}  /processo      {C.GRAY}— Listar/encerrar processos
{C.WHITE}  /sistema       {C.GRAY}— Info de CPU, RAM, disco, bateria
{C.WHITE}  /screenshot    {C.GRAY}— Capturar a tela
{C.WHITE}  /imagine       {C.GRAY}— Gerar imagem via IA (Replicate — FLUX)
{C.WHITE}  /travar        {C.GRAY}— Bloquear a tela do computador
{C.WHITE}  /player        {C.GRAY}— Tocar músicas locais 🎵
{C.WHITE}  /spotify       {C.GRAY}— Abrir/pesquisar no Spotify

{C.CYAN}{C.BOLD}  ── 📱 WhatsApp (v3.0) ────────────────────────────────────────{C.RESET}
{C.WHITE}  /wpp           {C.GRAY}— Conectar via QR Code
{C.WHITE}  /wpp_enviar    {C.GRAY}— Enviar mensagem para um contato
{C.WHITE}  /wpp_auto      {C.GRAY}— Auto-resposta com IA ligada/desligada
{C.WHITE}  /wpp_status    {C.GRAY}— Status da conexão WhatsApp

{C.CYAN}{C.BOLD}  ── 👤 Conta ──────────────────────────────────────────────────{C.RESET}
{C.WHITE}  /conta           {C.GRAY}— Mostra a conta atualmente logada
{C.WHITE}  /historico_conta {C.GRAY}— Histórico de mensagens salvas nesta conta
{C.WHITE}  /logout          {C.GRAY}— Sai da conta atual e volta à tela de login
{C.WHITE}  /manutencao      {C.GRAY}— Verifica e instala atualizações da NOX (GitHub)
{C.WHITE}  /admin_usuarios  {C.GRAY}— Lista contas cadastradas (apenas admin)
{C.GRAY}  Esqueceu a senha? Escolha a opção 3 na tela de login.{C.RESET}

{C.CYAN}{C.BOLD}  ── 🤖 Sistema Multiagente (v4.0) ────────────────────────────{C.RESET}
{C.WHITE}  /agente          {C.GRAY}— Envia tarefa para +60 agentes especializados
{C.WHITE}  /agente_status   {C.GRAY}— Status dos times e total de agentes
{C.WHITE}  /agente_projeto  {C.GRAY}— Lista projetos gerados (sites, sistemas, APIs)
{C.WHITE}  /agente_exportar {C.GRAY}— Salva arquivos de um projeto em disco
{C.WHITE}  /agente_hist     {C.GRAY}— Histórico de tarefas do orquestrador

{C.GRAY}  💡 Dica: fale naturalmente! Ex: "abre o chrome",
     "toca uma música", "volume 50", "deleta arquivo.txt"
{C.PURPLE}{C.BOLD}  ╚═════════════════════════════════════════════════════════════╝{C.RESET}
""")

    def _cmd_facts(self):
        summary = self.memory.get_facts_summary()
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ FATOS APRENDIDOS ══════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}{summary}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚══════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_learn_fact(self):
        try:
            key   = input("  Chave: ").strip()
            value = input("  Valor: ").strip()
            if key and value:
                self.memory.add_fact(key, value)
                self.print_nox(f"Fato salvo: {key} → {value} 🧠")
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_forget_fact(self):
        facts = self.memory.get_all_facts()
        if not facts:
            self.print_nox("Nenhum fato.")
            return
        keys = list(facts.keys())
        for i, k in enumerate(keys, 1):
            v = facts[k]["value"] if isinstance(facts[k], dict) else facts[k]
            print(f"  {i}. {k}: {v}")
        try:
            ch = input("\n  Número para esquecer: ").strip()
            idx = int(ch) - 1
            if 0 <= idx < len(keys):
                self.memory.remove_fact(keys[idx])
                self.print_nox(f"Esqueci: {keys[idx]} ✓")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_history(self):
        history = self.memory.get_recent_history(8)
        if not history:
            self.print_nox("Nenhuma conversa salva.")
            return
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ HISTÓRICO ══════════════════════════════╗{C.RESET}")
        for entry in history:
            ts = ""
            try:
                dt = datetime.fromisoformat(entry["timestamp"])
                ts = f"{C.GRAY}[{dt.strftime('%d/%m %H:%M')}]{C.RESET} "
            except Exception:
                pass
            u = entry.get("user", "")[:60]
            n = entry.get("nox",  "")[:60]
            print(f"\n  {ts}{C.CYAN}Você:{C.RESET} {u}{'…' if len(entry.get('user',''))>60 else ''}")
            print(f"  {C.PURPLE}Nox:{C.RESET}  {n}{'…' if len(entry.get('nox',''))>60 else ''}")
        print(f"\n{C.PURPLE}{C.BOLD}  ╚══════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_personality(self):
        keys = list(PERSONALITIES.keys())
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ PERSONALIDADE ══════════════════════════╗{C.RESET}")
        for i, k in enumerate(keys, 1):
            cur = f" {C.GREEN}← atual{C.RESET}" if k == self.personality else ""
            print(f"  {i}. {PERSONALITIES[k]['label']}{cur}")
        print(f"{C.PURPLE}{C.BOLD}  ╚══════════════════════════════════════════╝{C.RESET}")
        try:
            ch = input(f"\n  Escolha (Enter = manter): ").strip()
            if not ch: return
            idx = int(ch) - 1
            if 0 <= idx < len(keys):
                self.personality = keys[idx]
                self.config.set("personality", self.personality)
                self.print_nox(f"Personalidade: {PERSONALITIES[self.personality]['label']} ✓")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_toggle_timestamp(self):
        self.show_ts = not self.show_ts
        self.config.set("show_timestamps", self.show_ts)
        self.print_nox(f"Timestamps {'ativados ⏰' if self.show_ts else 'desativados'}")

    def _cmd_voice_chat(self):
        # ── Tenta abrir interface gráfica primeiro ──────────────────
        if VOICE_UI_AVAILABLE:
            try:
                self.print_nox("Abrindo interface grafica de voz...")
                launch_voice_ui(self)
                return
            except Exception as e:
                self.print_nox(f"Interface grafica falhou ({e}). Usando modo terminal.")

        # ── Fallback: modo conversa por voz no terminal ─────────────
        if not STT_AVAILABLE:
            self.print_nox("sounddevice + SpeechRecognition necessarios.")
            return
        if not TTS_AVAILABLE:
            self.print_nox("edge-tts necessario.")
            return
        old = self.voice_mode; self.voice_mode = True
        try:
            self.voice_conversation_loop()
        except KeyboardInterrupt:
            self.voice_chat = False
        finally:
            self.voice_mode = old

    def _cmd_listen_once(self):
        text = self.listen_vad()
        if text:
            response = self._process_and_respond(text)
            if response:
                self.print_separator()
                self.typing_effect(response)
                self.print_separator()
                if self.voice_mode:
                    self._speak_blocking(response)

    def _cmd_sensitivity(self):
        if not self.vad:
            self.print_nox("sounddevice não disponível.")
            return
        print(f"  Limiar atual: {C.WHITE}{self.vad.ENERGY_THRESHOLD}{C.RESET}")
        try:
            novo = int(input("  Novo valor (50–5000): ").strip())
            self.vad.ENERGY_THRESHOLD = max(50, min(5000, novo))
            self.print_nox(f"Sensibilidade: {self.vad.ENERGY_THRESHOLD}")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_toggle_tts(self):
        if not TTS_AVAILABLE:
            self.print_nox("edge-tts não instalado.")
            return
        self.voice_mode = not self.voice_mode
        self.config.set("voice_enabled", self.voice_mode)
        self.print_nox(f"Voz {'ativada 🔊' if self.voice_mode else 'desativada 🔇'}")

    def _cmd_save(self):
        self.memory.save()
        self.print_nox("Memória salva! 💾")

    def _cmd_memory(self):
        data = self.memory.get_summary()
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ MEMÓRIA ═══════════════════════════════╗{C.RESET}")
        print(f"  Nome          : {C.CYAN}{data.get('user_name','?')}{C.RESET}")
        print(f"  Trocas totais : {C.CYAN}{data.get('total_exchanges',0)}{C.RESET}")
        print(f"  Fatos salvos  : {C.CYAN}{data.get('facts_count',0)}{C.RESET}")
        print(f"  Primeira vez  : {C.CYAN}{data.get('first_seen','?')}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚═══════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_clear(self):
        try:
            c = input(f"  {C.YELLOW}Limpar TODA a memória? (s/n): {C.RESET}").strip().lower()
            if c == "s":
                self.memory.clear(); self.user_name = None
                self.history = []; self._session_exchanges = []
                self.print_nox("Memória limpa. 🗑️")
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_exit(self):
        self.print_separator()
        self.typing_effect("Salvando memória...", delay=0.02)
        self.memory.save(); self._save_streak()
        if self._session_exchanges:
            self.typing_effect("Gerando resumo...", delay=0.02)
            summary = self._generate_session_summary()
            n = len(self._session_exchanges)
            print(f"\n{C.PURPLE}{C.BOLD}  ╔══ RESUMO DA SESSÃO ══════════════════════╗{C.RESET}")
            print(f"  Trocas: {C.CYAN}{n}{C.RESET}")
            print(f"\n  {summary}")
            print(f"\n{C.PURPLE}{C.BOLD}  ╚═══════════════════════════════════════════╝{C.RESET}")
        self.typing_effect("Até logo! 👋", delay=0.02)
        self._speak_blocking("Até logo!")
        self.running = False

    def _cmd_conta(self):
        role_tag = f"{C.YELLOW}👑 admin{C.RESET}" if self._is_admin() else f"{C.GRAY}usuário{C.RESET}"
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ MINHA CONTA ═════════════════════════════╗{C.RESET}")
        print(f"  Usuário : {C.CYAN}{self.account_username or '?'}{C.RESET}  {role_tag}")
        print(f"  Nuvem   : {C.GREEN + '☁ sincronizado' if nox_auth.sb.is_configured() else C.GRAY + 'offline (local)'}{C.RESET}")
        print(f"  Memória : {C.GRAY}{self.memory.memory_file}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
        print(f"  {C.GRAY}Use /logout para sair da conta.{C.RESET}\n")

    def _cmd_logout(self):
        try:
            c = input(f"  {C.YELLOW}Sair da conta '{self.account_username}'? (s/n): {C.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return
        if c != "s":
            return
        self.memory.save()
        nox_auth.clear_session()
        self.print_nox("Sessão encerrada. Até logo! 👋")
        time.sleep(1)
        self.running = False
        # Reinicia o processo para voltar à tela de login
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:
            sys.exit(0)

    def _cmd_historico_conta(self):
        if not self.account_user_id:
            self.print_nox("Nenhuma conta ativa.")
            return
        try:
            n = int(input("  Quantas mensagens mostrar? (Enter=20): ").strip() or "20")
        except (ValueError, KeyboardInterrupt, EOFError):
            n = 20
        rows = nox_auth.get_conversation_history(self.account_user_id, limit=n)
        if not rows:
            self.print_nox("Nenhuma mensagem salva ainda.")
            return
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ HISTÓRICO DA CONTA ({self.account_username}) ══════╗{C.RESET}")
        for r in rows:
            tag = f"{C.CYAN}Você{C.RESET}" if r["role"] == "user" else f"{C.PURPLE}Nox{C.RESET}"
            texto = r["content"][:70] + ("…" if len(r["content"]) > 70 else "")
            print(f"  {tag}: {texto}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _is_admin(self) -> bool:
        return self.account_role == "admin"

    def _cmd_admin_usuarios(self):
        if not self._is_admin():
            self.print_nox("🔒 Esse comando é só para administradores.")
            return
        users = nox_auth.list_all_users()
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ USUÁRIOS CADASTRADOS ══════════════════════╗{C.RESET}")
        for u in users:
            role_tag = f"{C.YELLOW}👑 admin{C.RESET}" if u.get("role") == "admin" else f"{C.GRAY}usuário{C.RESET}"
            print(f"  {C.CYAN}{u.get('username','?'):<20}{C.RESET} {role_tag}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_teste_atualizacao(self):
        """Comando de teste — só existe pra provar que o /manutencao funcionou."""
        v = nox_updater.get_local_version()
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ TESTE DE ATUALIZAÇÃO ═══════════════════╗{C.RESET}")
        print(f"  🎉 Esse comando só existe na versão {C.CYAN}{v}{C.RESET}!")
        print(f"  Se você está vendo isso, o /manutencao funcionou. ✅")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_manutencao(self):
        """
        Modo de manutenção: verifica se há uma nova versão da NOX no
        GitHub e, se houver, baixa e substitui os próprios arquivos —
        sem apagar memória, contas, .env ou configurações pessoais.
        Apenas administradores podem rodar esse comando.
        """
        if not self._is_admin():
            self.print_nox("🔒 Apenas administradores podem rodar a manutenção do sistema.")
            return

        print(f"\n{C.YELLOW}{C.BOLD}  ╔══ MODO DE MANUTENÇÃO ══════════════════════╗{C.RESET}")
        print(f"  {C.GRAY}Repositório: github.com/{nox_updater.REPO_OWNER}/{nox_updater.REPO_NAME}{C.RESET}")
        print(f"{C.YELLOW}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

        local_v = nox_updater.get_local_version()
        self.print_system(f"Versão instalada: {local_v}")
        self.print_system("Verificando atualizações no GitHub...")

        remote_v = nox_updater.get_remote_version()
        if remote_v is None:
            self.print_nox(
                "❌ Não consegui verificar atualizações. Confira sua internet "
                "ou se o repositório/arquivo config/version.json existe lá."
            )
            return

        if remote_v == local_v:
            self.print_nox(f"✅ Você já está na versão mais recente ({local_v}).")
            return

        self.print_nox(f"🆕 Nova versão disponível: {C.GREEN}{remote_v}{C.WHITE} (atual: {local_v})")
        try:
            c = input(f"  {C.YELLOW}Atualizar agora? A Nox vai reiniciar no final. (s/n): {C.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return
        if c != "s":
            self.print_nox("Atualização cancelada.")
            return

        try:
            self.memory.save()
            self.print_system("Salvando estado atual antes de atualizar...")

            backup_dir = nox_updater.backup_current(progress_cb=self.print_system)
            tmp_dir, new_files = nox_updater.download_update(progress_cb=self.print_system)
            self.print_system("Substituindo arquivos (memória, contas e .env NÃO são tocados)...")
            n = nox_updater.apply_update(new_files, progress_cb=self.print_system)
            nox_updater.set_local_version(remote_v)
            nox_updater.cleanup(tmp_dir)

            self.print_nox(f"✅ Atualização concluída! {n} arquivo(s) substituído(s).")
            self.print_nox(f"📦 Backup da versão anterior: {backup_dir}")
            self.print_nox("Reiniciando a Nox com a nova versão em 3 segundos...")
            time.sleep(3)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            self.print_nox(f"❌ Erro durante a atualização: {e}")
            self.print_nox("Nada foi perdido — se um backup chegou a ser feito, ele está intacto.")

    def _cmd_stats(self):
        msgs   = len([m for m in self.history if m["role"] == "user"])
        total  = self.memory.get_summary().get("total_exchanges", 0)
        facts  = self.memory.get_summary().get("facts_count", 0)
        ativos = len([r for r in self._reminders if not r.get("fired")])
        streak = self._streak.get("count", 1)
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ STATS ══════════════════════════════════╗{C.RESET}")
        print(f"  Mensagens (sessão)  : {C.CYAN}{msgs}{C.RESET}")
        print(f"  Total histórico     : {C.CYAN}{total}{C.RESET}")
        print(f"  Fatos aprendidos    : {C.CYAN}{facts}{C.RESET}")
        print(f"  Streak              : {C.ORANGE}{streak} 🔥{C.RESET}")
        print(f"  Personalidade       : {C.CYAN}{PERSONALITIES.get(self.personality,{}).get('label','?')}{C.RESET}")
        print(f"  Humor               : {C.CYAN}{self.current_mood}{C.RESET}")
        print(f"  TTS                 : {C.CYAN}{'Sim' if self.voice_mode else 'Não'}{C.RESET}")
        print(f"  Modo noturno        : {C.CYAN}{'🌙 Ativo' if self.night_mode else 'Inativo'}{C.RESET}")
        print(f"  Modo foco           : {C.CYAN}{'🎯 Ativo' if self.focus_mode else 'Inativo'}{C.RESET}")
        print(f"  Pomodoro            : {C.CYAN}{'🍅 Rodando' if self._pomodoro_active else 'Parado'}{C.RESET}")
        print(f"  Lembretes ativos    : {C.CYAN}{ativos}{C.RESET}")
        print(f"  Aliases             : {C.CYAN}{len(self._aliases)}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_config(self):
        cfg = self.config.all()
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ CONFIG ════════════════════════════════╗{C.RESET}")
        for k, v in cfg.items():
            print(f"  {C.WHITE}{k:<25}: {C.CYAN}{v}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚══════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_debug(self):
        api_url = self.config.get("api_url", "NÃO DEFINIDO")
        api_key = self.config.get("api_key", "NÃO DEFINIDO")
        model   = self.config.get("model",   "NÃO DEFINIDO")
        key_ok  = ("***" + api_key[-8:]) if len(api_key) > 8 else "INVÁLIDA"
        print(f"\n{C.YELLOW}{C.BOLD}  ╔══ DEBUG ══════════════════════════════════╗{C.RESET}")
        print(f"  URL  : {C.CYAN}{api_url}{C.RESET}")
        print(f"  KEY  : {C.CYAN}{key_ok}{C.RESET}")
        print(f"  MODEL: {C.CYAN}{model}{C.RESET}")
        print(f"  TTS  : {C.CYAN}{TTS_AVAILABLE}{C.RESET}")
        print(f"  STT  : {C.CYAN}{SPEECH_AVAILABLE}{C.RESET}")
        print(f"{C.YELLOW}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    def _cmd_dado(self):
        """Lança dados personalizados."""
        print(f"\n  {C.YELLOW}{C.BOLD}🎲 LANÇADOR DE DADOS{C.RESET}")
        try:
            expr = input("  Formato (ex: 2d6, 1d20, 3d8): ").strip().lower() or "1d6"
            m    = re.match(r"(\d+)d(\d+)", expr)
            if not m:
                self.print_nox("Formato inválido. Use NdL (ex: 2d6).")
                return
            qtd, lados = int(m.group(1)), int(m.group(2))
            if qtd > 100 or lados > 10000:
                self.print_nox("Limite: 100 dados, 10000 lados.")
                return
            resultados = [random.randint(1, lados) for _ in range(qtd)]
            total      = sum(resultados)
            print(f"  Resultados : {C.CYAN}{resultados}{C.RESET}")
            print(f"  Total      : {C.GREEN}{C.BOLD}{total}{C.RESET}\n")
            if self.voice_mode:
                self._speak_async(f"Resultado: {total}")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_sorteio(self):
        """Sorteia um item de uma lista ou número de um intervalo."""
        print(f"\n  {C.GREEN}{C.BOLD}🎰 SORTEIO{C.RESET}")
        print(f"  {C.GRAY}1. Sortear número  2. Sortear da lista{C.RESET}")
        try:
            op = input("  Opção: ").strip()
            if op == "1":
                minv = int(input("  Mínimo (Enter=1): ").strip() or "1")
                maxv = int(input("  Máximo (Enter=100): ").strip() or "100")
                if minv >= maxv:
                    self.print_nox("Mínimo deve ser menor que máximo.")
                    return
                result = random.randint(minv, maxv)
                print(f"\n  {C.GREEN}{C.BOLD}🎯 Sorteado: {result}{C.RESET}\n")
                if self.voice_mode:
                    self._speak_async(f"Número sorteado: {result}")
            elif op == "2":
                itens_str = input("  Itens separados por vírgula: ").strip()
                if not itens_str:
                    return
                itens  = [i.strip() for i in itens_str.split(",") if i.strip()]
                result = random.choice(itens)
                print(f"\n  {C.GREEN}{C.BOLD}🎯 Sorteado: {result}{C.RESET}\n")
                if self.voice_mode:
                    self._speak_async(f"Sorteado: {result}")
            else:
                self.print_nox("Opção inválida.")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_imc(self):
        """Calcula IMC e mostra classificação."""
        print(f"\n  {C.BLUE}{C.BOLD}⚖️  CALCULADORA DE IMC{C.RESET}")
        try:
            peso = float(input("  Peso (kg): ").strip().replace(",", "."))
            alt  = float(input("  Altura (m, ex: 1.75): ").strip().replace(",", "."))
            if peso <= 0 or alt <= 0:
                self.print_nox("Valores inválidos.")
                return
            imc = peso / (alt ** 2)
            if imc < 18.5:   cat, cor = "Abaixo do peso", C.BLUE
            elif imc < 25.0: cat, cor = "Peso normal ✓",  C.GREEN
            elif imc < 30.0: cat, cor = "Sobrepeso",       C.YELLOW
            elif imc < 35.0: cat, cor = "Obesidade grau I", C.ORANGE
            else:             cat, cor = "Obesidade grau II+", C.RED
            print(f"\n  IMC          : {C.BOLD}{imc:.1f}{C.RESET}")
            print(f"  Classificação: {cor}{C.BOLD}{cat}{C.RESET}\n")
            if self.voice_mode:
                self._speak_async(f"Seu IMC é {imc:.1f}. {cat}.")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Valores inválidos.")

    def _cmd_conversor(self):
        """Conversor de unidades: temperatura, distância, peso, velocidade."""
        categorias = {
            "1": "Temperatura",
            "2": "Distância",
            "3": "Peso",
            "4": "Velocidade",
        }
        print(f"\n  {C.CYAN}{C.BOLD}📐 CONVERSOR DE UNIDADES{C.RESET}")
        for k, v in categorias.items():
            print(f"  {k}. {v}")
        try:
            op  = input("\n  Categoria: ").strip()
            val = float(input("  Valor: ").strip().replace(",", "."))

            if op == "1":  # Temperatura
                print(f"  {C.GRAY}1=°C→°F  2=°F→°C  3=°C→K{C.RESET}")
                sub = input("  Conversão: ").strip()
                if   sub == "1": r, u = val * 9/5 + 32, "°F"
                elif sub == "2": r, u = (val - 32) * 5/9, "°C"
                elif sub == "3": r, u = val + 273.15, "K"
                else: self.print_nox("Inválido."); return

            elif op == "2":  # Distância
                print(f"  {C.GRAY}1=km→mi  2=mi→km  3=m→ft  4=ft→m{C.RESET}")
                sub = input("  Conversão: ").strip()
                if   sub == "1": r, u = val * 0.621371, "milhas"
                elif sub == "2": r, u = val * 1.60934, "km"
                elif sub == "3": r, u = val * 3.28084, "pés"
                elif sub == "4": r, u = val * 0.3048, "metros"
                else: self.print_nox("Inválido."); return

            elif op == "3":  # Peso
                print(f"  {C.GRAY}1=kg→lb  2=lb→kg  3=g→oz  4=oz→g{C.RESET}")
                sub = input("  Conversão: ").strip()
                if   sub == "1": r, u = val * 2.20462, "libras"
                elif sub == "2": r, u = val * 0.453592, "kg"
                elif sub == "3": r, u = val * 0.035274, "onças"
                elif sub == "4": r, u = val * 28.3495, "gramas"
                else: self.print_nox("Inválido."); return

            elif op == "4":  # Velocidade
                print(f"  {C.GRAY}1=km/h→mph  2=mph→km/h  3=m/s→km/h{C.RESET}")
                sub = input("  Conversão: ").strip()
                if   sub == "1": r, u = val * 0.621371, "mph"
                elif sub == "2": r, u = val * 1.60934, "km/h"
                elif sub == "3": r, u = val * 3.6, "km/h"
                else: self.print_nox("Inválido."); return
            else:
                self.print_nox("Categoria inválida."); return

            print(f"\n  {C.GREEN}{C.BOLD}= {r:.4f} {u}{C.RESET}\n")
            if self.voice_mode:
                self._speak_async(f"Resultado: {r:.2f} {u}")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Valor inválido.")

    def _cmd_binario(self):
        """Converte entre binário, decimal, hexadecimal e octal."""
        print(f"\n  {C.GREEN}{C.BOLD}💻 CONVERSOR DE BASES{C.RESET}")
        print(f"  {C.GRAY}1=Dec→Bin  2=Bin→Dec  3=Dec→Hex  4=Hex→Dec{C.RESET}")
        print(f"  {C.GRAY}5=Dec→Oct  6=Oct→Dec  7=Tudo de uma vez{C.RESET}")
        try:
            op = input("  Opção: ").strip()
            if op == "7":
                val = int(input("  Número decimal: ").strip())
                print(f"  Decimal  : {C.WHITE}{val}{C.RESET}")
                print(f"  Binário  : {C.CYAN}{bin(val)[2:]}{C.RESET}")
                print(f"  Hexadec. : {C.GREEN}{hex(val)[2:].upper()}{C.RESET}")
                print(f"  Octal    : {C.YELLOW}{oct(val)[2:]}{C.RESET}")
                return
            entrada = input("  Valor: ").strip()
            if   op == "1": r = bin(int(entrada))[2:];       u = "binário"
            elif op == "2": r = str(int(entrada, 2));         u = "decimal"
            elif op == "3": r = hex(int(entrada))[2:].upper();u = "hexadecimal"
            elif op == "4": r = str(int(entrada, 16));        u = "decimal"
            elif op == "5": r = oct(int(entrada))[2:];        u = "octal"
            elif op == "6": r = str(int(entrada, 8));         u = "decimal"
            else: self.print_nox("Inválido."); return
            print(f"\n  {C.GREEN}{C.BOLD}= {r} ({u}){C.RESET}\n")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Valor inválido para a base escolhida.")

    def _cmd_meta(self):
        """Sistema simples de metas pessoais com progresso."""
        meta_file = "nox_metas.json"
        def _load_metas():
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return []
        def _save_metas(metas):
            try:
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(metas, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        metas = _load_metas()
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ METAS PESSOAIS ═════════════════════════╗{C.RESET}")
        if metas:
            for i, m in enumerate(metas, 1):
                pct  = int((m["atual"] / m["total"]) * 20)
                bar  = "█" * pct + "░" * (20 - pct)
                done = "✅" if m["atual"] >= m["total"] else "🔲"
                print(f"  {done} {i}. {C.WHITE}{m['nome']}{C.RESET}")
                print(f"     [{bar}] {m['atual']}/{m['total']}")
        else:
            print(f"  {C.GRAY}Nenhuma meta cadastrada.{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        print(f"\n  {C.GRAY}[1] Nova meta  [2] Atualizar progresso  [3] Remover  [Enter] Fechar{C.RESET}")
        try:
            op = input("  Opção: ").strip()
            if op == "1":
                nome  = input("  Nome da meta: ").strip()
                total = int(input("  Total necessário (ex: 10 para '10 livros'): ").strip())
                metas.append({"nome": nome, "total": total, "atual": 0,
                               "criada": datetime.now().strftime("%d/%m/%Y")})
                _save_metas(metas)
                self.print_nox(f"Meta '{nome}' criada! 🎯")
            elif op == "2" and metas:
                idx = int(input("  Número da meta: ").strip()) - 1
                inc = int(input("  Progresso adicionado: ").strip())
                metas[idx]["atual"] = min(metas[idx]["atual"] + inc, metas[idx]["total"])
                if metas[idx]["atual"] >= metas[idx]["total"]:
                    self.print_nox(f"🏆 Meta '{metas[idx]['nome']}' CONCLUÍDA! Parabéns!")
                    if self.voice_mode:
                        self._speak_async(f"Parabéns! Você concluiu a meta {metas[idx]['nome']}!")
                _save_metas(metas)
            elif op == "3" and metas:
                idx = int(input("  Número para remover: ").strip()) - 1
                nome = metas.pop(idx)["nome"]
                _save_metas(metas)
                self.print_nox(f"Meta '{nome}' removida.")
        except (ValueError, IndexError, KeyboardInterrupt, EOFError):
            pass

    def _cmd_countdown_date(self):
        """Conta regressiva até uma data específica."""
        print(f"\n  {C.PURPLE}{C.BOLD}📅 CONTAGEM REGRESSIVA{C.RESET}")
        try:
            data_str = input("  Data alvo (DD/MM/AAAA): ").strip()
            evento   = input("  Nome do evento: ").strip() or "Evento"
            alvo     = datetime.strptime(data_str, "%d/%m/%Y")
            hoje     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            diff     = alvo - hoje
            dias     = diff.days
            if dias < 0:
                self.print_nox(f"'{evento}' já passou há {abs(dias)} dias.")
            elif dias == 0:
                self.print_nox(f"🎉 '{evento}' é HOJE!")
                if self.voice_mode:
                    self._speak_async(f"Hoje é o dia de {evento}!")
            else:
                semanas = dias // 7
                print(f"\n  {C.CYAN}{C.BOLD}⏳ {evento}{C.RESET}")
                print(f"  Faltam : {C.GREEN}{C.BOLD}{dias} dias{C.RESET}")
                print(f"  Ou seja: {C.GRAY}{semanas} semanas e {dias % 7} dias{C.RESET}\n")
                if self.voice_mode:
                    self._speak_async(f"Faltam {dias} dias para {evento}.")
        except (ValueError, KeyboardInterrupt, EOFError):
            self.print_nox("Formato inválido. Use DD/MM/AAAA.")

    def _cmd_tabela(self):
        """Exibe tabela de atalhos e referências úteis de programação."""
        categorias = {
            "1": ("Git básico", [
                ("git init",          "Inicia repositório"),
                ("git add .",         "Adiciona tudo"),
                ("git commit -m ''",  "Faz commit"),
                ("git push",          "Envia para remoto"),
                ("git pull",          "Puxa do remoto"),
                ("git status",        "Mostra status"),
                ("git log --oneline", "Histórico curto"),
                ("git branch nome",   "Cria branch"),
                ("git checkout nome", "Troca branch"),
                ("git merge nome",    "Faz merge"),
            ]),
            "2": ("Python rápido", [
                ("list comp",  "[x for x in lista if cond]"),
                ("dict comp",  "{k: v for k, v in d.items()}"),
                ("lambda",     "lambda x: x * 2"),
                ("enumerate",  "for i, v in enumerate(lista):"),
                ("zip",        "for a, b in zip(l1, l2):"),
                ("*args",      "def f(*args): → tupla"),
                ("**kwargs",   "def f(**kwargs): → dict"),
                ("f-string",   "f'Olá {nome}'"),
                ("walrus :=",  "if (n := len(a)) > 10:"),
                ("type hint",  "def f(x: int) -> str:"),
            ]),
            "3": ("Linux/terminal", [
                ("ls -la",         "Lista arquivos com detalhes"),
                ("cd -",           "Volta ao diretório anterior"),
                ("ctrl+r",         "Busca no histórico"),
                ("!! ",            "Repete último comando"),
                ("grep -r txt .",  "Busca texto recursivamente"),
                ("ps aux | grep",  "Filtra processos"),
                ("kill -9 PID",    "Mata processo"),
                ("chmod +x",       "Torna executável"),
                ("tar -xzf",       "Extrai .tar.gz"),
                ("df -h",          "Espaço em disco"),
            ]),
        }
        print(f"\n  {C.ORANGE}{C.BOLD}📋 TABELAS DE REFERÊNCIA{C.RESET}")
        for k, (nome, _) in categorias.items():
            print(f"  {k}. {nome}")
        try:
            op = input("\n  Escolha: ").strip()
            if op not in categorias:
                self.print_nox("Inválido.")
                return
            nome, itens = categorias[op]
            print(f"\n{C.ORANGE}{C.BOLD}  ╔══ {nome.upper()} {'═'*(38-len(nome))}╗{C.RESET}")
            for cmd_ref, desc in itens:
                print(f"  {C.CYAN}{cmd_ref:<22}{C.RESET} {C.GRAY}{desc}{C.RESET}")
            print(f"{C.ORANGE}{C.BOLD}  ╚{'═'*44}╝{C.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            pass



    # ══════════════════════════════════════════
    #  v3.0 — EXECUTOR DE AÇÕES DE SISTEMA
    # ══════════════════════════════════════════

    def _execute_system_action(self, action: str, arg: str) -> str | None:
        """Executa uma ação de controle do sistema e retorna mensagem."""
        _vol_step = 10
        action_map = {
            "delete":         lambda: sc.file_delete(arg),
            "create_file":    lambda: sc.file_create(arg),
            "create_folder":  lambda: sc.folder_create(arg),
            "open_app":       lambda: sc.open_app(arg),
            "open_url":       lambda: sc.open_url(arg),
            "play_music":     lambda: sc.play_music(arg),
            "stop_music":     lambda: sc.stop_music(),
            "set_volume":     lambda: sc.set_volume(int(arg) if arg.isdigit() else 50),
            "volume_up":      lambda: sc.set_volume(min(100, 50 + _vol_step)),  # simplificado
            "volume_down":    lambda: sc.set_volume(max(0, 50 - _vol_step)),
            "mute":           lambda: sc.mute_volume(),
            "screenshot":     lambda: sc.screenshot(),
            "lock":           lambda: sc.lock_screen(),
            "sysinfo":        lambda: sc.system_info(),
            "battery":        lambda: sc.battery_info(),
            "list_procs":     lambda: "\n" + sc.list_processes(arg),
            "kill_proc":      lambda: sc.kill_process(arg),
            "list_dir":       lambda: "\n" + sc.folder_list(arg or "."),
            "clipboard_copy": lambda: sc.clipboard_copy(arg),
        }
        fn = action_map.get(action)
        if fn:
            try:
                return fn()
            except Exception as e:
                return f"❌ Erro ao executar ação: {e}"
        return None

    # ══════════════════════════════════════════
    #  v3.0 — CONTROLE DE ARQUIVOS
    # ══════════════════════════════════════════

    def _cmd_arquivo(self):
        print(f"\n{C.CYAN}{C.BOLD}  ╔══ CONTROLE DE ARQUIVOS ════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}1. Deletar arquivo/pasta")
        print(f"  2. Criar arquivo")
        print(f"  3. Criar pasta")
        print(f"  4. Copiar")
        print(f"  5. Mover/Renomear")
        print(f"  6. Ler conteúdo")
        print(f"  7. Listar pasta")
        print(f"  8. Buscar arquivo{C.RESET}")
        print(f"{C.CYAN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                p = input("  Caminho para deletar: ").strip()
                confirm = input(f"  Deletar '{p}'? (s/n): ").strip().lower()
                if confirm == "s":
                    self.print_nox(sc.file_delete(p))
                else:
                    self.print_nox("Cancelado.")
            elif op == "2":
                p = input("  Caminho do novo arquivo: ").strip()
                print("  Conteúdo (Enter em linha vazia para finalizar):")
                lines = []
                while True:
                    line = input()
                    if line == "": break
                    lines.append(line)
                self.print_nox(sc.file_create(p, "\n".join(lines)))
            elif op == "3":
                p = input("  Caminho da nova pasta: ").strip()
                self.print_nox(sc.folder_create(p))
            elif op == "4":
                src = input("  Origem: ").strip()
                dst = input("  Destino: ").strip()
                self.print_nox(sc.file_copy(src, dst))
            elif op == "5":
                src = input("  Arquivo atual: ").strip()
                dst = input("  Novo nome ou destino: ").strip()
                self.print_nox(sc.file_move(src, dst))
            elif op == "6":
                p = input("  Arquivo para ler: ").strip()
                content = sc.file_read(p)
                print(f"\n{C.WHITE}{content[:3000]}{C.RESET}")
            elif op == "7":
                p = input("  Pasta (Enter = atual): ").strip() or "."
                print(f"\n{sc.folder_list(p)}")
            elif op == "8":
                pattern = input("  Padrão de busca (ex: *.py): ").strip()
                root = input("  Onde buscar (Enter = ~): ").strip() or "~"
                results = sc.file_search(pattern, root)
                if results:
                    for r in results:
                        print(f"  📄 {r}")
                else:
                    self.print_nox("Nenhum arquivo encontrado.")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — CONTROLE DE PASTA (atalho rápido)
    # ══════════════════════════════════════════

    def _cmd_pasta(self):
        try:
            p = input("  Listar pasta (Enter = Desktop): ").strip() or "~/Desktop"
            print(f"\n{sc.folder_list(p)}")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — ABRIR APLICATIVOS
    # ══════════════════════════════════════════

    def _cmd_app(self):
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ ABRIR APLICATIVO ═══════════════════════╗{C.RESET}")
        print(f"  {C.GRAY}Apps reconhecidos: chrome, firefox, spotify, discord,")
        print(f"  vscode, calculadora, explorador, notepad, terminal,")
        print(f"  word, excel, whatsapp, telegram, zoom, teams...{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            name = input("\n  Qual app abrir? ").strip()
            if name:
                self.print_nox(sc.open_app(name))
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — CONTROLE DE VOLUME
    # ══════════════════════════════════════════

    def _cmd_volume(self):
        print(f"\n{C.BLUE}{C.BOLD}  ╔══ CONTROLE DE VOLUME ═════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}1. Definir volume (0-100%)")
        print(f"  2. Mutar")
        print(f"  3. Desmutar{C.RESET}")
        print(f"{C.BLUE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                v = input("  Volume (0-100): ").strip()
                self.print_nox(sc.set_volume(int(v)))
            elif op == "2":
                self.print_nox(sc.mute_volume())
            elif op == "3":
                self.print_nox(sc.unmute_volume())
        except (KeyboardInterrupt, EOFError, ValueError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — PROCESSOS
    # ══════════════════════════════════════════

    def _cmd_processo(self):
        print(f"\n{C.ORANGE}{C.BOLD}  ╔══ PROCESSOS ═══════════════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}1. Listar processos")
        print(f"  2. Encerrar processo{C.RESET}")
        print(f"{C.ORANGE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                filtro = input("  Filtrar por nome (Enter = todos): ").strip()
                print(f"\n{sc.list_processes(filtro)}")
            elif op == "2":
                nome = input("  Nome ou PID do processo: ").strip()
                c = input(f"  Encerrar '{nome}'? (s/n): ").strip().lower()
                if c == "s":
                    self.print_nox(sc.kill_process(nome))
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — INFO DO SISTEMA
    # ══════════════════════════════════════════

    def _cmd_sistema(self):
        print(f"\n{C.CYAN}{C.BOLD}  ╔══ INFO DO SISTEMA ═════════════════════════╗{C.RESET}")
        print(sc.system_info())
        print(sc.battery_info())
        print(sc.get_local_ip())
        print(f"{C.CYAN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    # ══════════════════════════════════════════
    #  v3.0 — SCREENSHOT
    # ══════════════════════════════════════════

    def _cmd_screenshot(self):
        path = input("  Salvar em (Enter = Desktop): ").strip() or "~/Desktop/nox_screenshot.png"
        self.print_nox(sc.screenshot(path))

    def _cmd_imagine(self):
        """
        /imagine <prompt> — Gera imagem via Replicate (FLUX) em background.
        O chat fica LIVRE imediatamente. Quando a imagem ficar pronta,
        a NOX avisa por texto (e por voz, se estiver no modo conversa).
        As imagens são salvas em nox_output/output/
        """
        import threading as _threading

        # ── Pega o prompt ────────────────────────────────────────────
        prompt = self._last_raw_cmd.partition(" ")[2].strip() if hasattr(self, "_last_raw_cmd") else ""
        if not prompt:
            prompt = input("  Descreva a imagem que quer gerar: ").strip()
        if not prompt:
            self.print_nox("Informe um prompt. Ex: /imagine um gato astronauta na lua")
            return

        # ── Pasta de saída: nox_output/output/ ──────────────────────
        import sys as _sys
        from pathlib import Path as _Path
        pasta_output = _Path(__file__).parent / "output"
        pasta_output.mkdir(parents=True, exist_ok=True)

        self.print_nox(
            f"🎨 Gerando imagem em background: \"{prompt}\"\n"
            f"   O chat já está liberado — vou te avisar quando terminar!"
        )

        # ── Função que roda na thread ────────────────────────────────
        def _worker():
            try:
                from image_generator import generate_image, ImageGeneratorError
                path = generate_image(prompt, output_dir=str(pasta_output))

                self.print_nox(f"✅ Imagem pronta! Salva em:\n   {path}")
                

                # Fala por voz se estiver no modo conversa (/conversa)
                if getattr(self, "voice_chat", False) or getattr(self, "voice_mode", False):
                    try:
                        self._speak_blocking("Imagem gerada com sucesso! Já salvei na pasta output.")
                    except Exception:
                        pass

                # Abre automaticamente no visualizador do sistema
                try:
                    import subprocess as _sp
                    if _sys.platform == "win32":
                        os.startfile(path)
                    elif _sys.platform == "darwin":
                        _sp.Popen(["open", path])
                    else:
                        _sp.Popen(["xdg-open", path])
                except Exception:
                    pass

            except ImportError:
                self.print_nox(
                    "❌ Módulo image_generator.py não encontrado.\n"
                    "   Coloque image_generator.py na mesma pasta do main.py."
                )
            except Exception as e:
                self.print_nox(f"❌ Erro ao gerar imagem: {e}")

        # ── Dispara a thread e devolve o controle ao usuário ─────────
        t = _threading.Thread(target=_worker, daemon=True, name="nox-imagine")
        t.start()

    # ══════════════════════════════════════════
    #  v3.0 — TRAVAR TELA
    # ══════════════════════════════════════════

    def _cmd_travar(self):
        self.print_nox(sc.lock_screen())

    # ══════════════════════════════════════════
    #  v3.0 — PLAYER DE MÚSICA LOCAL
    # ══════════════════════════════════════════

    def _cmd_player(self):
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ PLAYER DE MÚSICA ═══════════════════════╗{C.RESET}")
        print(f"  {C.WHITE}1. Tocar arquivo (caminho ou nome)")
        print(f"  2. Parar música")
        print(f"  3. Status")
        print(f"  4. Listar músicas da pasta Music{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                path = input("  Arquivo ou nome da música: ").strip()
                self.print_nox(sc.play_music(path))
            elif op == "2":
                self.print_nox(sc.stop_music())
            elif op == "3":
                self.print_nox(sc.music_status())
            elif op == "4":
                folder = input("  Pasta (Enter = ~/Music): ").strip() or "~/Music"
                musics = sc.list_music(folder)
                if musics:
                    for m in musics:
                        print(f"  🎵 {m}")
                else:
                    self.print_nox("Nenhuma música encontrada. Tente especificar a pasta.")
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — SPOTIFY
    # ══════════════════════════════════════════

    def _cmd_spotify(self):
        try:
            q = input("  Buscar no Spotify (Enter = abrir Spotify): ").strip()
            self.print_nox(sc.open_spotify(q))
        except (KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  v3.0 — WHATSAPP
    # ══════════════════════════════════════════

    def _cmd_wpp(self):
        """Menu principal do WhatsApp."""
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ WHATSAPP ════════════════════════════════╗{C.RESET}")
        estado = wpp.status_str()
        print(f"  {estado}")
        print(f"  {C.GRAY}──────────────────────────────────────────{C.RESET}")
        print(f"  {C.WHITE}1. Conectar / gerar QR Code")
        print(f"  2. Ver chats recentes")
        print(f"  3. Desconectar")
        print(f"  4. Status{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()

            if op == "1":
                if wpp.is_connected():
                    self.print_nox("WhatsApp já está conectado! Use /wpp_enviar para enviar mensagens.")
                    return
                if wpp.is_connecting():
                    self.print_nox("Já está conectando, aguarde o QR Code no terminal...")
                    return

                # Callback chamado quando mensagem chegar
                def on_msg(msg):
                    name = msg.get("name", msg.get("from", "?"))
                    body = msg.get("body", "")
                    isgroup = msg.get("isGroup", False)
                    grupo = " [GRUPO]" if isgroup else ""
                    print(f"\n  📩 {C.GREEN}{name}{grupo}{C.RESET}: {body}")

                    auto, prompt_auto = wpp.get_auto_reply_state()
                    if auto and not isgroup:
                        instrucao = prompt_auto or "Você é um assistente útil. Responda de forma natural, curta e amigável."
                        resp = self._quick_api_call(
                            f"Instrução: {instrucao}\n\nMensagem recebida de {name}: {body}\n\nResponda de forma natural:",
                            max_tokens=250,
                        )
                        if resp:
                            wpp.send_message(msg.get("reply_to") or msg["from"], resp)
                            print(f"  {C.CYAN}🤖 Auto-resposta:{C.RESET} {resp[:100]}")

                ok, msg = wpp.connect(on_message_cb=on_msg)
                self.print_nox(msg)
                if ok:
                    print(f"\n  {C.YELLOW}⏳ Aguarde — o QR Code vai aparecer aqui em alguns segundos.{C.RESET}")
                    print(f"  {C.GRAY}  Abra o WhatsApp > Aparelhos conectados > Conectar aparelho{C.RESET}\n")

            elif op == "2":
                if not wpp.is_connected():
                    self.print_nox("WhatsApp não conectado. Use a opção 1 primeiro.")
                    return
                wpp.request_chats()
                self.print_system("Buscando chats...")
                time.sleep(2)
                eventos = wpp.get_pending(timeout=2)
                chats = next((e["data"] for e in eventos if e.get("type") == "chats"), None)
                if chats:
                    print(f"\n{C.GREEN}{C.BOLD}  ╔══ CHATS RECENTES ══════════════════════════╗{C.RESET}")
                    for c in chats[:15]:
                        unread = f" ({c.get('unread',0)} não lidas)" if c.get('unread') else ""
                        print(f"  {C.WHITE}• {c.get('name','?')}{C.GRAY}{unread}{C.RESET}")
                    print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
                else:
                    self.print_nox("Nenhum chat recebido ainda. Tente novamente.")

            elif op == "3":
                self.print_nox(wpp.disconnect())

            elif op == "4":
                self.print_nox(wpp.status_str())

        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_wpp_enviar(self):
        """Envia mensagem pelo WhatsApp."""
        if not wpp.is_connected():
            self.print_nox("❌ WhatsApp não conectado. Use /wpp > opção 1 primeiro.")
            return
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ ENVIAR MENSAGEM ═════════════════════════╗{C.RESET}")
        try:
            numero   = input("  Número com DDD+DDI (ex: 5511999999999): ").strip()
            mensagem = input("  Mensagem: ").strip()
            if numero and mensagem:
                resultado = wpp.send_message(numero, mensagem)
                self.print_nox(resultado)
            else:
                self.print_nox("Número ou mensagem vazio. Cancelado.")
        except (KeyboardInterrupt, EOFError):
            pass
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")

    def _cmd_wpp_auto(self):
        """Configura a auto-resposta com IA."""
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ AUTO-RESPOSTA WHATSAPP ══════════════════╗{C.RESET}")
        auto, prompt = wpp.get_auto_reply_state()
        status = f"{C.GREEN}ATIVA 🟢{C.RESET}" if auto else f"{C.RED}INATIVA 🔴{C.RESET}"
        print(f"  Status: {status}")
        if prompt:
            print(f"  Instrução: {C.GRAY}{prompt[:60]}{C.RESET}")
        print(f"  {C.GRAY}──────────────────────────────────────────{C.RESET}")
        print(f"  {C.WHITE}1. Ativar auto-resposta")
        print(f"  2. Desativar auto-resposta")
        print(f"  3. Mudar instrução da IA")
        print(f"  4. Ver instrução atual{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        try:
            op = input("\n  Opção: ").strip()
            if op == "1":
                if not wpp.is_connected():
                    self.print_nox("⚠️  Conecte o WhatsApp primeiro com /wpp.")
                    return
                self.print_nox(wpp.set_auto_reply(True, prompt))
                self.print_nox("🤖 Nox vai responder automaticamente cada mensagem recebida!")
            elif op == "2":
                self.print_nox(wpp.set_auto_reply(False, prompt))
            elif op == "3":
                print(f"  {C.GRAY}Exemplo: 'Responda sempre em inglês e de forma formal'")
                print(f"  Deixe vazio para usar o padrão amigável.{C.RESET}")
                new_prompt = input("  Nova instrução: ").strip()
                wpp.set_auto_reply(auto, new_prompt)
                self.print_nox(f"✅ Instrução salva!")
            elif op == "4":
                if prompt:
                    self.print_nox(f"Instrução atual: {prompt}")
                else:
                    self.print_nox("Nenhuma instrução personalizada. Usando padrão amigável.")
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_wpp_status(self):
        """Exibe status detalhado do WhatsApp."""
        print(f"\n{C.GREEN}{C.BOLD}  ╔══ STATUS WHATSAPP ═════════════════════════╗{C.RESET}")
        print(f"  {wpp.status_str()}")
        auto, prompt = wpp.get_auto_reply_state()
        auto_str = f"{C.GREEN}Ativa{C.RESET}" if auto else f"{C.RED}Inativa{C.RESET}"
        print(f"  Auto-resposta: {auto_str}")
        if prompt:
            print(f"  Instrução: {C.GRAY}{prompt[:60]}{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

    # ══════════════════════════════════════════
    #  NOVOS COMANDOS v3.2 — Utilidades
    # ══════════════════════════════════════════

    def _cmd_hash(self):
        """Gera hash MD5, SHA1, SHA256 ou SHA512 de texto ou arquivo."""
        import hashlib
        print(f"\n  {C.CYAN}{C.BOLD}🔑 GERADOR DE HASH{C.RESET}")
        print(f"  {C.GRAY}1. Hash de texto  2. Hash de arquivo{C.RESET}")
        try:
            op = input("  Opção: ").strip()
            if op == "1":
                texto = input("  Texto: ").strip()
                if not texto:
                    return
                data = texto.encode("utf-8")
            elif op == "2":
                caminho = input("  Caminho do arquivo: ").strip().strip('"')
                if not os.path.isfile(caminho):
                    self.print_nox("Arquivo não encontrado.")
                    return
                with open(caminho, "rb") as f:
                    data = f.read()
            else:
                self.print_nox("Opção inválida.")
                return

            print(f"\n  {C.YELLOW}MD5    :{C.RESET} {C.WHITE}{hashlib.md5(data).hexdigest()}{C.RESET}")
            print(f"  {C.YELLOW}SHA1   :{C.RESET} {C.WHITE}{hashlib.sha1(data).hexdigest()}{C.RESET}")
            print(f"  {C.YELLOW}SHA256 :{C.RESET} {C.WHITE}{hashlib.sha256(data).hexdigest()}{C.RESET}")
            print(f"  {C.YELLOW}SHA512 :{C.RESET} {C.WHITE}{hashlib.sha512(data).hexdigest()}{C.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_ping(self):
        """Testa conectividade com um host e mede latência."""
        print(f"\n  {C.GREEN}{C.BOLD}📡 PING{C.RESET}")
        try:
            host = input("  Host ou IP (Enter=8.8.8.8): ").strip() or "8.8.8.8"
            count = input("  Quantos pings? (Enter=4): ").strip() or "4"
            try:
                count = max(1, min(int(count), 20))
            except ValueError:
                count = 4

            print(f"\n  {C.GRAY}Pingando {host} ({count}x)...{C.RESET}\n")
            param = "-n" if os.name == "nt" else "-c"
            cmd = ["ping", param, str(count), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout or result.stderr

            # Colorir a saída
            for line in output.splitlines():
                if "tempo=" in line.lower() or "time=" in line.lower() or "ms" in line.lower():
                    print(f"  {C.GREEN}{line}{C.RESET}")
                elif "erro" in line.lower() or "error" in line.lower() or "unreachable" in line.lower() or "falha" in line.lower():
                    print(f"  {C.RED}{line}{C.RESET}")
                elif line.strip():
                    print(f"  {C.GRAY}{line}{C.RESET}")
            print()
        except subprocess.TimeoutExpired:
            self.print_nox("Timeout — host não respondeu.")
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_diff(self):
        """Compara dois textos e exibe as diferenças linha a linha."""
        import difflib
        print(f"\n  {C.PURPLE}{C.BOLD}📄 COMPARAR TEXTOS{C.RESET}")
        print(f"  {C.GRAY}Digite o 1º texto (linha em branco para terminar):{C.RESET}")
        try:
            linhas1 = []
            while True:
                l = input()
                if l == "":
                    break
                linhas1.append(l + "\n")

            print(f"  {C.GRAY}Digite o 2º texto (linha em branco para terminar):{C.RESET}")
            linhas2 = []
            while True:
                l = input()
                if l == "":
                    break
                linhas2.append(l + "\n")

            if not linhas1 and not linhas2:
                return

            diff = list(difflib.unified_diff(linhas1, linhas2, fromfile="Texto 1", tofile="Texto 2"))
            if not diff:
                self.print_nox("✅ Os textos são idênticos!")
                return

            print(f"\n  {C.YELLOW}{C.BOLD}Diferenças encontradas:{C.RESET}\n")
            for line in diff:
                line = line.rstrip("\n")
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"  {C.GREEN}{line}{C.RESET}")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"  {C.RED}{line}{C.RESET}")
                elif line.startswith("@"):
                    print(f"  {C.CYAN}{line}{C.RESET}")
                else:
                    print(f"  {C.GRAY}{line}{C.RESET}")
            print()
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_regex(self):
        """Testa expressões regex em tempo real contra um texto."""
        import re as _re
        print(f"\n  {C.ORANGE}{C.BOLD}🔍 TESTADOR DE REGEX{C.RESET}")
        try:
            padrao = input("  Padrão (regex): ").strip()
            if not padrao:
                return
            texto = input("  Texto para testar: ").strip()
            if not texto:
                return

            flags_str = input("  Flags (i=ignorar maiúsc, m=multilinha, Enter=nenhum): ").strip().lower()
            flags = 0
            if "i" in flags_str:
                flags |= _re.IGNORECASE
            if "m" in flags_str:
                flags |= _re.MULTILINE

            try:
                matches = list(_re.finditer(padrao, texto, flags))
            except _re.error as e:
                self.print_nox(f"Regex inválido: {e}")
                return

            if not matches:
                print(f"\n  {C.RED}✗ Nenhuma correspondência encontrada.{C.RESET}\n")
                return

            print(f"\n  {C.GREEN}{C.BOLD}✓ {len(matches)} correspondência(s) encontrada(s):{C.RESET}\n")
            for i, m in enumerate(matches, 1):
                print(f"  {C.YELLOW}Match {i}:{C.RESET} {C.WHITE}{repr(m.group())}{C.RESET}  {C.GRAY}(pos {m.start()}–{m.end()}){C.RESET}")
                if m.groups():
                    for j, g in enumerate(m.groups(), 1):
                        print(f"    {C.GRAY}Grupo {j}:{C.RESET} {C.CYAN}{repr(g)}{C.RESET}")

            # Mostra texto com matches destacados
            print(f"\n  {C.GRAY}Texto marcado:{C.RESET}")
            resultado = _re.sub(padrao, lambda x: f"\033[42m\033[30m{x.group()}\033[0m", texto, flags=flags)
            print(f"  {resultado}\n")

        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_resumo(self):
        """Resume um texto longo usando IA."""
        print(f"\n  {C.CYAN}{C.BOLD}📝 RESUMIDOR DE TEXTO{C.RESET}")
        print(f"  {C.GRAY}Cole o texto (linha em branco para finalizar):{C.RESET}\n")
        try:
            linhas = []
            while True:
                l = input()
                if l == "" and linhas:
                    break
                linhas.append(l)
            texto = "\n".join(linhas).strip()
            if not texto:
                return
            if len(texto) < 100:
                self.print_nox("Texto muito curto para resumir.")
                return

            print(f"\n  {C.GRAY}Resumindo...{C.RESET}")
            estilo = input("  Estilo (1=bullet points  2=parágrafo  Enter=bullet): ").strip() or "1"

            if estilo == "2":
                prompt = f"Resuma o texto abaixo em um parágrafo claro e conciso em português:\n\n{texto}"
            else:
                prompt = f"Resuma o texto abaixo em bullet points (use • como marcador), em português, de forma clara e direta:\n\n{texto}"

            resultado = self._quick_api_call(prompt, max_tokens=400)
            if resultado:
                print(f"\n{C.YELLOW}{C.BOLD}  ╔══ RESUMO ═══════════════════════════════════╗{C.RESET}")
                for linha in resultado.splitlines():
                    print(f"  {C.WHITE}{linha}{C.RESET}")
                print(f"{C.YELLOW}{C.BOLD}  ╚══════════════════════════════════════════════╝{C.RESET}\n")
            else:
                self.print_nox("API não disponível. Configure em /config.")
        except (KeyboardInterrupt, EOFError):
            pass

    def _cmd_habito(self):
        """Rastreador de hábitos diários com histórico."""
        habito_file = "nox_habitos.json"

        def _load():
            if os.path.exists(habito_file):
                try:
                    with open(habito_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return []

        def _save(data):
            try:
                with open(habito_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        habitos = _load()
        hoje = datetime.now().strftime("%Y-%m-%d")

        print(f"\n{C.GREEN}{C.BOLD}  ╔══ RASTREADOR DE HÁBITOS ══════════════════╗{C.RESET}")
        if habitos:
            for i, h in enumerate(habitos, 1):
                feito_hoje = hoje in h.get("registros", [])
                streak = 0
                d = datetime.now()
                while True:
                    ds = d.strftime("%Y-%m-%d")
                    if ds in h.get("registros", []):
                        streak += 1
                        d -= timedelta(days=1)
                    else:
                        break
                icone = f"{C.GREEN}✅{C.RESET}" if feito_hoje else f"{C.RED}○{C.RESET}"
                total = len(h.get("registros", []))
                print(f"  {icone} {i}. {C.WHITE}{h['nome']}{C.RESET}  {C.GRAY}streak: {streak}d | total: {total}d{C.RESET}")
        else:
            print(f"  {C.GRAY}Nenhum hábito cadastrado.{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}")
        print(f"\n  {C.GRAY}[1] Marcar feito hoje  [2] Novo hábito  [3] Remover  [4] Histórico  [Enter] Fechar{C.RESET}")

        try:
            op = input("  Opção: ").strip()

            if op == "1":
                if not habitos:
                    self.print_nox("Nenhum hábito cadastrado.")
                    return
                for i, h in enumerate(habitos, 1):
                    feito = "✅" if hoje in h.get("registros", []) else "○"
                    print(f"  {feito} {i}. {h['nome']}")
                idx_str = input("  Número do hábito (ou 'todos'): ").strip().lower()
                alvos = range(len(habitos)) if idx_str == "todos" else [int(idx_str) - 1]
                for idx in alvos:
                    if 0 <= idx < len(habitos):
                        regs = habitos[idx].setdefault("registros", [])
                        if hoje not in regs:
                            regs.append(hoje)
                            self.print_nox(f"✅ '{habitos[idx]['nome']}' marcado para hoje!")
                            if self.voice_mode:
                                self._speak_async(f"Hábito {habitos[idx]['nome']} concluído!")
                        else:
                            self.print_nox(f"'{habitos[idx]['nome']}' já foi marcado hoje.")
                _save(habitos)

            elif op == "2":
                nome = input("  Nome do hábito: ").strip()
                if nome:
                    habitos.append({"nome": nome, "registros": [], "criado": hoje})
                    _save(habitos)
                    self.print_nox(f"Hábito '{nome}' criado! 💪")

            elif op == "3":
                if not habitos:
                    return
                for i, h in enumerate(habitos, 1):
                    print(f"  {i}. {h['nome']}")
                idx = int(input("  Número para remover: ").strip()) - 1
                if 0 <= idx < len(habitos):
                    nome = habitos.pop(idx)["nome"]
                    _save(habitos)
                    self.print_nox(f"Hábito '{nome}' removido.")

            elif op == "4":
                if not habitos:
                    return
                for i, h in enumerate(habitos, 1):
                    print(f"  {i}. {h['nome']}")
                idx = int(input("  Número para ver histórico: ").strip()) - 1
                if 0 <= idx < len(habitos):
                    h = habitos[idx]
                    regs = sorted(h.get("registros", []), reverse=True)[:14]
                    print(f"\n  {C.YELLOW}{C.BOLD}{h['nome']} — últimos {len(regs)} registros:{C.RESET}")
                    for r in regs:
                        try:
                            d = datetime.strptime(r, "%Y-%m-%d").strftime("%d/%m/%Y (%A)")
                        except Exception:
                            d = r
                        print(f"    {C.GREEN}✓{C.RESET} {C.GRAY}{d}{C.RESET}")
                    print()

        except (ValueError, IndexError, KeyboardInterrupt, EOFError):
            pass

    # ══════════════════════════════════════════
    #  COMANDOS v2.8 FALTANDO
    # ══════════════════════════════════════════

    def _cmd_relogio(self):
        """Exibe relógio em tempo real no terminal."""
        self.print_nox("Relógio em tempo real (pressione Enter para parar):")
        import threading as _th
        stop_flag = [False]

        def _tick():
            while not stop_flag[0]:
                now = datetime.now().strftime("%H:%M:%S  |  %d/%m/%Y")
                print(f"\r  {C.CYAN}{C.BOLD}⏰  {now}{C.RESET}", end="", flush=True)
                time.sleep(1)
            print()

        t = _th.Thread(target=_tick, daemon=True)
        t.start()
        try:
            input()
        except Exception:
            pass
        stop_flag[0] = True
        t.join(timeout=2)

    def _cmd_ascii(self):
        """Converte texto em arte ASCII grande."""
        texto = input(f"  {C.CYAN}Texto para converter em ASCII art: {C.RESET}").strip()
        if not texto:
            self.print_nox("Nenhum texto informado.")
            return
        try:
            import subprocess as _sp, sys as _sys
            # tenta instalar pyfiglet se não tiver
            try:
                import pyfiglet
            except ImportError:
                _sp.check_call([_sys.executable, "-m", "pip", "install", "pyfiglet",
                                "--break-system-packages", "-q"])
                import pyfiglet
            art = pyfiglet.figlet_format(texto, font="standard")
            print(f"\n{C.PURPLE}{art}{C.RESET}")
        except Exception:
            # Fallback manual simples
            print(f"\n  {C.BOLD}{C.CYAN}{texto.upper()}{C.RESET}\n")
            self.print_nox("(pyfiglet não disponível — exibindo texto simples em maiúsculas)")

    def _cmd_ip(self):
        """Exibe o IP local e tenta obter o IP público."""
        import socket as _sock
        try:
            # IP local
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "Não disponível"

        # IP público via API
        public_ip = "Não disponível"
        if REQUESTS_AVAILABLE:
            try:
                import requests as _req
                r = _req.get("https://api.ipify.org?format=json", timeout=5)
                public_ip = r.json().get("ip", "Não disponível")
            except Exception:
                pass

        self.print_nox(
            f"🌐 IP Local  : {C.CYAN}{local_ip}{C.RESET}\n"
            f"   IP Público: {C.GREEN}{public_ip}{C.RESET}"
        )

    # ══════════════════════════════════════════
    #  SISTEMA MULTIAGENTE v4.0
    # ══════════════════════════════════════════

    def _cmd_agente(self):
        """Envia tarefa para o sistema multiagente com Grok."""
        if not MULTIAGENT_AVAILABLE:
            self.print_nox(f"Sistema multiagente indisponível: {_mae_reason}")
            return

        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ NOX MULTIAGENTE ═══════════════════════╗{C.RESET}")
        print(f"  {C.GRAY}+60 agentes especializados coordenados por IA{C.RESET}")
        print(f"  {C.GRAY}Exemplos:{C.RESET}")
        print(f"  {C.CYAN}• crie uma landing page para academia de yoga{C.RESET}")
        print(f"  {C.CYAN}• crie uma API REST em FastAPI para gestão de tarefas{C.RESET}")
        print(f"  {C.CYAN}• crie um e-commerce de roupas{C.RESET}")
        print(f"  {C.CYAN}• escreva um artigo sobre inteligência artificial{C.RESET}")
        print(f"  {C.CYAN}• revise este código para bugs de segurança{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

        try:
            task = input(f"  {C.BOLD}Tarefa para os agentes:{C.RESET} ").strip()
            if not task:
                return

            # NOX_API_KEY (Groq) já está configurada no .env — o grok_client usa automaticamente.
            # Não é necessário pedir chave ao usuário.

            print(f"\n  {C.GRAY}🤖 Orquestrando agentes...{C.RESET}\n")
            start = time.time()

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(_ORCHESTRATOR.process(task))
            finally:
                loop.close()

            elapsed = time.time() - start
            print(f"{C.PURPLE}{C.BOLD}  ╔══ RESULTADO ({elapsed:.1f}s) ══════════════════════╗{C.RESET}")
            for line in result.splitlines():
                print(f"  {C.WHITE}{line}{C.RESET}")
            print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")

            _GLOBAL_MEM.add_long(f"Tarefa: {task[:100]}", source="user", importance=3)

        except (KeyboardInterrupt, EOFError):
            self.print_nox("Cancelado.")
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_agente_status(self):
        """Exibe status completo do sistema multiagente."""
        if not MULTIAGENT_AVAILABLE:
            self.print_nox(f"Sistema multiagente indisponível: {_mae_reason}")
            return

        try:
            status = _ORCHESTRATOR.get_status()
            print(f"\n{C.PURPLE}{C.BOLD}  ╔══ STATUS MULTIAGENTE ═══════════════════════╗{C.RESET}")
            print(f"  {C.CYAN}Times ativos:{C.RESET}   {C.WHITE}{status['teams']}{C.RESET}")
            print(f"  {C.CYAN}Total agentes:{C.RESET}  {C.WHITE}{status['total_agents']}{C.RESET}")
            print(f"  {C.CYAN}Tarefas feitas:{C.RESET} {C.WHITE}{status['tasks_done']}{C.RESET}")
            print(f"  {C.CYAN}Projetos:{C.RESET}       {C.WHITE}{status['projects']}{C.RESET}")
            print(f"\n  {C.YELLOW}{C.BOLD}Times e Agentes:{C.RESET}")
            for team_name, info in status["teams_detail"].items():
                agents = info["agents"]
                print(f"  {C.GREEN}▸ {team_name.upper()}{C.RESET} {C.GRAY}({len(agents)} agentes){C.RESET}")
                if agents:
                    print(f"    {C.GRAY}{", ".join(agents[:8])}{"..." if len(agents) > 8 else ""}{C.RESET}")
            print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_agente_projeto(self):
        """Lista projetos gerados pelo sistema multiagente."""
        if not MULTIAGENT_AVAILABLE:
            self.print_nox("Sistema multiagente indisponível.")
            return
        try:
            projetos = _GLOBAL_MEM.list_projects()
            if not projetos:
                self.print_nox("Nenhum projeto gerado ainda. Use /agente para criar um.")
                return
            print(f"\n{C.CYAN}{C.BOLD}  ╔══ PROJETOS GERADOS ═══════════════════════╗{C.RESET}")
            for p in projetos[-10:]:
                status_cor = C.GREEN if p["status"] == "completed" else C.YELLOW
                n_files = len(p.get("files", {}))
                print(f"  {status_cor}■{C.RESET} [{p['id']}] {C.WHITE}{p['name'][:50]}{C.RESET}")
                print(f"    {C.GRAY}Status: {p['status']} | Arquivos: {n_files} | {p['created_at'][:10]}{C.RESET}")
            print(f"{C.CYAN}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")
            print(f"  {C.GRAY}Use /agente_exportar para salvar em disco.{C.RESET}\n")
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_agente_exportar(self):
        """Exporta arquivos de um projeto para disco."""
        if not MULTIAGENT_AVAILABLE:
            self.print_nox("Sistema multiagente indisponível.")
            return
        try:
            projetos = _GLOBAL_MEM.list_projects()
            if not projetos:
                self.print_nox("Nenhum projeto disponível.")
                return
            for p in projetos[-5:]:
                print(f"  {C.CYAN}[{p['id']}]{C.RESET} {p['name'][:50]}")
            project_id = input("  ID do projeto: ").strip()
            if not project_id:
                return
            print(f"  {C.GRAY}Exportando...{C.RESET}")
            result = export_project(project_id)
            print(f"\n{C.GREEN}{result}{C.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as e:
            self.print_nox(f"Erro: {e}")

    def _cmd_agente_historico(self):
        """Histórico de tarefas do orquestrador."""
        if not MULTIAGENT_AVAILABLE:
            self.print_nox("Sistema multiagente indisponível.")
            return
        history = _ORCHESTRATOR.get_history(10)
        if not history:
            self.print_nox("Nenhuma tarefa registrada.")
            return
        print(f"\n{C.PURPLE}{C.BOLD}  ╔══ HISTÓRICO MULTIAGENTE ══════════════════╗{C.RESET}")
        for h in history:
            print(f"  {C.CYAN}[{h['id']}]{C.RESET} {C.WHITE}{h['input']}{C.RESET}")
            print(f"    {C.GRAY}Times: {", ".join(h['teams'])} | {h['time']}{C.RESET}")
        print(f"{C.PURPLE}{C.BOLD}  ╚════════════════════════════════════════════╝{C.RESET}\n")


    def run(self):
        # ── Verificação de ban ANTES de qualquer coisa ──
        ban_info = check_ban()
        if ban_info:
            self._show_ban_screen(ban_info)
            return  # nunca chega aqui

        self.boot_sequence()

        while self.running:
            try:
                name  = self.user_name or "VOCÊ"
                foco  = f"{C.YELLOW}[FOCO]{C.RESET} " if self.focus_mode else ""
                noite = f"{C.GRAY}[🌙]{C.RESET} " if self.night_mode else ""
                pomo  = f"{C.RED}[🍅]{C.RESET} " if self._pomodoro_active else ""
                nc    = C.GRAY if self.night_mode else C.CYAN
                arrow = f"{noite}{foco}{pomo}{nc}{C.BOLD}{name.upper()} ›{C.RESET} "
                print()
                user_input = input(arrow).strip()
                if not user_input: continue
                response = self.process_message(user_input)
                if response:
                    self.print_separator()
                    self.typing_effect(response)
                    self.print_separator()
                    if self.voice_mode:
                        self._speak_async(response)
            except KeyboardInterrupt:
                print()
                self.print_separator()
                self._cmd_exit()
            except EOFError:
                self._cmd_exit()


if __name__ == "__main__":
    try:
        run_splash()
    except Exception as e:
        print(f"Erro ao iniciar splash screen: {e}")

    _user_id, _username, _role = _auth_flow()

    nox = NoxAI(account_user_id=_user_id, account_username=_username, account_role=_role)
    nox.run()