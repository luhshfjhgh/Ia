"""
NOX AI — Interface Gráfica de Voz (voice_ui.py)
================================================

Este módulo é ativado quando o usuário digita /conversa no terminal.
Ele abre a interface gráfica (index.html via pywebview) e conecta
todos os botões da toolbar com a IA do main.py:

  • VOICE  — liga/desliga microfone (STT -> IA -> TTS)
  • VISION — liga/desliga câmera (captura frames com OpenCV)
  • CHAT   — envia texto digitado para a IA
  • INPUT  — muta/desmuta o microfone sem fechar o modo voz
  • MODULES — abre/fecha painel de status dos módulos

Como usar:
    1. No main.py o comando /conversa chama launch_voice_ui(nox)
    2. A janela abre, a IA começa a ouvir automaticamente
    3. Feche a janela ou diga "tchau" para voltar ao terminal
"""

import os
import sys
import threading
import time
import queue
import asyncio
import tempfile

# ── pywebview ──────────────────────────────────────────────────────────────
try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False

# ── câmera (opcional) ──────────────────────────────────────────────────────
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ── WhatsApp Skill (opcional) ──────────────────────────────────────────────
try:
    import whatsapp_skill as _wpp_skill
    import whatsapp_bot   as _wpp
    WPP_SKILL_AVAILABLE = True
except ImportError:
    WPP_SKILL_AVAILABLE = False
    _wpp_skill = None
    _wpp       = None

# ── diretório base deste arquivo ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")


# ══════════════════════════════════════════════════════════════════════════
#  CLASSE API  (ponte Python ↔ JavaScript da interface)
# ══════════════════════════════════════════════════════════════════════════

