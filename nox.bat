@echo off
REM ============================================================
REM  nox.bat — Launcher global da NOX AI
REM  Permite abrir o projeto digitando apenas "nox" em qualquer
REM  terminal (cmd ou PowerShell), de qualquer pasta do sistema.
REM ============================================================

REM %~dp0 = pasta onde este arquivo .bat está salvo.
REM Isso garante que ele sempre entre na pasta certa do projeto,
REM não importa de onde o comando "nox" foi digitado.
cd /d "%~dp0"

python main.py

REM Se o Python não for encontrado, avisa o usuário.
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Nao foi possivel iniciar a NOX. Verifique se o Python esta instalado.
    pause
)
