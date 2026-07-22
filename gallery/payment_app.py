# -*- coding: utf-8 -*-
"""
gallery/payment_app.py — Tela de pagamento Pix
────────────────────────────────────────────────────────────────────
Uso: python payment_app.py <plan_key> <user_id> <username>
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import payments  # noqa: E402


def main():
    plan_key = sys.argv[1] if len(sys.argv) > 1 else "basic"
    user_id  = sys.argv[2] if len(sys.argv) > 2 else ""
    username = sys.argv[3] if len(sys.argv) > 3 else ""

    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFileDialog
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtGui import QColor

    plan = payments.PLANS.get(plan_key, payments.PLANS["basic"])
    plan_label = f"{plan['nome']} — {plan['preco_label']}"

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payment_screen.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace(
        "<script>",
        f"<script>window.NOX_PLAN_LABEL = {json.dumps(plan_label)};",
        1,
    )

    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="nox_payment_")
    tmp_html_path = os.path.join(tmp_dir, "payment.html")
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
    window.resize(480, 420)
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

    def pick_and_attach():
        path, _ = QFileDialog.getOpenFileName(
            window, "Selecione o comprovante", "",
            "Comprovantes (*.png *.jpg *.jpeg *.pdf)"
        )
        if not path:
            return
        ok, msg = payments.attach_receipt(user_id, username, plan_key, path)
        safe_msg = json.dumps(msg)
        view.page().runJavaScript(f"window.noxShowStatus && window.noxShowStatus({safe_msg})")

    def on_title_changed(t: str):
        if t == "__NOX_CLOSE__":
            app.quit()
        elif t == "__NOX_PICK_FILE__":
            pick_and_attach()

    view.titleChanged.connect(on_title_changed)

    bridge_js = """
    window.noxClose = function(){ document.title = '__NOX_CLOSE__'; };
    window.noxPickFile = function(){ document.title = '__NOX_PICK_FILE__'; };
    """
    view.page().loadFinished.connect(lambda ok: view.page().runJavaScript(bridge_js))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
