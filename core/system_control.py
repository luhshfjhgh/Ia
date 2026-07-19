# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║       NOX AI — System Control Module        ║
║   Controle total do notebook via terminal   ║
╚══════════════════════════════════════════════╝
  Controle de arquivos, apps, volume, música,
  processos, screenshot, clipboard e muito mais.
"""

import os
import sys
import re
import glob
import shutil
import subprocess
import platform
import threading
import time
from datetime import datetime
from pathlib import Path

IS_WIN   = sys.platform == "win32"
IS_MAC   = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ── Imports opcionais ──────────────────────────────────────
try:
    import psutil
    PSUTIL_OK = True
except (ImportError, OSError, Exception):
    PSUTIL_OK = False
    psutil = None

try:
    import pyperclip
    CLIPBOARD_OK = True
except (ImportError, OSError, Exception):
    CLIPBOARD_OK = False
    pyperclip = None

try:
    import pyautogui
    PYAUTOGUI_OK = True
except (ImportError, OSError, Exception):
    PYAUTOGUI_OK = False
    pyautogui = None


# ══════════════════════════════════════════════════════
#  UTILITÁRIOS INTERNOS
# ══════════════════════════════════════════════════════

def _run(cmd: str | list, capture=True) -> str:
    """Executa comando no shell e retorna stdout."""
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=15)
        else:
            r = subprocess.run(cmd, capture_output=capture, text=True, timeout=15)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"ERRO: {e}"


def _expand(path: str) -> str:
    """Expande ~ e variáveis de ambiente."""
    return os.path.expandvars(os.path.expanduser(path))


# ══════════════════════════════════════════════════════
#  ARQUIVOS
# ══════════════════════════════════════════════════════

def file_delete(path: str) -> str:
    p = Path(_expand(path))
    if not p.exists():
        return f"❌ Não encontrado: {path}"
    try:
        if p.is_dir():
            shutil.rmtree(p)
            return f"🗑️  Pasta deletada: {p.name}"
        else:
            p.unlink()
            return f"🗑️  Arquivo deletado: {p.name}"
    except Exception as e:
        return f"❌ Erro: {e}"


def file_move(src: str, dst: str) -> str:
    try:
        s, d = Path(_expand(src)), Path(_expand(dst))
        shutil.move(str(s), str(d))
        return f"📦 Movido: {s.name} → {d}"
    except Exception as e:
        return f"❌ Erro: {e}"


def file_copy(src: str, dst: str) -> str:
    try:
        s, d = Path(_expand(src)), Path(_expand(dst))
        if s.is_dir():
            shutil.copytree(str(s), str(d))
        else:
            shutil.copy2(str(s), str(d))
        return f"📋 Copiado: {s.name} → {d}"
    except Exception as e:
        return f"❌ Erro: {e}"


def file_create(path: str, content: str = "") -> str:
    try:
        p = Path(_expand(path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Arquivo criado: {p}"
    except Exception as e:
        return f"❌ Erro: {e}"


def file_read(path: str) -> str:
    try:
        p = Path(_expand(path))
        if not p.exists():
            return f"❌ Não encontrado: {path}"
        if p.stat().st_size > 500_000:
            return f"⚠️  Arquivo muito grande ({p.stat().st_size // 1024}KB). Exibindo início:\n" + p.read_text(encoding="utf-8", errors="ignore")[:2000]
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"❌ Erro: {e}"


def file_search(pattern: str, root: str = "~") -> list[str]:
    root_path = _expand(root)
    results = []
    try:
        for match in glob.glob(os.path.join(root_path, "**", pattern), recursive=True):
            results.append(match)
        return results[:50]
    except Exception:
        return []


def folder_list(path: str = ".") -> str:
    p = Path(_expand(path))
    if not p.exists():
        return f"❌ Pasta não existe: {path}"
    items = []
    try:
        for item in sorted(p.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                s = item.stat().st_size
                size = f"  {s//1024}KB" if s > 1024 else f"  {s}B"
            items.append(f"  {icon} {item.name}{size}")
        return f"📂 {p}\n" + "\n".join(items) if items else "  (vazio)"
    except Exception as e:
        return f"❌ Erro: {e}"


def folder_create(path: str) -> str:
    try:
        Path(_expand(path)).mkdir(parents=True, exist_ok=True)
        return f"📁 Pasta criada: {path}"
    except Exception as e:
        return f"❌ Erro: {e}"


def rename(src: str, new_name: str) -> str:
    try:
        s = Path(_expand(src))
        d = s.parent / new_name
        s.rename(d)
        return f"✏️  Renomeado: {s.name} → {new_name}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  APPS
# ══════════════════════════════════════════════════════

# Mapa de nomes amigáveis → comandos por OS
APP_MAP_WIN = {
    "chrome":      "start chrome",
    "firefox":     "start firefox",
    "notepad":     "notepad",
    "calculadora": "calc",
    "explorador":  "explorer",
    "cmd":         "start cmd",
    "powershell":  "start powershell",
    "word":        "start winword",
    "excel":       "start excel",
    "spotify":     "start spotify",
    "discord":     "start discord",
    "vscode":      "start code",
    "paint":       "mspaint",
    "teams":       "start teams",
    "zoom":        "start zoom",
    "whatsapp":    "start whatsapp",
    "telegram":    "start telegram",
}

APP_MAP_LINUX = {
    "chrome":      "google-chrome",
    "firefox":     "firefox",
    "gedit":       "gedit",
    "calculadora": "gnome-calculator",
    "explorador":  "nautilus",
    "terminal":    "gnome-terminal",
    "vscode":      "code",
    "spotify":     "spotify",
    "discord":     "discord",
    "telegram":    "telegram-desktop",
    "vlc":         "vlc",
}

APP_MAP_MAC = {
    "chrome":      "open -a 'Google Chrome'",
    "firefox":     "open -a Firefox",
    "safari":      "open -a Safari",
    "calculadora": "open -a Calculator",
    "finder":      "open .",
    "vscode":      "open -a 'Visual Studio Code'",
    "spotify":     "open -a Spotify",
    "discord":     "open -a Discord",
    "telegram":    "open -a Telegram",
    "terminal":    "open -a Terminal",
}


def open_app(name: str) -> str:
    name_lower = name.lower().strip()
    if IS_WIN:
        cmd = APP_MAP_WIN.get(name_lower, f"start {name}")
    elif IS_MAC:
        cmd = APP_MAP_MAC.get(name_lower, f"open -a '{name}'")
    else:
        cmd = APP_MAP_LINUX.get(name_lower, name_lower)

    try:
        if IS_WIN:
            os.system(cmd)
        elif IS_MAC:
            os.system(cmd + " &>/dev/null &")
        else:
            subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"🚀 Abrindo {name}..."
    except Exception as e:
        return f"❌ Não foi possível abrir {name}: {e}"


def open_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        if IS_WIN:
            os.system(f'start "" "{url}"')
        elif IS_MAC:
            os.system(f'open "{url}"')
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"🌐 Abrindo: {url}"
    except Exception as e:
        return f"❌ Erro: {e}"


def open_file_with_default(path: str) -> str:
    p = _expand(path)
    try:
        if IS_WIN:
            os.startfile(p)
        elif IS_MAC:
            os.system(f'open "{p}"')
        else:
            subprocess.Popen(["xdg-open", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"📂 Abrindo: {os.path.basename(p)}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  PROCESSOS
# ══════════════════════════════════════════════════════

def list_processes(filter_name: str = "") -> str:
    if not PSUTIL_OK:
        return "⚠️  psutil não instalado. Execute: pip install psutil"
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            name = p.info["name"] or ""
            if filter_name and filter_name.lower() not in name.lower():
                continue
            mem = p.info["memory_info"].rss // 1024 // 1024 if p.info["memory_info"] else 0
            procs.append(f"  {p.info['pid']:>6}  {name:<30}  {mem:>4}MB")
        except Exception:
            pass
    if not procs:
        return "  Nenhum processo encontrado."
    header = f"  {'PID':>6}  {'NOME':<30}  {'MEM':>4}\n  {'─'*50}"
    return header + "\n" + "\n".join(procs[:30])


def kill_process(name_or_pid: str) -> str:
    if not PSUTIL_OK:
        return "⚠️  psutil não instalado."
    killed = []
    try:
        pid = int(name_or_pid)
        psutil.Process(pid).terminate()
        return f"💀 Processo {pid} encerrado."
    except ValueError:
        pass
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if name_or_pid.lower() in (p.info["name"] or "").lower():
                p.terminate()
                killed.append(p.info["name"])
        except Exception:
            pass
    return f"💀 Encerrado: {', '.join(killed)}" if killed else f"❌ Processo '{name_or_pid}' não encontrado."


# ══════════════════════════════════════════════════════
#  SISTEMA
# ══════════════════════════════════════════════════════

def system_info() -> str:
    info = []
    info.append(f"  🖥️  OS:      {platform.system()} {platform.release()}")
    info.append(f"  🏷️  Host:    {platform.node()}")
    info.append(f"  🧠 CPU:     {platform.processor() or 'N/A'}")
    if PSUTIL_OK:
        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        info.append(f"  ⚡ CPU uso: {cpu_pct}%")
        info.append(f"  💾 RAM:     {mem.used//1024//1024}MB / {mem.total//1024//1024}MB ({mem.percent}%)")
        info.append(f"  💿 Disco:   {disk.used//1024//1024//1024}GB / {disk.total//1024//1024//1024}GB ({disk.percent}%)")
    return "\n".join(info)


def battery_info() -> str:
    if not PSUTIL_OK:
        return "⚠️  psutil necessário."
    try:
        b = psutil.sensors_battery()
        if not b:
            return "🔌 Bateria não detectada (desktop?)"
        status = "🔌 Carregando" if b.power_plugged else "🔋 Bateria"
        mins = int(b.secsleft / 60) if b.secsleft > 0 else 0
        return f"  {status}: {b.percent:.0f}%  ⏱️  ~{mins}min restantes"
    except Exception as e:
        return f"❌ Erro: {e}"


def screenshot(save_path: str = "~/Desktop/nox_screenshot.png") -> str:
    if not PYAUTOGUI_OK:
        return "⚠️  pyautogui não instalado. Execute: pip install pyautogui pillow"
    try:
        p = _expand(save_path)
        img = pyautogui.screenshot()
        img.save(p)
        return f"📸 Screenshot salvo: {p}"
    except Exception as e:
        return f"❌ Erro: {e}"


def lock_screen() -> str:
    try:
        if IS_WIN:
            _run("rundll32.exe user32.dll,LockWorkStation")
        elif IS_MAC:
            _run('osascript -e \'tell app "System Events" to keystroke "q" using {command down, control down}\'')
        else:
            _run("loginctl lock-session")
        return "🔒 Tela bloqueada."
    except Exception as e:
        return f"❌ Erro: {e}"


def shutdown(delay_min: int = 0) -> str:
    try:
        if IS_WIN:
            _run(f"shutdown /s /t {delay_min * 60}")
        elif IS_MAC:
            _run(f"sudo shutdown -h +{delay_min}")
        else:
            _run(f"shutdown -h +{delay_min}")
        return f"⚠️  Sistema vai desligar em {delay_min} minuto(s)."
    except Exception as e:
        return f"❌ Erro: {e}"


def restart(delay_min: int = 0) -> str:
    try:
        if IS_WIN:
            _run(f"shutdown /r /t {delay_min * 60}")
        elif IS_MAC:
            _run(f"sudo shutdown -r +{delay_min}")
        else:
            _run(f"shutdown -r +{delay_min}")
        return f"🔄 Sistema vai reiniciar em {delay_min} minuto(s)."
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  VOLUME
# ══════════════════════════════════════════════════════

def set_volume(level: int) -> str:
    """level: 0–100"""
    level = max(0, min(100, level))
    try:
        if IS_WIN:
            # Usa PowerShell + NirCmd ou script
            script = f"(New-Object -ComObject WScript.Shell).SendKeys([char]173); " \
                     f"$vol = New-Object -ComObject Shell.Application; " \
                     f"$vol.SetVolume({level})"
            # Alternativa simples via nircmd se disponível
            if shutil.which("nircmd"):
                val = int(level / 100 * 65535)
                _run(f"nircmd setsysvolume {val}")
            else:
                # PowerShell via COM
                ps = f'$wshShell = New-Object -ComObject WScript.Shell; [Audio]::Volume = {level/100}'
                subprocess.Popen(["powershell", "-Command", ps], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_MAC:
            _run(f"osascript -e 'set volume output volume {level}'")
        else:
            # ALSA / PulseAudio
            if shutil.which("pactl"):
                _run(f"pactl set-sink-volume @DEFAULT_SINK@ {level}%")
            elif shutil.which("amixer"):
                _run(f"amixer -q sset Master {level}%")
        return f"🔊 Volume ajustado para {level}%"
    except Exception as e:
        return f"❌ Erro: {e}"


def mute_volume() -> str:
    try:
        if IS_WIN:
            if shutil.which("nircmd"):
                _run("nircmd mutesysvolume 1")
            else:
                subprocess.Popen(["powershell", "-Command",
                    "[Audio]::Mute = $true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_MAC:
            _run("osascript -e 'set volume output muted true'")
        else:
            if shutil.which("pactl"):
                _run("pactl set-sink-mute @DEFAULT_SINK@ 1")
            else:
                _run("amixer -q sset Master mute")
        return "🔇 Volume mutado."
    except Exception as e:
        return f"❌ Erro: {e}"


def unmute_volume() -> str:
    try:
        if IS_WIN:
            if shutil.which("nircmd"):
                _run("nircmd mutesysvolume 0")
        elif IS_MAC:
            _run("osascript -e 'set volume output muted false'")
        else:
            if shutil.which("pactl"):
                _run("pactl set-sink-mute @DEFAULT_SINK@ 0")
            else:
                _run("amixer -q sset Master unmute")
        return "🔊 Volume ativado."
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  MÚSICA (player local)
# ══════════════════════════════════════════════════════

_music_process = None
_music_current = ""


def play_music(path: str) -> str:
    """Toca arquivo de áudio local."""
    global _music_process, _music_current
    p = _expand(path)
    if not os.path.exists(p):
        # Tenta buscar na pasta Music do usuário
        music_dirs = [
            os.path.expanduser("~/Music"),
            os.path.expanduser("~/Música"),
            os.path.expanduser("~/Downloads"),
        ]
        for d in music_dirs:
            for ext in ["mp3", "wav", "ogg", "flac", "m4a"]:
                matches = glob.glob(os.path.join(d, "**", f"*{path}*.{ext}"), recursive=True)
                if matches:
                    p = matches[0]
                    break
            if os.path.exists(p):
                break

    if not os.path.exists(p):
        return f"❌ Arquivo não encontrado: {path}"

    stop_music()
    try:
        if IS_WIN:
            _music_process = subprocess.Popen(
                ["powershell", "-c", f'Add-Type -AssemblyName presentationCore; '
                 f'$player = New-Object System.Windows.Media.MediaPlayer; '
                 f'$player.Open("{p}"); $player.Play(); Start-Sleep -s 3600'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif IS_MAC:
            _music_process = subprocess.Popen(["afplay", p],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for player in ["mpg123", "ffplay", "mplayer", "cvlc"]:
                if shutil.which(player):
                    args = {
                        "ffplay": ["ffplay", "-nodisp", "-autoexit", p],
                        "mpg123": ["mpg123", "-q", p],
                        "mplayer": ["mplayer", "-quiet", p],
                        "cvlc":   ["cvlc", "--play-and-exit", p],
                    }.get(player, [player, p])
                    _music_process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
        _music_current = os.path.basename(p)
        return f"🎵 Tocando: {_music_current}"
    except Exception as e:
        return f"❌ Erro ao tocar: {e}"


def stop_music() -> str:
    global _music_process, _music_current
    if _music_process:
        try:
            _music_process.terminate()
            _music_process = None
            name = _music_current
            _music_current = ""
            return f"⏹️  Parado: {name}"
        except Exception as e:
            return f"❌ Erro: {e}"
    return "  Nenhuma música tocando."


def music_status() -> str:
    if _music_process and _music_process.poll() is None:
        return f"🎵 Tocando: {_music_current}"
    return "⏸️  Sem música tocando no momento."


def list_music(folder: str = "~/Music") -> list[str]:
    root = _expand(folder)
    files = []
    for ext in ["mp3", "wav", "ogg", "flac", "m4a", "aac"]:
        files.extend(glob.glob(os.path.join(root, "**", f"*.{ext}"), recursive=True))
    # Também tenta ~/Música (português)
    if not files:
        root2 = _expand("~/Música")
        for ext in ["mp3", "wav", "ogg", "flac", "m4a", "aac"]:
            files.extend(glob.glob(os.path.join(root2, "**", f"*.{ext}"), recursive=True))
    return [os.path.basename(f) for f in files[:30]]


def open_spotify(query: str = "") -> str:
    if query:
        q = query.replace(" ", "%20")
        url = f"https://open.spotify.com/search/{q}"
    else:
        url = "https://open.spotify.com"
    return open_url(url)


# ══════════════════════════════════════════════════════
#  CLIPBOARD
# ══════════════════════════════════════════════════════

def clipboard_copy(text: str) -> str:
    if CLIPBOARD_OK:
        pyperclip.copy(text)
        return f"📋 Copiado: {text[:50]}..."
    # Fallback via subprocess
    try:
        if IS_WIN:
            subprocess.run("clip", input=text.encode("utf-8"), check=True)
        elif IS_MAC:
            subprocess.run("pbcopy", input=text.encode("utf-8"), check=True)
        else:
            subprocess.run(["xclip", "-sel", "clip"], input=text.encode("utf-8"), check=True)
        return f"📋 Copiado para área de transferência."
    except Exception as e:
        return f"❌ Erro: {e}"


def clipboard_paste() -> str:
    if CLIPBOARD_OK:
        return pyperclip.paste()
    try:
        if IS_WIN:
            return _run("powershell Get-Clipboard")
        elif IS_MAC:
            return _run("pbpaste")
        else:
            return _run("xclip -sel clip -o")
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  WIFI / REDE
# ══════════════════════════════════════════════════════

def wifi_list() -> str:
    try:
        if IS_WIN:
            return _run("netsh wlan show networks")
        elif IS_MAC:
            return _run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s")
        else:
            if shutil.which("nmcli"):
                return _run("nmcli dev wifi list")
            return _run("iwlist scan 2>/dev/null | grep ESSID")
    except Exception as e:
        return f"❌ Erro: {e}"


def get_local_ip() -> str:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return f"🌐 IP local: {s.getsockname()[0]}"
    except Exception as e:
        return f"❌ Erro: {e}"


# ══════════════════════════════════════════════════════
#  NLP — Interpreta pedidos em linguagem natural
# ══════════════════════════════════════════════════════

def interpret_system_command(text: str) -> tuple[str, str] | None:
    """
    Analisa texto em linguagem natural e retorna (ação, argumento).
    Retorna None se não for um comando de sistema.
    """
    t = text.lower().strip()

    # ── Deletar arquivo ──
    m = re.search(r"(?:deleta|deletar|exclui|excluir|remover|remove|apagar|apaga)\s+(?:o\s+arquivo\s+|a\s+pasta\s+)?(.+)", t)
    if m:
        return ("delete", m.group(1).strip())

    # ── Criar arquivo ──
    m = re.search(r"(?:criar?|cria)\s+(?:um?\s+)?(?:arquivo|doc)\s+(?:chamado\s+|com\s+nome\s+)?(.+)", t)
    if m:
        return ("create_file", m.group(1).strip())

    # ── Criar pasta ──
    m = re.search(r"(?:criar?|cria)\s+(?:uma?\s+)?pasta\s+(?:chamad[ao]\s+)?(.+)", t)
    if m:
        return ("create_folder", m.group(1).strip())

    # ── Abrir app ──
    m = re.search(r"(?:abre|abrir|abra|abrindo|liga|iniciar?)\s+(?:o\s+|a\s+)?(?:app\s+|programa\s+|aplicativo\s+)?(.+)", t)
    if m:
        arg = m.group(1).strip().rstrip(".")
        if arg not in ["arquivo", "pasta", "url", "site", "musica", "música", "o", "a"]:
            return ("open_app", arg)

    # ── Abrir URL ──
    m = re.search(r"(?:abre|abrir|vai\s+para?|naveg(?:ar|a)\s+para?)\s+(?:o\s+site\s+|a\s+url\s+)?(?:https?://)?([a-z0-9\-\.]+\.[a-z]{2,}(?:/\S*)?)", t)
    if m:
        return ("open_url", m.group(1).strip())

    # ── Tocar música (arquivo local ou pesquisa) ──
    m = re.search(r"(?:toca|tocar|play|reproduz(?:ir)?|coloca)\s+(?:a\s+m[úu]sica\s+|o\s+som\s+|a\s+m[úu]sica\s+)?(?:do\s+|de\s+|da\s+)?(.+)", t)
    if m:
        return ("play_music", m.group(1).strip().rstrip(".!"))

    # ── Parar música ──
    if re.search(r"(?:para|parar|para\s+a\s+m[úu]sica|stop|silenci(?:a|ar)|cancela?\s+m[úu]sica)", t):
        return ("stop_music", "")

    # ── Volume ──
    m = re.search(r"(?:volume|som)\s+(?:para\s+|em\s+)?(\d+)%?", t)
    if m:
        return ("set_volume", m.group(1))

    m = re.search(r"(?:aumenta|sobe)\s+(?:o\s+)?volume", t)
    if m:
        return ("volume_up", "")

    m = re.search(r"(?:diminui|baixa|abaixa)\s+(?:o\s+)?volume", t)
    if m:
        return ("volume_down", "")

    if re.search(r"muta|mutar|silenci(?:a|ar)\s+(?:o\s+)?(?:volume|som)", t):
        return ("mute", "")

    # ── Screenshot ──
    if re.search(r"(?:print|screenshot|captura(?:r)?\s+tela|printscreen)", t):
        return ("screenshot", "")

    # ── Travar tela ──
    if re.search(r"(?:travar?|bloquear?|lock)\s+(?:a\s+)?tela", t):
        return ("lock", "")

    # ── Info do sistema ──
    if re.search(r"(?:info(?:rmações?)?\s+(?:do\s+)?(?:sistema|pc|computador)|status\s+do\s+(?:sistema|pc)|como\s+está\s+o\s+pc|cpu\s+e\s+ram|bateria)", t):
        if "bateria" in t:
            return ("battery", "")
        return ("sysinfo", "")

    # ── Processos ──
    m = re.search(r"(?:listar?|ver|mostrar?)\s+(?:os\s+)?processos", t)
    if m:
        return ("list_procs", "")

    m = re.search(r"(?:matar?|fechar?|encerrar?|kill)\s+(?:o\s+processo\s+|processo\s+)?(.+)", t)
    if m:
        return ("kill_proc", m.group(1).strip())

    # ── Listar pasta ──
    m = re.search(r"(?:listar?|ver|mostrar?)\s+(?:o\s+)?(?:conte[úu]do\s+)?(?:da\s+)?pasta\s+(.+)", t)
    if m:
        return ("list_dir", m.group(1).strip())

    if re.search(r"(?:listar?|ver|mostrar?)\s+(?:os\s+)?(?:arquivos|conte[úu]do)\s+(?:aqui|atual|do\s+diret[oó]rio)", t):
        return ("list_dir", ".")

    # ── Clipboard ──
    m = re.search(r"(?:copia|copiar)\s+(?:para\s+[aá]\s+[aá]rea\s+de\s+transfer[eê]ncia\s+)?[\"']?(.+)[\"']?\s*(?:para\s+[aá]\s+[aá]rea)?", t)
    if m and "área" not in m.group(1):
        return ("clipboard_copy", m.group(1).strip().strip("\"'"))

    return None
