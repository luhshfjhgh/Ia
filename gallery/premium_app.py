# -*- coding: utf-8 -*-
"""
gallery/premium_app.py — Janela dos Planos Premium
────────────────────────────────────────────────────────────────────
Uso: python premium_app.py <user_id> <username>
"""
import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import payments  # noqa: E402


def main():
    user_id  = sys.argv[1] if len(sys.argv) > 1 else ""
    username = sys.argv[2] if len(sys.argv) > 2 else ""

    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtGui import QColor

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "premium_cards.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    data_script = f"<script>window.NOX_PLANS = {json.dumps(payments.PLANS)};</script>"
    html = html.replace("<!--NOX_DATA_INJECTION_POINT-->", data_script)

    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="nox_premium_")
    tmp_html_path = os.path.join(tmp_dir, "premium.html")
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    app = QApplication(sys.argv)
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )
    window.resize(700, 460)
    screen = app.primaryScreen().availableGeometry()
    window.move(
        screen.x() + (screen.width() - window.width()) // 2,
        screen.y() + (screen.height() - window.height()) // 2,
    )

    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)

    view = QWebEngineView(window)
    view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    view.page().setBackgroundColor(QColor(0, 0, 0, 0))
    layout.addWidget(view)

    view.load(QUrl.fromLocalFile(tmp_html_path))
    window.show()

    payment_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payment_app.py")

    def on_title_changed(t: str):
        if t == "__NOX_CLOSE__":
            app.quit()
        elif t.startswith("__NOX_SELECT_PLAN__:"):
            plan_key = t.split(":", 1)[1]
            if plan_key == "free":
                ok, msg = payments.start_subscription(user_id, username, "free")
                print(f"[NOX] {msg}")
                app.quit()
            else:
                app.quit()
                subprocess.Popen([sys.executable, payment_script, plan_key, user_id, username])

    view.titleChanged.connect(on_title_changed)

    # Conecta os botões do HTML ao Python via mudança de titulo
    bridge_js = """
    window.noxClose = function(){ document.title = '__NOX_CLOSE__'; };
    window.noxSelectPlan = function(key){ document.title = '__NOX_SELECT_PLAN__:' + key; };
    """
    view.page().loadFinished.connect(lambda ok: view.page().runJavaScript(bridge_js))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
