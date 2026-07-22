# -*- coding: utf-8 -*-
"""
core/winpaths.py — Acha pastas do Windows (Downloads, Imagens, etc.)
────────────────────────────────────────────────────────────────────
No Windows em português, essas pastas ficam com nomes traduzidos no
disco de verdade ("Imagens", "Capturas de Tela", "Área de Trabalho"...),
então caminhos fixos tipo "~/Pictures" simplesmente não existem aí.

O Windows guarda o caminho REAL de cada uma dessas pastas por um ID
interno (GUID) que não muda com o idioma — é isso que usamos aqui via
SHGetKnownFolderPath (API oficial do Windows), em vez de adivinhar
pelo nome.
"""

from __future__ import annotations
import os
import sys
import ctypes
from ctypes import wintypes

IS_WIN = sys.platform.startswith("win")

# FOLDERID oficiais (não mudam entre idiomas/versões do Windows)
_FOLDER_GUIDS = {
    "desktop":     "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "downloads":   "{374DE290-123F-4565-9164-39C4925E467B}",
    "documents":   "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "pictures":    "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "videos":      "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
    "music":       "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "screenshots": "{B7BEDE81-DF94-4682-A7D8-57A52620B86F}",  # Imagens\Capturas de Tela
}

# Fallback em português/inglês caso a API falhe por algum motivo
_FALLBACK_NAMES = {
    "desktop":     ["Desktop", "Área de Trabalho"],
    "downloads":   ["Downloads"],
    "documents":   ["Documents", "Documentos"],
    "pictures":    ["Pictures", "Imagens"],
    "videos":      ["Videos", "Vídeos"],
    "music":       ["Music", "Músicas"],
    "screenshots": [
        os.path.join("Pictures", "Screenshots"),
        os.path.join("Imagens", "Capturas de Tela"),
        os.path.join("Imagens", "Screenshots"),
    ],
}


def get_known_folder(name: str) -> str | None:
    """Retorna o caminho real da pasta (ex: 'downloads', 'pictures',
    'screenshots'), certo não importa o idioma do Windows. None se
    não conseguir resolver de jeito nenhum."""
    name = name.lower()

    if IS_WIN and name in _FOLDER_GUIDS:
        try:
            guid = _FOLDER_GUIDS[name]

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8),
                ]

            # Monta o GUID a partir da string "{XXXXXXXX-XXXX-...}"
            g = GUID()
            ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(g))

            path_ptr = ctypes.c_wchar_p()
            result = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(g), 0, 0, ctypes.byref(path_ptr)
            )
            if result == 0 and path_ptr.value:
                path = path_ptr.value
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                if os.path.isdir(path):
                    return path
        except Exception:
            pass

    # Fallback: tenta nomes conhecidos em pt-BR/en dentro do perfil do usuário
    home = os.path.expanduser("~")
    for candidate in _FALLBACK_NAMES.get(name, []):
        p = os.path.join(home, candidate)
        if os.path.isdir(p):
            return p

    return None