class NoxWebApi:
    """
    Todos os métodos públicos ficam acessíveis no JS como:
        window.pywebview.api.nome_do_metodo(args)
    """

    def __init__(self, nox_instance):
        self.nox = nox_instance          # instância do NoxAI (main.py)
        self._window = None              # referência à janela (definida após criação)
        self._mic_active = False
        self._muted = False
        self._cam_active = False
        self._cam_thread = None
        self._cam_running = False
        self._nox_camera  = None   # instancia de NoxCamera (camera.py)
        self._voice_thread = None
        self._voice_running = False
        self._log_queue = queue.Queue()  # logs para empurrar à interface

        # ── WhatsApp ────────────────────────────────────────────────
        self._wpp_qr_cb_registered = False  # callback de QR já registrado?

    # ── referência à janela ──────────────────────────────────────────────

    def set_window(self, win):
        self._window = win

    # ── utilitário: envia linha de log para a interface ──────────────────

    def push_log(self, line: str):
        """Empurra uma linha para o log da interface (thread-safe)."""
        if self._window:
            safe = line.replace("`", "'").replace("\\", "/")
            try:
                self._window.evaluate_js(
                    f"logLines = [...logLines.slice(-6), `{safe}`]; renderLog();"
                )
            except Exception:
                pass

    def push_status(self, label: str, active: bool):
        """Atualiza o status central da interface."""
        if self._window:
            js_active = "true" if active else "false"
            safe = label.replace("`", "'")
            try:
                self._window.evaluate_js(f"setStatus(`{safe}`, {js_active});")
            except Exception:
                pass

    # ══════════════════════════════════════════
    #  BOTÃO VOICE — microfone principal
    # ══════════════════════════════════════════

    def toggle_mic(self, active: bool):
        """
        Chamado pelo botão VOICE da toolbar.
        Liga o loop de conversa por voz em background.
        """
        self._mic_active = active

        if active:
            self.push_log("› microfone armado")
            self.push_status("LISTENING", True)
            self._muted = False
            self._start_voice_loop()
            # Inicia monitor de mensagens WhatsApp (se disponível)
            if WPP_SKILL_AVAILABLE:
                _wpp_skill.start_message_monitor(
                    speak_fn=self.nox._speak_blocking,
                    log_fn=self.push_log,
                    nox=self.nox,
                )
                self._setup_wpp_qr_hook()
        else:
            self.push_log("› microfone desarmado")
            self.push_status("SYSTEM STANDBY", False)
            self._stop_voice_loop()
            # Para monitor WhatsApp
            if WPP_SKILL_AVAILABLE:
                _wpp_skill.stop_message_monitor()

        return {"ok": True, "active": active}

    def _start_voice_loop(self):
        """Inicia thread de escuta contínua."""
        if self._voice_running:
            return
        self._voice_running = True
        self._voice_thread = threading.Thread(
            target=self._voice_loop_worker, daemon=True
        )
        self._voice_thread.start()

    def _stop_voice_loop(self):
        """Para a thread de escuta."""
        self._voice_running = False
        # Sinaliza ao nox que saiu do modo voz
        self.nox.voice_chat = False

    def _voice_loop_worker(self):
        """
        Worker da thread de voz:
        Ouve → verifica se é comando WhatsApp → manda para a IA → fala → repete.
        """
        self.nox.voice_chat = True
        old_voice_mode = self.nox.voice_mode
        self.nox.voice_mode = True

        self.push_log("› modo conversa iniciado")
        intro = "Interface gráfica ativa. Pode falar!"
        self.nox._speak_blocking(intro)

        while self._voice_running and self.nox.running:
            # Mudo: não ouve, mas mantém loop ativo
            if self._muted:
                time.sleep(0.3)
                continue

            user_text = self.nox.listen_vad()
            if not user_text:
                continue

            # Palavras de saída
            if any(w in user_text.lower() for w in ["sair", "encerrar", "tchau", "fechar"]):
                self.push_log("› conversa encerrada por voz")
                self.push_status("SYSTEM STANDBY", False)
                self._voice_running = False
                self.nox.voice_chat = False
                # Desativa botão mic na interface
                if self._window:
                    try:
                        self._window.evaluate_js(
                            "const b=document.querySelector('.tbtn[data-key=\"mic\"]');"
                            "if(b){b.classList.remove('active');"
                            "b.innerHTML=ICONS.mic(GOLD)+'<span class=\"tag\">VOICE</span>';}"
                        )
                    except Exception:
                        pass
                self.nox._speak_blocking("Até mais!")
                break

            self.push_log(f"› você: {user_text[:40]}")
            self.push_status("PROCESSING", True)

            # ── Verifica intenção WhatsApp ANTES de chamar a IA ─────────
            response = None
            if WPP_SKILL_AVAILABLE:
                wpp_intent = _wpp_skill.detect_intent(user_text)
                if wpp_intent:
                    self.push_log(f"› [WPP] ação: {wpp_intent['intent']}")

                    def _wpp_speak(txt: str):
                        if hasattr(self.nox, "_speak_interruptible"):
                            self.nox._speak_interruptible(txt)
                        else:
                            self.nox._speak_blocking(txt)

                    response = _wpp_skill.handle_intent(
                        wpp_intent,
                        self.nox,
                        speak_fn  = _wpp_speak,
                        listen_fn = self.nox.listen_vad,
                        qr_callback = self._show_wpp_qr,
                    )

            # ── Sem intenção WhatsApp → processa com a IA normalmente ────
            if response is None:
                response = self.nox._process_and_respond(user_text)

            if response:
                short = response[:60] + ("..." if len(response) > 60 else "")
                self.push_log(f"› nox: {short}")
                self.push_status("SPEAKING", True)
                # ── Fala interrompível (barge-in): se o usuário começar a
                #    falar por cima, a NOX para na hora e volta a ouvir.
                #    hasattr() garante compatibilidade com versões antigas
                #    do main.py que não tenham esse método ainda.
                if hasattr(self.nox, "_speak_interruptible"):
                    interrompida = self.nox._speak_interruptible(response)
                    if interrompida:
                        self.push_log("› (interrompida — pode falar)")
                else:
                    self.nox._speak_blocking(response)
                self.push_status("LISTENING", True)

        self.nox.voice_mode = old_voice_mode
        self._mic_active = False

    # ══════════════════════════════════════════════════════
    #  WHATSAPP — QR Code na interface gráfica
    # ══════════════════════════════════════════════════════

    def _setup_wpp_qr_hook(self):
        """Registra o callback de QR no whatsapp_bot (uma vez só)."""
        if not WPP_SKILL_AVAILABLE or self._wpp_qr_cb_registered:
            return
        _wpp.add_qr_callback(self._show_wpp_qr)
        self._wpp_qr_cb_registered = True

    def _show_wpp_qr(self, qr_data: str):
        """
        Recebe o dado bruto do QR Code e exibe um overlay na interface.
        Chamado pelo whatsapp_bot quando o QR chega.
        """
        if not self._window:
            return

        # Gera imagem PNG base64
        img_src = None
        if WPP_SKILL_AVAILABLE:
            img_src = _wpp_skill.qr_data_to_base64_png(qr_data)

        if img_src:
            # Exibe QR como imagem na interface
            js = f"""
(function() {{
    let ov = document.getElementById('nox-wpp-qr-overlay');
    if (!ov) {{
        ov = document.createElement('div');
        ov.id = 'nox-wpp-qr-overlay';
        ov.style.cssText = `
            position:fixed; top:0; left:0; width:100%; height:100%;
            background:rgba(5,4,8,0.88); z-index:9999;
            display:flex; flex-direction:column; align-items:center;
            justify-content:center; gap:18px;
        `;
        ov.innerHTML = `
            <div style="color:#FFD27A;font-size:11px;letter-spacing:0.35em;
                        font-family:'Courier New',monospace;margin-bottom:4px;">
                WHATSAPP — ESCANEIE O QR CODE
            </div>
            <img id="nox-wpp-qr-img"
                 style="width:240px;height:240px;border-radius:12px;
                        border:3px solid rgba(255,210,122,0.4);background:#fff;padding:4px;"
                 src="{img_src}" alt="QR Code" />
            <div style="color:rgba(255,235,200,0.6);font-size:10px;
                        letter-spacing:0.2em;text-align:center;">
                WhatsApp &gt; Aparelhos Conectados &gt; Conectar Aparelho
            </div>
            <button onclick="document.getElementById('nox-wpp-qr-overlay').remove()"
                style="margin-top:8px;background:rgba(255,210,122,0.12);
                       border:1px solid rgba(255,210,122,0.3);border-radius:8px;
                       color:#FFD27A;padding:8px 22px;cursor:pointer;
                       font-size:10px;letter-spacing:0.3em;font-family:inherit;">
                FECHAR
            </button>
        `;
        document.body.appendChild(ov);
    }} else {{
        const img = document.getElementById('nox-wpp-qr-img');
        if (img) img.src = '{img_src}';
    }}
}})();
"""
        else:
            # Sem PIL: mostra aviso de texto
            js = """
(function() {
    let ov = document.getElementById('nox-wpp-qr-overlay');
    if (!ov) {
        ov = document.createElement('div');
        ov.id = 'nox-wpp-qr-overlay';
        ov.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
            'background:rgba(5,4,8,0.88);z-index:9999;display:flex;' +
            'flex-direction:column;align-items:center;justify-content:center;gap:14px;';
        ov.innerHTML = '<div style=\"color:#FFD27A;font-size:12px;letter-spacing:0.3em\">' +
            'QR CODE NO TERMINAL — instale: pip install qrcode pillow' +
            '</div><button onclick=\"this.parentElement.remove()\" ' +
            'style=\"color:#FFD27A;background:rgba(255,210,122,0.1);border:1px solid rgba(255,210,122,0.3);' +
            'border-radius:8px;padding:8px 22px;cursor:pointer;letter-spacing:0.3em\">FECHAR</button>';
        document.body.appendChild(ov);
    }
})();
"""

        try:
            self._window.evaluate_js(js)
        except Exception:
            pass

        self.push_log("› 📱 QR Code do WhatsApp exibido!")
        self.push_status("WPP — ESCANEIE O QR", True)

    def wpp_hide_qr(self):
        """Remove o overlay do QR Code (chamado pelo JS ou quando conectar)."""
        if self._window:
            try:
                self._window.evaluate_js(
                    "const ov=document.getElementById('nox-wpp-qr-overlay');"
                    "if(ov)ov.remove();"
                )
            except Exception:
                pass

    # ══════════════════════════════════════════
    #  BOTÃO INPUT — muta/desmuta microfone
    # ══════════════════════════════════════════

    def toggle_mute(self, muted: bool):
        """
        Chamado pelo botão INPUT da toolbar.
        Muta o microfone sem encerrar o modo conversa.
        """
        self._muted = muted
        status = "MUTED" if muted else ("LISTENING" if self._mic_active else "SYSTEM STANDBY")
        self.push_log(f"› microfone {'mutado' if muted else 'desmutado'}")
        self.push_status(status, not muted and self._mic_active)
        return {"ok": True, "muted": muted}

    # ══════════════════════════════════════════
    #  BOTÃO VISION — câmera
    # ══════════════════════════════════════════

    def toggle_camera(self, active: bool):
        """
        Chamado pelo botao VISION da toolbar.
        Abre/fecha a camera com deteccao de objetos (camera.py).
        """
        self._cam_active = active

        if active:
            # Usa NoxCamera (camera.py) se disponivel
            if CAMERA_MODULE_OK:
                self.push_log("› [VISION] iniciando deteccao de objetos...")
                self._nox_camera = NoxCamera(
                    log_fn=self.push_log,
                    confidence=0.45,
                    camera_index=0,
                )
                self._nox_camera.start()
                self._cam_running = True
            elif CV2_AVAILABLE:
                # fallback: camera simples sem deteccao
                self.push_log("› camera simples (instale ultralytics para deteccao)")
                self._cam_running = True
                self._cam_thread = threading.Thread(
                    target=self._cam_worker_simple, daemon=True
                )
                self._cam_thread.start()
            else:
                self.push_log("› [VISION] instale opencv: pip install opencv-python")
                return {"ok": False, "reason": "opencv not available"}
        else:
            self.push_log("› [VISION] camera desativada")
            self._cam_running = False
            if self._nox_camera:
                self._nox_camera.stop()
                self._nox_camera = None

        return {"ok": True, "active": active}

    def _cam_worker_simple(self):
        """Fallback: camera sem deteccao de objetos (apenas overlay NOX)."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.push_log("› erro: camera nao encontrada")
            self._cam_running = False
            self._cam_active = False
            return

        self.push_log("› camera aberta — pressione Q para fechar")
        while self._cam_running:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.putText(
                frame, "NOX AI — VISION (sem deteccao)", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 210, 122), 2
            )
            cv2.imshow("NOX AI — VISION", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

        cap.release()
        cv2.destroyAllWindows()
        self._cam_running = False
        self._cam_active = False
        self.push_log("› camera fechada")
    # ══════════════════════════════════════════
    #  BOTÃO CHAT — enviar texto para a IA
    # ══════════════════════════════════════════

    def send_message(self, text: str):
        """
        Chamado pelo campo de chat (botão CHAT) da interface.
        Retorna a resposta da IA como string.
        """
        if not text or not text.strip():
            return ""

        self.push_log(f"› chat: {text[:40]}")
        self.push_status("PROCESSING", True)

        response = self.nox._process_and_respond(text.strip())

        if response:
            short = response[:60] + ("..." if len(response) > 60 else "")
            self.push_log(f"› nox: {short}")
            if self.nox.voice_mode or self._mic_active:
                threading.Thread(
                    target=self.nox._speak_blocking, args=(response,), daemon=True
                ).start()

        self.push_status(
            "LISTENING" if self._mic_active else "SYSTEM STANDBY",
            self._mic_active
        )
        return response or ""

    # ══════════════════════════════════════════
    #  BOTÃO MODULES — status dos módulos
    # ══════════════════════════════════════════

    def get_modules_status(self):
        """
        Retorna um dict com o status dos principais módulos da IA.
        Chamado pelo botão MODULES da toolbar.
        """
        try:
            import speech_recognition  # noqa
            stt_ok = True
        except ImportError:
            stt_ok = False

        try:
            import edge_tts  # noqa
            tts_ok = True
        except ImportError:
            tts_ok = False

        return {
            "stt":      stt_ok,
            "tts":      tts_ok,
            "cam":      CV2_AVAILABLE,
            "voice":    self._mic_active,
            "muted":    self._muted,
            "cam_on":   self._cam_active,
            "wpp":      (_wpp.is_connected() if WPP_SKILL_AVAILABLE else False),
            "model":    self.nox.config.get("model", "desconhecido")
                        if hasattr(self.nox, "config") else "—",
            "personality": getattr(self.nox, "personality", "—"),
        }


# ══════════════════════════════════════════════════════════════════════════
#  PATCH no index.html: adiciona handlers JS para os novos botões
# ══════════════════════════════════════════════════════════════════════════

EXTRA_JS = """
<script>
// ── NOX voice_ui.py — handlers dos botões extras ──────────────────────

