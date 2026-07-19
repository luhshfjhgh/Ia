# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║       NOX AI — WhatsApp Integration         ║
║    Conecta via QR Code (whatsapp-web.js)    ║
╚══════════════════════════════════════════════╝
  v2 — QR no terminal, auto-reply com IA,
       reader thread corrigido
"""

import os
import sys
import json
import time
import queue
import threading
import subprocess
from pathlib import Path

_DIR         = Path(__file__).parent
_NODE_SCRIPT = _DIR / "whatsapp_bridge.js"
_SESSION_DIR = _DIR / "whatsapp_session"

# ── Estado global ───────────────────────────────────────────────
_process: subprocess.Popen | None = None
_connected    = False
_connecting   = False
_incoming_q: queue.Queue = queue.Queue()
_auto_reply   = False
_auto_prompt  = ""
_on_message_cb = None   # callback externo (legado — mantido para compatibilidade)

# ── Múltiplos callbacks (novos) ─────────────────────────────────
_message_callbacks: list = []   # chamados a cada mensagem recebida
_qr_callbacks:     list = []    # chamados quando QR Code chega
_nox_auto_reply_cb = None       # ref ao callback de auto-reply (para poder remover)

# ══════════════════════════════════════════════════════
#  BRIDGE JS — gerado em disco na primeira execução
#  QR Code impresso direto no terminal via stdout
# ══════════════════════════════════════════════════════

BRIDGE_JS = r"""
const { Client, LocalAuth } = require('whatsapp-web.js');
const fs = require('fs');

// ── Resolve o caminho do Chromium para o puppeteer-core usar ──────────
// whatsapp-web.js depende de puppeteer-core, que NÃO baixa um Chromium
// sozinho — é preciso apontar explicitamente para um executável.
// Tentamos, em ordem:
//   1) Chromium baixado pelo pacote 'puppeteer' completo (instalado junto)
//   2) Google Chrome já instalado no sistema (Windows/Mac/Linux)
//   3) Microsoft Edge já instalado no sistema (Windows)
function resolveExecutablePath() {
    // 1) puppeteer completo (baixa Chromium na instalação)
    try {
        const puppeteer = require('puppeteer');
        const p = puppeteer.executablePath();
        if (p && fs.existsSync(p)) return p;
    } catch (e) { /* pacote 'puppeteer' não disponível */ }

    // 2) Candidatos comuns de Chrome/Edge instalados no sistema
    const candidates = [
        // Windows — Chrome
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        process.env.LOCALAPPDATA ? process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe' : null,
        // Windows — Edge (vem de fábrica em qualquer Windows 10/11)
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        // macOS
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        // Linux
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        '/usr/bin/microsoft-edge',
    ].filter(Boolean);

    for (const c of candidates) {
        try { if (fs.existsSync(c)) return c; } catch (e) {}
    }

    return null; // nenhum encontrado — deixa o puppeteer-core tentar o padrão dele
}

const _execPath = resolveExecutablePath();
if (_execPath) {
    process.stderr.write(`[NOX] Usando navegador: ${_execPath}\n`);
} else {
    process.stderr.write(
        '[NOX] AVISO: nenhum Chrome/Edge/Chromium encontrado automaticamente. ' +
        'Instale o Google Chrome ou rode: npm install puppeteer\n'
    );
}

const _puppeteerConfig = {
    headless: true,
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
    ],
};
if (_execPath) _puppeteerConfig.executablePath = _execPath;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: process.env.SESSION_DIR || './.wwebjs_auth' }),
    puppeteer: _puppeteerConfig,
});

// ── QR Code — envia dados para Python renderizar ──────────────
client.on('qr', qr => {
    process.stdout.write(JSON.stringify({ type: 'qr_data', data: qr }) + '\n');
});

// ── Pronto ────────────────────────────────────────────────────
client.on('ready', () => {
    process.stdout.write(JSON.stringify({ type: 'ready' }) + '\n');
});

// ── Auth OK ───────────────────────────────────────────────────
client.on('authenticated', () => {
    process.stdout.write(JSON.stringify({ type: 'authenticated' }) + '\n');
});

