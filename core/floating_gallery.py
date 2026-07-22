# -*- coding: utf-8 -*-
"""
core/floating_gallery.py — Dispara a janela flutuante da galeria
────────────────────────────────────────────────────────────────────
Abre uma janelinha SEM moldura, transparente, sempre por cima de tudo,
mostrando as imagens de uma pasta num carrossel 3D controlado por
gesto de mão (webcam) ou mouse.

Roda como PROCESSO SEPARADO (gallery/floating_gallery_app.py) —
assim o PyQt não trava o loop principal da Nox no terminal.
"""

from __future__ import annotations
import os
import sys
import subprocess

_GALLERY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gallery")
_APP_SCRIPT  = os.path.join(_GALLERY_DIR, "floating_gallery_app.py")


def _pyqt_installed() -> bool:
    try:
        import PyQt6  # noqa
        import PyQt6.QtWebEngineWidgets  # noqa
        return True
    except Exception:
        return False


def _install_pyqt(progress_cb=None) -> bool:
    if progress_cb:
        progress_cb("Instalando PyQt6 (só na primeira vez, pode levar um minuto)...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "PyQt6", "PyQt6-WebEngine",
             "--break-system-packages", "-q"]
        )
        return True
    except Exception:
        return False


def open_gallery(folder: str, title: str = "Galeria", progress_cb=None) -> str:
    if not os.path.isdir(os.path.expanduser(folder)):
        return f"❌ Pasta não encontrada: {folder}"

    if not _pyqt_installed():
        if not _install_pyqt(progress_cb):
            return ("⚠️  Não consegui instalar o PyQt6 automaticamente. Rode manualmente: "
                    "pip install PyQt6 PyQt6-WebEngine --break-system-packages")

    try:
        # Processo independente — não bloqueia o terminal da Nox
        subprocess.Popen(
            [sys.executable, _APP_SCRIPT, folder, title],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return f"🖼️  Abrindo a galeria flutuante ({title})... gire a mão pra girar, belisque os dedos pra dar zoom."
    except Exception as e:
        return f"❌ Erro ao abrir a galeria: {e}"


def open_screenshots_gallery(progress_cb=None) -> str:
    import winpaths
    folder = winpaths.get_known_folder("screenshots") or winpaths.get_known_folder("pictures")
    if not folder:
        return "❌ Não encontrei uma pasta de imagens/capturas de tela."
    return open_gallery(folder, "Suas capturas de tela", progress_cb)


def open_downloads_gallery(progress_cb=None) -> str:
    import winpaths
    folder = winpaths.get_known_folder("downloads")
    if not folder:
        return "❌ Não encontrei a pasta Downloads."
    return open_gallery(folder, "Seus arquivos (Downloads)", progress_cb)