// Estado local dos botões
let _camActive = false;
let _muted     = false;
let _chatOpen  = false;
let _modOpen   = false;

// ── helpers ──────────────────────────────────────────────────────────

function apiCall(method, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
    return window.pywebview.api[method](...args);
  }
  return Promise.resolve(null);
}

function setButtonActive(key, on) {
  const btn = document.querySelector(`.tbtn[data-key="${key}"]`);
  if (!btn) return;
  btn.classList.toggle("active", on);
  const tag = btn.querySelector(".tag");
  // ripple
  const old = btn.querySelector(".ripple");
  if (old) old.remove();
  if (on) {
    const r = document.createElement("span");
    r.className = "ripple";
    btn.appendChild(r);
  }
}

// ── VISION (câmera) ──────────────────────────────────────────────────

function toggleCamera() {
  _camActive = !_camActive;
  setButtonActive("cam", _camActive);
  const label = _camActive ? "VISION ON" : "VISION";
  document.querySelector('.tbtn[data-key="cam"] .tag').textContent = label;
  logLines = [...logLines.slice(-6), _camActive ? "› câmera ativada" : "› câmera desativada"];
  renderLog();
  apiCall("toggle_camera", _camActive);
}

// ── INPUT (mute/desmute) ─────────────────────────────────────────────