// ── Auth falhou ───────────────────────────────────────────────
client.on('auth_failure', msg => {
    process.stdout.write(JSON.stringify({ type: 'auth_failure', data: msg }) + '\n');
});

// ── Desconectado ──────────────────────────────────────────────
client.on('disconnected', reason => {
    process.stdout.write(JSON.stringify({ type: 'disconnected', data: reason }) + '\n');
});

// ── Mensagem recebida ─────────────────────────────────────────
client.on('message', async msg => {
    // Protege contra erro "No LID for user" do WhatsApp novo
    let name = msg.from;
    try {
        const contact = await msg.getContact();
        name = contact.pushname || contact.name || msg.from;
    } catch(e) {
        // LID não resolvido — usa o ID bruto mesmo
    }

    // Normaliza o remetente: prefere número @c.us, ignora LID
    let from = msg.from;
    if (msg.author) from = msg.author; // mensagem de grupo
    // Se vier no formato LID (ex: 123456789@lid), tenta pegar número do ID
    if (from.endsWith('@lid') && msg.id && msg.id.remote) {
        from = msg.id.remote;
    }

    // reply_to: usa msg.id.remote que sempre tem o número @c.us correto
    const replyTo = (msg.id && msg.id.remote) ? msg.id.remote : from;

    const payload = {
        type:    'message',
        from:    from,
        reply_to: replyTo,
        msg_id:  msg.id._serialized,
        name:    name,
        body:    msg.body,
        isGroup: msg.from.includes('@g.us'),
        id:      msg.id._serialized,
        ts:      new Date().toISOString(),
    };
    process.stdout.write(JSON.stringify(payload) + '\n');
    // Guarda a última mensagem por remetente para poder usar reply()
    global._lastMsg = global._lastMsg || {};
    global._lastMsg[from] = msg;
});

