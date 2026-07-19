# -*- coding: utf-8 -*-
"""
ban_system.py — Sistema de segurança da Nox AI v3.1
────────────────────────────────────────────────────
• JSON de ban criptografado com Fernet (AES-128-CBC + HMAC)
• Qualquer alteração no arquivo invalida o ban → ban permanente
• Senha necessária para VISUALIZAR o ban (não para remover)
• Impossível desbanir antes de 24h — tempo assinado com HMAC
• Fingerprint: SHA-256(hostname + MAC + volume_serial)
"""

import json, os, re, uuid, socket, hashlib, hmac, base64, sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Dependência: cryptography ─────────────────────────────────
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    os.system(f"{sys.executable} -m pip install cryptography --break-system-packages -q")
    from cryptography.fernet import Fernet, InvalidToken

BAN_FILE    = "nox_ban.dat"
SECRET_SEED = "NoxAI_v3_BanKey_2026_!@#"   # semente da chave — não altere
ADMIN_PASS  = "nox2026"                      # senha para visualizar detalhes do ban

import tempfile, platform

# ── Chave disfarçada no Registro do Windows ───────────────────
_REG_PATH  = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_REG_VALUE = "IconUnderlineAsync"   # nome disfarçado de configuração do Explorer

def _reg_write(data: bytes):
    """Salva ban criptografado no Registro do Windows."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_BINARY, data)
        winreg.CloseKey(key)
    except Exception:
        pass

def _reg_read() -> bytes | None:
    """Lê ban do Registro do Windows."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, _REG_VALUE)
        winreg.CloseKey(key)
        return bytes(val) if val else None
    except Exception:
        return None