function toggleMute() {
  _muted = !_muted;
  setButtonActive("key", _muted);
  const label = _muted ? "MUTED" : "INPUT";
  document.querySelector('.tbtn[data-key="key"] .tag').textContent = label;
  logLines = [...logLines.slice(-6), _muted ? "› mic mutado" : "› mic ativo"];
  renderLog();
  apiCall("toggle_mute", _muted);
}

// ── CHAT (painel de texto) ────────────────────────────────────────────

let chatPanel = null;

function buildChatPanel() {
  if (chatPanel) { chatPanel.remove(); chatPanel = null; return; }
  chatPanel = document.createElement("div");
  chatPanel.id = "nox-chat-panel";
  chatPanel.style.cssText = `
    position:fixed; bottom:130px; left:50%; transform:translateX(-50%);
    width:560px; z-index:999;
    background:rgba(15,12,8,0.92); border:1px solid rgba(255,210,122,0.3);
    border-radius:12px; padding:16px; display:flex; gap:10px;
    backdrop-filter:blur(12px); box-shadow:0 20px 60px rgba(0,0,0,0.6);
  `;
  chatPanel.innerHTML = `
    <input id="nox-chat-input" type="text" placeholder="Digite sua mensagem..."
      style="flex:1; background:rgba(255,255,255,0.06); border:1px solid rgba(255,210,122,0.2);
             border-radius:8px; padding:10px 14px; color:#fff; font-family:inherit;
             font-size:13px; outline:none; letter-spacing:0.05em;"
    />
    <button onclick="sendChatMessage()"
      style="background:linear-gradient(135deg,#FF9A2E,#FFD27A); color:#1a0f00;
             border:none; border-radius:8px; padding:10px 20px; cursor:pointer;
             font-family:inherit; font-weight:700; font-size:12px; letter-spacing:0.2em;">
      ENVIAR
    </button>
  `;
  document.getElementById("app").appendChild(chatPanel);
  document.getElementById("nox-chat-input").focus();
  document.getElementById("nox-chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter") sendChatMessage();
  });
}