// ── Comandos do Python via stdin ──────────────────────────────
let buffer = '';
process.stdin.on('data', async data => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop(); // guarda linha incompleta
    for (const line of lines) {
        if (!line.trim()) continue;
        let cmd;
        try { cmd = JSON.parse(line.trim()); } catch { continue; }

        if (cmd.action === 'send') {
            try {
                const to = cmd.to;
                // ── Estratégia anti-LID ───────────────────────────────────
                // O erro "No LID for user" acontece quando o whatsapp-web.js
                // tenta resolver o identificador do contato e ele ainda não
                // está mapeado para o novo sistema de contas do WhatsApp.
                // Solução: usar getChatById() e chat.sendMessage() em vez de
                // client.sendMessage() direto — o WhatsApp resolve o LID
                // internamente quando acessa pelo objeto chat.
                // Fallback 1: reply() na última mensagem (mais seguro de todos)
                // Fallback 2: getChatById + chat.sendMessage
                // Fallback 3: client.sendMessage (última tentativa)
                const lastMsg = global._lastMsg && global._lastMsg[to];
                if (lastMsg) {
                    await lastMsg.reply(cmd.text);
                } else {
                    try {
                        const chat = await client.getChatById(to);
                        await chat.sendMessage(cmd.text);
                    } catch (lidErr) {
                        // se ainda falhar, tenta o método direto como último recurso
                        await client.sendMessage(to, cmd.text);
                    }
                }
                process.stdout.write(JSON.stringify({ type: 'sent', to: to }) + '\n');
            } catch(e) {
                process.stdout.write(JSON.stringify({ type: 'error', data: e.message }) + '\n');
            }

        } else if (cmd.action === 'send_media') {
            try {
                const fs = require('fs');
                const path = require('path');
                const { MessageMedia } = require('whatsapp-web.js');

                const filePath = cmd.path;
                if (!fs.existsSync(filePath)) {
                    throw new Error('Arquivo não encontrado: ' + filePath);
                }

                const ext = path.extname(filePath).toLowerCase();
                const mimeMap = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png',  '.gif':  'image/gif',
                    '.webp':'image/webp', '.bmp':  'image/bmp',
                    '.heic':'image/heic',
                    '.mp4': 'video/mp4',  '.mov':  'video/quicktime',
                    '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska',
                    '.webm':'video/webm', '.3gp':  'video/3gpp',
                    '.pdf': 'application/pdf',
                    '.doc': 'application/msword',
                    '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.ppt': 'application/vnd.ms-powerpoint',
                    '.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    '.txt': 'text/plain', '.csv':  'text/csv',
                    '.mp3': 'audio/mpeg', '.wav':  'audio/wav',
                    '.ogg': 'audio/ogg',  '.m4a':  'audio/mp4',
                    '.flac':'audio/flac',
                };
                const mime     = mimeMap[ext] || 'application/octet-stream';
                const data     = fs.readFileSync(filePath).toString('base64');
                const filename = path.basename(filePath);
                const media    = new MessageMedia(mime, data, filename);
                const caption  = cmd.caption || '';
                const opts     = { caption };

                // Mesma estratégia anti-LID do send de texto
                const lastMsg = global._lastMsg && global._lastMsg[cmd.to];
                if (lastMsg) {
                    await lastMsg.reply(media, null, opts);
                } else {
                    try {
                        const chat = await client.getChatById(cmd.to);
                        await chat.sendMessage(media, opts);
                    } catch (lidErr) {
                        await client.sendMessage(cmd.to, media, opts);
                    }
                }
                process.stdout.write(JSON.stringify({ type: 'sent', to: cmd.to, file: filename }) + '\n');
            } catch(e) {
                process.stdout.write(JSON.stringify({ type: 'error', data: 'send_media: ' + e.message }) + '\n');
            }
        } else if (cmd.action === 'get_chats') {
            try {
                const chats = await client.getChats();
                const list  = chats.slice(0, 25).map(c => ({
                    id:   c.id._serialized,
                    name: c.name || c.id.user,
                    unread: c.unreadCount,
                }));
                process.stdout.write(JSON.stringify({ type: 'chats', data: list }) + '\n');
            } catch(e) {
                process.stdout.write(JSON.stringify({ type: 'error', data: e.message }) + '\n');
            }
        } else if (cmd.action === 'get_contacts') {
            try {
                const contacts = await client.getContacts();
                const list = contacts.filter(c => c.isMyContact).slice(0,50).map(c=>({
                    id:   c.id._serialized,
                    name: c.pushname || c.name || c.id.user,
                    number: c.number,
                }));
                process.stdout.write(JSON.stringify({ type: 'contacts', data: list }) + '\n');
            } catch(e) {
                process.stdout.write(JSON.stringify({ type: 'error', data: e.message }) + '\n');
            }
        } else if (cmd.action === 'logout') {
            await client.logout();
            process.exit(0);
        } else if (cmd.action === 'ping') {
            process.stdout.write(JSON.stringify({ type: 'pong' }) + '\n');
        }
    }
});

process.on('SIGTERM', () => { client.destroy(); process.exit(0); });

