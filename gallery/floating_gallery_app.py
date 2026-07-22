# -*- coding: utf-8 -*-
"""
gallery/floating_gallery_app.py — Janela flutuante transparente
────────────────────────────────────────────────────────────────────
Roda como um PROCESSO SEPARADO (a Nox lança isso via subprocess, não
importa direto), porque o PyQt precisa ser dono do "loop principal" —
rodar junto com o terminal ia travar os dois.

Uso:
    python floating_gallery_app.py "<pasta_de_imagens>" "<titulo>"

Depende de: PyQt6, PyQt6-WebEngine
    pip install PyQt6 PyQt6-WebEngine
(A Nox tenta instalar sozinha na primeira vez que você usar, se faltar.)
"""

import sys
import os
import json
import glob
from urllib.parse import quote

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def _collect_images(folder: str, limit: int = 24):
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return []
    files = []
    for ext in IMG_EXTS:
        files.extend(glob.glob(os.path.join(folder, f"*{ext}")))
        files.extend(glob.glob(os.path.join(folder, f"*{ext.upper()}")))
    files = sorted(files, key=os.path.getmtime, reverse=True)[:limit]
    # file:// com barras corretas + espaços/acentos escapados (%20 etc.)
    # — sem isso, nomes como "Capturas de Tela" quebram o carregamento
    urls = []
    for f in files:
        normalized = f.replace("\\", "/")
        encoded = quote(normalized, safe="/:")
        urls.append("file:///" + encoded)
    return urls


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "~/Pictures/Screenshots"
    title  = sys.argv[2] if len(sys.argv) > 2 else "Galeria"

    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

    images = _collect_images(folder)
    print(f"[NOX] Pasta: {folder}")
    print(f"[NOX] Imagens encontradas: {len(images)}")
    for u in images[:5]:
        print(f"[NOX]   - {u}")

    # ── Gera um HTML temporário já com as imagens embutidas no texto ──
    # (embutir ANTES de carregar evita corrida de tempo: se a gente só
    # injeta via JS depois que a página carrega, o script que monta o
    # carrossel já rodou antes disso, com a lista vazia — por isso as
    # imagens não apareciam.)
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "floating_gallery.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    data_script = (
        f"<script>window.NOX_IMAGES = {json.dumps(images)}; "
        f"window.NOX_TITLE = {json.dumps(title)};</script>"
    )
    html = html.replace("<!--NOX_DATA_INJECTION_POINT-->", data_script)

    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="nox_gallery_")
    tmp_html_path = os.path.join(tmp_dir, "gallery.html")
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    html_url = QUrl.fromLocalFile(tmp_html_path)

    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle(f"NOX — {title}")
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool  # nao aparece na barra de tarefas
    )
    window.resize(560, 560)

    # Centraliza na tela
    screen = app.primaryScreen().availableGeometry()
    window.move(
        screen.x() + (screen.width() - window.width()) // 2,
        screen.y() + (screen.height() - window.height()) // 2,
    )

    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)

    view = QWebEngineView(window)
    view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    view.page().setBackgroundColor(Qt.GlobalColor.transparent)

    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

    # Autoriza a webcam sem popup de permissao (janela nossa, controlada)
    def on_permission(url, feature):
        try:
            view.page().setFeaturePermission(
                url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )
        except Exception:
            pass

    try:
        view.page().featurePermissionRequested.connect(on_permission)
    except Exception:
        pass

    layout.addWidget(view)

    view.load(html_url)
    window.show()

    # Permite fechar a janela clicando no "X" do HTML (window.noxClose)
    channel_js = "window.noxClose = function(){ document.title = '__NOX_CLOSE__'; };"
    view.page().loadFinished.connect(lambda ok: view.page().runJavaScript(channel_js))

    def on_title_changed(new_title):
        if new_title == "__NOX_CLOSE__":
            app.quit()

    view.titleChanged.connect(on_title_changed)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