async function sendChatMessage() {
  const inp = document.getElementById("nox-chat-input");
  if (!inp) return;
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = "";
  logLines = [...logLines.slice(-6), `› você: ${txt.slice(0,40)}`];
  renderLog();
  const resp = await apiCall("send_message", txt);
  if (resp) {
    logLines = [...logLines.slice(-6), `› nox: ${resp.slice(0,60)}`];
    renderLog();
  }
}

function toggleChat() {
  _chatOpen = !_chatOpen;
  setButtonActive("chat", _chatOpen);
  buildChatPanel();
}

// ── MODULES (painel de status) ────────────────────────────────────────

let modPanel = null;

async function toggleModules() {
  _modOpen = !_modOpen;
  setButtonActive("grid", _modOpen);

  if (!_modOpen) {
    if (modPanel) { modPanel.remove(); modPanel = null; }
    return;
  }

  const status = await apiCall("get_modules_status") || {};

  modPanel = document.createElement("div");
  modPanel.id = "nox-mod-panel";
  modPanel.style.cssText = `
    position:fixed; bottom:130px; right:32px; width:280px; z-index:999;
    background:rgba(15,12,8,0.92); border:1px solid rgba(255,210,122,0.25);
    border-radius:10px; padding:18px;
    backdrop-filter:blur(12px); box-shadow:0 20px 60px rgba(0,0,0,0.6);
    font-size:11px; letter-spacing:0.2em; color:rgba(255,235,200,0.8);
  `;

  function row(label, val, ok) {
    const dot = ok ? "#4ade80" : "#ef4444";
    return `<div style="display:flex;justify-content:space-between;margin-bottom:10px;">
      <span style="color:var(--gold)">${label}</span>
      <span style="display:flex;align-items:center;gap:6px;">
        <span style="width:7px;height:7px;border-radius:50%;background:${dot};display:inline-block"></span>
        ${val}
      </span>
    </div>`;
  }

  modPanel.innerHTML = `
    <div style="color:var(--gold);font-size:10px;letter-spacing:0.35em;margin-bottom:14px;border-bottom:1px solid rgba(255,210,122,0.15);padding-bottom:10px">MÓDULOS</div>
    ${row("STT",       status.stt     ? "online"     : "offline",    status.stt)}
    ${row("TTS",       status.tts     ? "online"     : "offline",    status.tts)}
    ${row("CÂMERA",   status.cam     ? "disponível"  : "sem opencv",  status.cam)}
    ${row("VOICE",    status.voice   ? "ativo"       : "inativo",    status.voice)}
    ${row("MIC",      status.muted   ? "mutado"      : "livre",      !status.muted)}
    ${row("WHATSAPP", status.wpp     ? "conectado"   : "desconectado", status.wpp)}
    ${row("MODEL",    String(status.model || "—"), true)}
    ${row("PERSONA",  String(status.personality || "—"), true)}
  `;
  document.getElementById("app").appendChild(modPanel);
}