client.initialize().catch(err => {
    process.stdout.write(JSON.stringify({
        type: 'error',
        data: 'Falha ao iniciar o navegador (Puppeteer): ' + (err && err.message ? err.message : String(err))
    }) + '\n');
    process.stderr.write(
        '[NOX] Dica: instale o pacote puppeteer completo para baixar um Chromium automaticamente:\n' +
        '      cd communication && npm install puppeteer\n' +
        '      Ou instale o Google Chrome no sistema.\n'
    );
});
"""


# ══════════════════════════════════════════════════════
#  SETUP — verifica Node e instala dependências
# ══════════════════════════════════════════════════════

import shutil
import platform

IS_WIN = platform.system() == "Windows"


def _find_cmd(name: str) -> str | None:
    """
    Encontra o executável correto no Windows (npm → npm.cmd)
    e em outros sistemas. Retorna None se não encontrar.
    """
    # No Windows npm e npx são scripts .cmd
    candidates = [name]
    if IS_WIN:
        candidates = [name + ".cmd", name + ".ps1", name]
    for c in candidates:
        if shutil.which(c):
            return c
    return None


def _check_node() -> bool:
    node = _find_cmd("node")
    if not node:
        return False
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _check_packages() -> bool:
    """
    Verifica se whatsapp-web.js E o pacote 'puppeteer' completo (que baixa
    seu próprio Chromium) estão instalados. Sem o puppeteer completo, o
    whatsapp-web.js usa apenas puppeteer-core, que NÃO baixa navegador
    nenhum sozinho — e o cliente trava com TimeoutError ao tentar abrir
    o navegador.
    """
    has_wpp       = (_DIR / "node_modules" / "whatsapp-web.js").exists()
    has_puppeteer = (_DIR / "node_modules" / "puppeteer").exists()
    return has_wpp and has_puppeteer


def setup_whatsapp() -> tuple[bool, str]:
    """
    Garante que Node e pacotes estão disponíveis.
    Retorna (ok, mensagem).
    """
    node = _find_cmd("node")
    npm  = _find_cmd("npm")

    if not node:
        return (False,
            "❌ Node.js não encontrado!\n"
            "   Instale em: https://nodejs.org (versão 18 LTS ou superior)\n"
            "   Após instalar, FECHE e REABRA o terminal."
        )

    if not npm:
        return (False,
            "❌ npm não encontrado no PATH!\n"
            "   O npm vem junto com o Node.js.\n"
            "   Tente reinstalar o Node.js e reabra o terminal."
        )

    if not _check_packages():
        print("  ⏳ Instalando dependências Node.js (whatsapp-web.js + puppeteer)...")
        print("  ⏳ O puppeteer baixa um Chromium próprio (~200MB) — pode levar alguns minutos na primeira vez...")
        try:
            r = subprocess.run(
                [npm, "install", "whatsapp-web.js", "puppeteer"],
                cwd=str(_DIR),
                capture_output=False,
                timeout=600,   # puppeteer baixa um Chromium inteiro — mais tempo de margem
                shell=IS_WIN,   # no Windows precisa de shell=True para .cmd
            )
            if r.returncode != 0:
                return (False, "❌ Erro ao instalar dependências npm. Verifique sua conexão.")
        except subprocess.TimeoutExpired:
            return (False,
                "❌ Instalação demorou demais (mais de 10 minutos). "
                "Verifique sua conexão com a internet e tente novamente."
            )
        except FileNotFoundError:
            return (False,
                f"❌ npm não encontrado ({npm}).\n"
                "   Reinstale o Node.js em https://nodejs.org e reabra o terminal."
            )

    # Grava o bridge JS
    _NODE_SCRIPT.write_text(BRIDGE_JS, encoding="utf-8")
    return (True, "✅ Dependências OK.")


# ══════════════════════════════════════════════════════
#  READER THREAD — lê stdout do Node linha a linha
# ══════════════════════════════════════════════════════

def _reader_thread(proc: subprocess.Popen):
    """
    Lê cada linha JSON do processo Node e despacha eventos.
    Roda em daemon thread — morre quando o programa fecha.
    """
    global _connected, _connecting

    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            # linha não-JSON do Node — imprime como debug
            print(f"  [node] {line}")
            continue

        t = obj.get("type")

        if t == "qr_data":
            qr_raw = obj.get("data", "")
            # Renderiza o QR Code no terminal usando Python (sem depender do Node)
            try:
                import qrcode as _qrlib
                qr_obj = _qrlib.QRCode(
                    error_correction=_qrlib.constants.ERROR_CORRECT_L,
                    box_size=1,
                    border=1,
                )
                qr_obj.add_data(qr_raw)
                qr_obj.make(fit=True)
                print("\n")
                qr_obj.print_ascii(invert=True)
                print("  📱 Escaneie o QR Code acima com seu WhatsApp!")
                print("  (WhatsApp > Aparelhos conectados > Conectar aparelho)\n")
            except (ImportError, OSError, Exception):
                print("\n  [QR] Instale qrcode: pip install qrcode")
                print(f"  [QR Bruto] {qr_raw[:60]}...\n")
            # Notifica callbacks de QR (ex: interface gráfica voice_ui)
            for _cb in list(_qr_callbacks):
                try:
                    _cb(qr_raw)
                except Exception as _e:
                    print(f"  [wpp] qr_callback erro: {_e}")

        elif t == "authenticated":
            print("\n  🔐 WhatsApp autenticado! Aguardando inicialização...\n")

        elif t == "ready":
            _connected  = True
            _connecting = False
            print("\n  ✅ WhatsApp conectado com sucesso! 🟢")
            print("  Use /wpp_enviar para enviar mensagens")
            print("  Use /wpp_auto para ativar resposta automática\n")

        elif t == "disconnected":
            _connected  = False
            _connecting = False
            print(f"\n  ⚠️  WhatsApp desconectado: {obj.get('data')}\n")

        elif t == "auth_failure":
            _connected  = False
            _connecting = False
            print(f"\n  ❌ Falha na autenticação WhatsApp: {obj.get('data')}\n")

        elif t == "message":
            _incoming_q.put(obj)
            # Notifica todos os callbacks registrados
            for _cb in list(_message_callbacks):
                try:
                    _cb(obj)
                except Exception as _e:
                    print(f"  [wpp] message_callback erro: {_e}")
            # Mantém compatibilidade com callback legado
            if _on_message_cb:
                try:
                    _on_message_cb(obj)
                except Exception as e:
                    print(f"  [wpp] Erro no callback: {e}")

        elif t == "chats":
            _incoming_q.put(obj)   # quem pediu vai buscar

        elif t == "contacts":
            _incoming_q.put(obj)

        elif t in ("sent", "pong"):
            pass  # silencioso

        elif t == "error":
            print(f"\n  ❌ Erro WhatsApp: {obj.get('data')}\n")
            # Se o erro veio durante a tentativa de conexão (ex: falha do
            # Puppeteer ao abrir o navegador), reseta o estado para não
            # ficar travado em "conectando" pra sempre.
            if not _connected:
                _connecting = False
            _incoming_q.put(obj)


def _stderr_thread(proc: subprocess.Popen):
    """
    Repassa o stderr do Node direto para o terminal.
    É aqui que o QR Code aparece (qrcode-terminal escreve no stderr).
    """
    for line in proc.stderr:
        sys.stdout.write(line)
        sys.stdout.flush()


# ══════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════

def connect(on_message_cb=None) -> tuple[bool, str]:
    """
    Inicia o cliente WhatsApp.
    Retorna (ok, mensagem).
    """
    global _process, _connected, _connecting, _on_message_cb

    if _process and _process.poll() is None:
        return (True, "WhatsApp já está rodando.")

    ok, msg = setup_whatsapp()
    if not ok:
        return (False, msg)

    _on_message_cb = on_message_cb
    env = os.environ.copy()
    env["SESSION_DIR"] = str(_SESSION_DIR)

    node = _find_cmd("node")
    if not node:
        return (False, "❌ Node.js não encontrado. Instale em https://nodejs.org e reabra o terminal.")

    try:
        _process = subprocess.Popen(
            [node, str(_NODE_SCRIPT)],
            cwd=str(_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",   # Node sempre emite UTF-8; sem isso o Windows
            errors="replace",  # usa cp1252 e quebra com nomes/emoji acentuados
            bufsize=1,
            env=env,
            shell=False,
        )
    except FileNotFoundError:
        return (False, f"❌ Node.js não encontrado em: {node}\n   Reinstale em https://nodejs.org")
    except Exception as e:
        return (False, f"❌ Falha ao iniciar processo Node: {e}")

    _connecting = True

    # Thread que lê stdout (eventos JSON)
    threading.Thread(target=_reader_thread, args=(_process,), daemon=True).start()
    # Thread que repassa stderr → terminal (QR Code aparece aqui)
    threading.Thread(target=_stderr_thread, args=(_process,), daemon=True).start()

    return (True, "⏳ Iniciando WhatsApp... O QR Code vai aparecer em alguns segundos.")


def disconnect() -> str:
    global _process, _connected, _connecting
    if not _process or _process.poll() is not None:
        return "WhatsApp não está conectado."
    try:
        _send_cmd({"action": "logout"})
        time.sleep(1)
        _process.terminate()
        _process    = None
        _connected  = False
        _connecting = False
        return "📴 WhatsApp desconectado."
    except Exception as e:
        return f"❌ Erro: {e}"


def is_connected() -> bool:
    return _connected and _process is not None and _process.poll() is None


def is_connecting() -> bool:
    return _connecting and not _connected


def _send_cmd(cmd: dict):
    global _process
    if _process and _process.stdin and _process.poll() is None:
        try:
            _process.stdin.write(json.dumps(cmd) + "\n")
            _process.stdin.flush()
        except BrokenPipeError:
            pass


def send_message(to: str, text: str) -> str:
    if not is_connected():
        return "❌ WhatsApp não conectado. Use /wpp para conectar."
    # Normaliza número
    if not to.endswith("@c.us") and not to.endswith("@g.us"):
        to = re.sub(r"[^\d]", "", to)
        to = to + "@c.us"
    _send_cmd({"action": "send", "to": to, "text": text})
    return f"📤 Mensagem enviada!"


def send_media(to: str, file_path: str, caption: str = "") -> str:
    """
    Envia um arquivo (foto, vídeo, documento ou áudio) do disco local.

    Parâmetros:
      to        — ID do contato (ex: '5511999999999@c.us')
      file_path — caminho absoluto do arquivo no disco
      caption   — legenda opcional (aparece embaixo da mídia no WhatsApp)

    Retorna mensagem de status.
    """
    import os as _os
    if not is_connected():
        return "❌ WhatsApp não conectado."
    if not _os.path.exists(file_path):
        return f"❌ Arquivo não encontrado: {file_path}"
    # Normaliza separadores (Windows usa \\ mas JSON precisa de \\\\)
    file_path = _os.path.normpath(_os.path.abspath(file_path))
    # Normaliza número
    if not to.endswith("@c.us") and not to.endswith("@g.us"):
        to = re.sub(r"[^\d]", "", to)
        to = to + "@c.us"
    _send_cmd({"action": "send_media", "to": to, "path": file_path, "caption": caption})
    return f"📤 Enviando {_os.path.basename(file_path)}..."


def request_chats():
    _send_cmd({"action": "get_chats"})


def request_contacts():
    _send_cmd({"action": "get_contacts"})


def get_pending(timeout: float = 1.5) -> list[dict]:
    """Pega eventos da fila com timeout."""
    msgs = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msgs.append(_incoming_q.get(timeout=0.1))
        except queue.Empty:
            break
    return msgs


def set_auto_reply(enabled: bool, prompt: str = "") -> str:
    global _auto_reply, _auto_prompt
    _auto_reply  = enabled
    _auto_prompt = prompt
    status = "✅ ATIVADA" if enabled else "❌ DESATIVADA"
    return f"Resposta automática {status}."


def get_auto_reply_state() -> tuple[bool, str]:
    return _auto_reply, _auto_prompt


# ══════════════════════════════════════════════════════
#  GERENCIAMENTO DE MÚLTIPLOS CALLBACKS (novo)
# ══════════════════════════════════════════════════════

def add_message_callback(fn) -> None:
    """Registra um callback chamado a cada mensagem recebida."""
    if fn not in _message_callbacks:
        _message_callbacks.append(fn)


def remove_message_callback(fn) -> None:
    """Remove um callback de mensagem."""
    if fn in _message_callbacks:
        _message_callbacks.remove(fn)


def add_qr_callback(fn) -> None:
    """Registra um callback chamado quando QR Code chegar."""
    if fn not in _qr_callbacks:
        _qr_callbacks.append(fn)


def remove_qr_callback(fn) -> None:
    """Remove um callback de QR Code."""
    if fn in _qr_callbacks:
        _qr_callbacks.remove(fn)


def status_str() -> str:
    if is_connected():
        return "🟢 WhatsApp conectado e pronto."
    if is_connecting():
        return "🟡 WhatsApp conectando... aguarde o QR Code."
    return "🔴 WhatsApp desconectado. Use /wpp para conectar."


# import necessário para send_message
import re
