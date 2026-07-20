# -*- coding: utf-8 -*-
"""
core/geoip.py — Rastreio de IP/localização aproximada no login
────────────────────────────────────────────────────────────────────
Usado pela auditoria de contas: toda vez que alguém loga, guardamos
o IP público e uma localização aproximada (cidade/região/país), pra
o admin conseguir ver de onde cada conta está sendo acessada e notar
logins suspeitos (ex: dois países muito distantes em pouco tempo).

Usa o serviço gratuito ip-api.com (sem necessidade de chave/token).
Se não tiver internet, retorna (None, None) sem quebrar o login.
"""

from __future__ import annotations
import requests
from typing import Optional, Tuple


def get_ip_and_location(timeout: int = 6) -> Tuple[Optional[str], Optional[str]]:
    """Retorna (ip, 'Cidade, Região, País') ou (None, None) em caso de falha."""
    try:
        r = requests.get(
            "http://ip-api.com/json/?fields=status,message,query,city,regionName,country",
            timeout=timeout,
        )
        data = r.json()
        if data.get("status") == "success":
            ip = data.get("query")
            loc = ", ".join(p for p in (data.get("city"), data.get("regionName"), data.get("country")) if p)
            return ip, (loc or None)
    except Exception:
        pass
    return None, None
