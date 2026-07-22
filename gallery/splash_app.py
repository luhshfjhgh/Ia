# -*- coding: utf-8 -*-
"""
gallery/splash_app.py — Splash de abertura com efeito de fumaça
────────────────────────────────────────────────────────────────────
Janela flutuante, sem moldura, fundo transparente de verdade,
mostrando "NOX AI" se materializando com efeito de fumaça (a mesma
técnica visual do componente Smoky Text) antes do terminal abrir.

Fecha sozinha assim que a animação termina — não precisa de
interação nenhuma.
"""

import sys
import os


def main():
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splash_smoky.html")

    app = QApplication(sys.argv)

    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )
    window.resize(860, 300)

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
    layout.addWidget(view)

    def on_title_changed(new_title):
        if new_title == "__NOX_SPLASH_DONE__":
            app.quit()

    view.titleChanged.connect(on_title_changed)
    view.load(QUrl.fromLocalFile(html_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