// ── Reconfigura toolbar com os novos handlers ─────────────────────────

(function patchToolbar() {
  // Aguarda a toolbar original ser construída, depois substitui handlers
  function patch() {
    const buttons = [
      { key: "mic",  onClick: toggleMic   },
      { key: "cam",  onClick: toggleCamera },
      { key: "chat", onClick: toggleChat  },
      { key: "key",  onClick: toggleMute  },
      { key: "grid", onClick: toggleModules },
    ];
    buttons.forEach(({ key, onClick }) => {
      const btn = document.querySelector(`.tbtn[data-key="${key}"]`);
      if (btn) {
        const fresh = btn.cloneNode(true);
        fresh.addEventListener("click", onClick);
        btn.parentNode.replaceChild(fresh, btn);
      }
    });
  }

  // Roda depois do buildToolbar() original
  if (document.readyState === "complete") {
    setTimeout(patch, 200);
  } else {
    window.addEventListener("load", () => setTimeout(patch, 200));
  }
})();
</script>
"""


def _inject_js(html_path: str) -> str:
    """
    Lê o index.html e injeta o bloco EXTRA_JS antes de </body>.
    Retorna o HTML modificado como string.
    """
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    if "nox-chat-panel" in html:
        return html  # já injetado
    return html.replace("</body>", EXTRA_JS + "\n</body>")


def _write_patched_html(html_path: str) -> str:
    """
    Grava o HTML modificado num arquivo temporário e retorna o caminho.
    """
    patched = _inject_js(html_path)
    tmp = os.path.join(tempfile.gettempdir(), "nox_voice_ui.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(patched)
    return tmp


# ══════════════════════════════════════════════════════════════════════════
#  FUNÇÃO PRINCIPAL — chamada pelo /conversa do main.py
# ══════════════════════════════════════════════════════════════════════════

def launch_voice_ui(nox_instance):
    """
    Abre a janela gráfica e conecta à IA do main.py.

    Uso no main.py:
        from voice_ui import launch_voice_ui
        ...
        def _cmd_voice_chat(self):
            launch_voice_ui(self)
    """
    if not WEBVIEW_AVAILABLE:
        print("[NOX] pywebview não instalado. Execute: pip install pywebview")
        return

    html_path = HTML_PATH
    if not os.path.exists(html_path):
        print(f"[NOX] index.html não encontrado em: {html_path}")
        return

    # Gera HTML com JS extra injetado
    patched_path = _write_patched_html(html_path)

    api = NoxWebApi(nox_instance)

    window = webview.create_window(
        "NOX AI — System Interface",
        patched_path,
        width=1500,
        height=900,
        min_size=(1100, 700),
        background_color="#05060A",
        js_api=api,
    )

    def on_loaded():
        api.set_window(window)
        api.push_log("› ponte python conectada")
        api.push_log("› clique VOICE para começar")
        api.push_status("SYSTEM STANDBY", False)
        # Registra callback de QR (exibe na UI quando WhatsApp pedir escaneamento)
        if WPP_SKILL_AVAILABLE:
            _wpp.add_qr_callback(api._show_wpp_qr)
            api._wpp_qr_cb_registered = True
            # Quando WhatsApp conectar, fecha overlay do QR e notifica
            def _on_wpp_ready(msg_obj):
                if isinstance(msg_obj, dict) and msg_obj.get("type") == "ready":
                    api.wpp_hide_qr()
                    api.push_log("› ✅ WhatsApp conectado!")
                    api.push_status("WPP CONECTADO", True)
            _wpp.add_message_callback(_on_wpp_ready)
            # Verifica se já estava conectado
            if _wpp.is_connected():
                api.push_log("› 🟢 WhatsApp já conectado")

    window.events.loaded += on_loaded

    print("[NOX] Abrindo interface gráfica... Feche a janela para voltar ao terminal.")
    webview.start(debug=False)

    # Cleanup ao fechar
    api._voice_running = False
    api._cam_running = False
    nox_instance.voice_chat = False
    print("[NOX] Interface gráfica fechada.")