def _reg_delete():
    """Remove ban do Registro."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, _REG_VALUE)
        winreg.CloseKey(key)
    except Exception:
        pass

def _appdata_path(fp: str) -> Path:
    r"""Caminho oculto no AppData\Roaming com nome disfarçado."""
    fname = hashlib.sha256(f"nox_shadow:{fp}".encode()).hexdigest()[:20]
    base  = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "Microsoft" / "Windows" / "Themes" / fname

def _backup_paths(fp: str) -> list:
    """Retorna lista de caminhos de backup adicionais para o ban."""
    paths = []
    try:
        fname = hashlib.sha256(f"nox_backup:{fp}".encode()).hexdigest()[:20]
        base  = os.environ.get("APPDATA") or str(Path.home() / ".config")
        paths.append(Path(base) / "Microsoft" / "Windows" / "Shell" / fname)
        paths.append(Path(base) / "Local" / "Temp" / f".{fname}")
    except Exception:
        pass
    return paths

# ── Chave Fernet derivada do seed + fingerprint ───────────────
def _derive_key(fp: str) -> bytes:
    raw = hashlib.sha256(f"{SECRET_SEED}:{fp}".encode()).digest()
    return base64.urlsafe_b64encode(raw)

# ── Fingerprint ───────────────────────────────────────────────
def _get_fingerprint() -> str:
    try:
        hostname = socket.gethostname()
        mac      = uuid.UUID(int=uuid.getnode()).hex[-12:]
        # Tenta pegar serial do volume no Windows
        try:
            import subprocess
            out = subprocess.check_output("vol C:", shell=True, stderr=subprocess.DEVNULL).decode()
            serial = re.search(r"[0-9A-F]{4}-[0-9A-F]{4}", out)
            vol = serial.group(0) if serial else "NOVOL"
        except Exception:
            vol = "NOVOL"
        raw = f"{hostname}:{mac}:{vol}"
    except Exception:
        raw = socket.gethostname()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

# ── HMAC do timestamp para impedir alteração de datas ─────────
def _sign(data: str, fp: str) -> str:
    key = hashlib.sha256(f"{SECRET_SEED}:{fp}:SIGN".encode()).digest()
    return hmac.new(key, data.encode(), hashlib.sha256).hexdigest()

def _verify_sign(data: str, sig: str, fp: str) -> bool:
    return hmac.compare_digest(_sign(data, fp), sig)

# ── Salvar / carregar ─────────────────────────────────────────
def _save(ban: dict, fp: str):
    fernet = Fernet(_derive_key(fp))
    raw    = json.dumps(ban, ensure_ascii=False).encode()
    token  = fernet.encrypt(raw)

    # 1) Arquivo principal
    try:
        Path(BAN_FILE).write_bytes(token)
    except Exception:
        pass

    # 2) Registro do Windows (invisível para usuário comum)
    _reg_write(token)

    # 3) AppData shadow com nome disfarçado
    try:
        shadow = _appdata_path(fp)
        shadow.parent.mkdir(parents=True, exist_ok=True)
        shadow.write_bytes(token)
        if platform.system() == "Windows":
            import subprocess
            subprocess.run(["attrib", "+H", "+S", str(shadow)], capture_output=True)
    except Exception:
        pass

    # 4) Backups ocultos adicionais
    for bp in _backup_paths(fp):
        try:
            bp.parent.mkdir(parents=True, exist_ok=True)
            bp.write_bytes(token)
            if platform.system() == "Windows":
                import subprocess
                subprocess.run(["attrib", "+H", "+S", str(bp)], capture_output=True)
        except Exception:
            pass

def _load(fp: str) -> dict | None:
    fernet = Fernet(_derive_key(fp))

    def _try_decrypt(raw_bytes: bytes) -> dict | None | str:
        """Retorna dict se OK, 'corrupted' se adulterado, None se vazio."""
        if not raw_bytes:
            return None
        try:
            return json.loads(fernet.decrypt(raw_bytes))
        except Exception:
            return "corrupted"

    # Coleta dados de todas as fontes
    local_bytes  = Path(BAN_FILE).read_bytes()  if Path(BAN_FILE).exists() else None
    reg_bytes    = _reg_read()
    shadow_bytes = _appdata_path(fp).read_bytes() if _appdata_path(fp).exists() else None
    backup_bytes = None
    for bp in _backup_paths(fp):
        if bp.exists():
            backup_bytes = bp.read_bytes()
            break

    local_r  = _try_decrypt(local_bytes)
    reg_r    = _try_decrypt(reg_bytes)
    shadow_r = _try_decrypt(shadow_bytes)
    backup_r = _try_decrypt(backup_bytes)

    # Se arquivo principal foi adulterado → ban imediato
    if local_r == "corrupted":
        return {"__corrupted__": True}

    # Pega primeiro resultado válido (dict)
    ban = None
    for r, raw in [(local_r, local_bytes), (reg_r, reg_bytes),
                   (shadow_r, shadow_bytes), (backup_r, backup_bytes)]:
        if isinstance(r, dict):
            ban = r
            # Restaura arquivo principal se sumiu
            if local_r is None and raw:
                try: Path(BAN_FILE).write_bytes(raw)
                except Exception: pass
            break

    return ban  # None = sem ban em nenhuma fonte

# ── API pública ───────────────────────────────────────────────

def check_ban() -> dict | None:
    """Retorna None se livre. Retorna dict com info se banido."""
    fp  = _get_fingerprint()
    ban = _load(fp)

    if ban is None:
        return None

    # Arquivo adulterado → trata como ban ativo por mais 24h
    if ban.get("__corrupted__"):
        return {
            "reason":    "Arquivo de ban adulterado — ban renovado automaticamente",
            "trigger":   "Adulteração detectada",
            "expires":   datetime.now() + timedelta(hours=24),
            "banned_at": "?",
            "corrupted": True,
        }

    # Verifica assinatura do timestamp
    expires_str = ban.get("expires", "")
    sig         = ban.get("sig", "")
    if not _verify_sign(expires_str, sig, fp):
        # Alguém editou a data de expiração → ban renovado
        _reban(ban, fp, "Assinatura de tempo inválida — tentativa de desban detectada")
        return check_ban()

    expires = datetime.fromisoformat(expires_str)
    if datetime.now() >= expires:
        Path(BAN_FILE).unlink(missing_ok=True)
        return None

    return {
        "reason":    ban.get("reason", "Conteúdo proibido"),
        "trigger":   ban.get("trigger", "?"),
        "expires":   expires,
        "banned_at": ban.get("banned_at", "?"),
    }


def apply_ban(reason: str, trigger: str, hours: int = 24):
    """Aplica ban de N horas (mínimo 24h sempre)."""
    hours = max(hours, 24)
    fp    = _get_fingerprint()
    now   = datetime.now()
    exp   = (now + timedelta(hours=hours)).isoformat()
    ban   = {
        "reason":    reason,
        "trigger":   trigger,
        "banned_at": now.isoformat(),
        "expires":   exp,
        "hours":     hours,
        "sig":       _sign(exp, fp),
    }
    _save(ban, fp)


def _reban(original: dict, fp: str, extra_reason: str):
    """Renova o ban por mais 24h ao detectar adulteração."""
    now = datetime.now()
    exp = (now + timedelta(hours=24)).isoformat()
    ban = {
        "reason":    extra_reason,
        "trigger":   original.get("trigger", "Adulteração"),
        "banned_at": now.isoformat(),
        "expires":   exp,
        "hours":     24,
        "sig":       _sign(exp, fp),
    }
    _save(ban, fp)


def verify_admin_password(senha: str) -> bool:
    """Verifica se a senha de admin está correta."""
    return hmac.compare_digest(
        hashlib.sha256(senha.encode()).hexdigest(),
        hashlib.sha256(ADMIN_PASS.encode()).hexdigest()
    )


def get_ban_details_with_password(senha: str) -> str:
    """Retorna detalhes completos do ban se a senha estiver correta."""
    if not verify_admin_password(senha):
        return "❌ Senha incorreta."
    ban_info = check_ban()
    if not ban_info:
        return "✅ Nenhum ban ativo."
    exp = ban_info['expires']
    remaining = exp - datetime.now()
    h, m = divmod(int(remaining.total_seconds()) // 60, 60)
    return (
        f"🔒 BAN ATIVO\n"
        f"  Motivo  : {ban_info['reason']}\n"
        f"  Gatilho : {ban_info['trigger']}\n"
        f"  Banido  : {ban_info['banned_at']}\n"
        f"  Expira  : {exp.strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"  Restante: {h}h {m}min\n"
        f"  (Não é possível remover antes do tempo expirar)"
    )


# ── Padrões de intenção ilegal ────────────────────────────────
_INTENT_VERBS = (
    r"(?:como|me ensina|me ajuda a|quero|preciso|consigo|comprar|vender|"
    r"fabricar|fazer|criar|sintetizar|refinar|produzir|obter|achar|"
    r"encontrar|conseguir|montar|preparar|hackear|invadir|atacar|"
    r"derrubar|roubar|clonar|fraudar|espalhar|distribuir)"
)
_DRUG_TARGETS = (
    r"(?:cocaína|cocaina|heroína|heroina|metanfetamina|meth|crack|lsd|"
    r"ecstasy|mdma|fentanil|ketamina|droga[s]?\s+ilegai[s]?)"
)
_HACK_TARGETS = (
    r"(?:site\s+do\s+governo|servidor\s+(?:do\s+)?governo|sistema\s+(?:do\s+)?governo|"
    r"banco\s+(?:central|federal)?|sistema\s+(?:da\s+)?policia|receita\s+federal|"
    r"banco\s+de\s+dados\s+(?:do\s+)?governo|inss|detran|cpf\s+(?:de\s+alguém|alheio)|"
    r"senha\s+(?:de\s+)?(?:alguém|outra\s+pessoa)|conta\s+bancária\s+(?:de\s+alguém)?|"
    r"cartão\s+(?:de\s+crédito\s+)?(?:de\s+alguém|alheio))"
)
_WEAPON_TARGETS = (
    r"(?:bomba|explosivo|artefato\s+explosivo|arma\s+caseira|"
    r"veneno\s+para\s+(?:matar|pessoa)|gás\s+tóxico)"
)
_VIOLENCE_TARGETS = (
    r"(?:matar\s+(?:alguém|uma\s+pessoa)|assassinar|torturar\s+(?:alguém|uma\s+pessoa)|"
    r"sequestrar\s+(?:alguém|uma\s+pessoa))"
)
_CSAM_TARGETS = (
    r"(?:foto[s]?\s+(?:de\s+)?criança[s]?\s+nu[as]?|"
    r"vídeo[s]?\s+(?:de\s+)?menor(?:es)?\s+(?:nu[as]?|pelad[ao]s?)|"
    r"conteúdo\s+(?:de\s+)?criança[s]?|pedofilia|abuso\s+(?:de\s+)?(?:criança|menor))"
)
_FRAUD_TARGETS = (
    r"(?:clonar\s+cartão|fraude\s+bancária|pix\s+falso|boleto\s+falso|"
    r"nota[s]?\s+(?:fals[ao]s?|falsificad[ao]s?)|dinheiro\s+falso|"
    r"documento[s]?\s+falso[s]?|identidade\s+fals[ao])"
)

INTENT_PATTERNS = [
    (rf"{_INTENT_VERBS}\s+.{{0,30}}{_DRUG_TARGETS}",      "solicitar informações sobre drogas ilegais"),
    (rf"{_DRUG_TARGETS}\s+.{{0,30}}{_INTENT_VERBS}",      "solicitar informações sobre drogas ilegais"),
    (rf"{_INTENT_VERBS}\s+.{{0,30}}{_HACK_TARGETS}",      "solicitar invasão de sistemas"),
    (rf"{_HACK_TARGETS}\s+.{{0,30}}{_INTENT_VERBS}",      "solicitar invasão de sistemas"),
    (rf"{_INTENT_VERBS}\s+.{{0,30}}{_WEAPON_TARGETS}",    "solicitar fabricação de armas/explosivos"),
    (rf"{_INTENT_VERBS}\s+.{{0,30}}{_VIOLENCE_TARGETS}",  "solicitar conteúdo de violência grave"),
    (rf"{_CSAM_TARGETS}",                                  "conteúdo de abuso infantil"),
    (rf"{_INTENT_VERBS}\s+.{{0,30}}{_FRAUD_TARGETS}",     "solicitar fraude/falsificação"),
    (rf"{_FRAUD_TARGETS}\s+.{{0,30}}{_INTENT_VERBS}",     "solicitar fraude/falsificação"),
]


def scan_message(text: str) -> tuple[str, str] | None:
    lower = text.lower().strip()
    for pattern, category in INTENT_PATTERNS:
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            return (match.group(0).strip(), category)
    return None


def is_morse_dangerous(text: str):
    result = scan_message(text)
    return result[0] if result else None
