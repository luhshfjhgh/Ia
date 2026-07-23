# -*- coding: utf-8 -*-
"""
config_manager.py — Gerenciador de configurações da Nox AI.

Lê variáveis sensíveis (API key, URL) do arquivo .env.
Lê configurações gerais do config.json.
O .env tem prioridade sobre config.json para chaves que existirem nos dois.
"""

import json
import os
from typing import Any

CONFIG_FILE = "config.json"
ENV_FILE    = ".env"

# Configurações padrão (não-sensíveis)
DEFAULTS: dict = {
    "api_url":              "",
    "api_key":              "",
    "ollama_model": os.getenv("OLLAMA_MODEL", "gemma2:2b"),
        "model":                "openai/gpt-oss-120b",
    "model_dev":            "deepseek-coder-v2",
    "max_tokens":           1024,
    "temperature":          0.85,
    "voice_enabled":        False,
    "tts_voice":            "pt-BR-FranciscaNeural",
    "max_history_context":  20,
    "typing_delay":         0.018,
    "language":             "auto",
    "show_timestamps":      False,
    "auto_save_interval":   10,
    "tts_speed":            "normal",
    "personality":          "sarcastica",
}

# Mapeamento: chave interna → variável no .env
ENV_MAP = {
    "api_url":              "NOX_API_URL",
    "api_key":              "NOX_API_KEY",
    "model":                "NOX_MODEL",
    "model_dev":            "NOX_MODEL_DEV",
    "max_tokens":           "NOX_MAX_TOKENS",
    "temperature":          "NOX_TEMPERATURE",
    "voice_enabled":        "NOX_VOICE_ENABLED",
    "tts_voice":            "NOX_TTS_VOICE",
    "max_history_context":  "NOX_MAX_HISTORY_CONTEXT",
    "typing_delay":         "NOX_TYPING_DELAY",
    "language":             "NOX_LANGUAGE",
    "show_timestamps":      "NOX_SHOW_TIMESTAMPS",
    "auto_save_interval":   "NOX_AUTO_SAVE_INTERVAL",
}


class ConfigManager:
    """Gerencia configurações da Nox AI lendo .env e config.json."""

    def __init__(self):
        self._data = self._load()

    # ─── Carregamento ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        """
        Ordem de prioridade:
          1. Variáveis de ambiente do sistema (os.environ)
          2. Arquivo .env
          3. config.json
          4. DEFAULTS internos
        """
        # Começa com os defaults
        merged = dict(DEFAULTS)

        # Carrega config.json (sobrescreve defaults)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    from_json = json.load(f)
                merged.update(from_json)
            except (json.JSONDecodeError, IOError):
                pass

        # Carrega .env (sobrescreve config.json para chaves mapeadas)
        env_vars = self._parse_env_file()
        for internal_key, env_key in ENV_MAP.items():
            # Prioridade: variável de sistema > .env
            raw = os.environ.get(env_key) or env_vars.get(env_key)
            if raw is not None:
                merged[internal_key] = self._cast(internal_key, raw)

        # Recria config.json sem dados sensíveis (apenas configurações gerais)
        self._write_config_without_secrets(merged)

        return merged

    def _parse_env_file(self) -> dict:
        """Lê o arquivo .env e retorna um dicionário de variáveis."""
        env_vars = {}
        if not os.path.exists(ENV_FILE):
            return env_vars
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Ignora comentários e linhas vazias
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        env_vars[key.strip()] = value.strip()
        except IOError:
            pass
        return env_vars

    def _cast(self, key: str, value: str) -> Any:
        """Converte string do .env para o tipo correto."""
        default = DEFAULTS.get(key)
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes")
        if isinstance(default, int):
            try: return int(value)
            except ValueError: return default
        if isinstance(default, float):
            try: return float(value)
            except ValueError: return default
        return value

    def _write_config_without_secrets(self, data: dict):
        """
        Salva config.json apenas com configurações não-sensíveis.
        Chaves api_key e api_url ficam SOMENTE no .env.
        """
        SECRET_KEYS = {"api_key", "api_url"}
        safe = {k: v for k, v in data.items() if k not in SECRET_KEYS}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(safe, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    # ─── Acesso público ────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """Atualiza em memória e persiste no config.json (não-sensíveis)."""
        self._data[key] = value
        self._write_config_without_secrets(self._data)

    def all(self) -> dict:
        """Retorna todas as configurações (oculta api_key por segurança)."""
        safe = dict(self._data)
        if safe.get("api_key"):
            safe["api_key"] = "***" + safe["api_key"][-6:]
        return safe
