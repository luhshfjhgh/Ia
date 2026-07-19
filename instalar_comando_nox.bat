@echo off
setlocal enabledelayedexpansion
echo ==========================================================
echo   Instalando o comando "nox" no terminal do Windows
echo ==========================================================
echo.

REM Pasta onde este instalador esta (a pasta do projeto)
set "NOX_DIR=%~dp0"
if "%NOX_DIR:~-1%"=="\" set "NOX_DIR=%NOX_DIR:~0,-1%"

echo Pasta do projeto detectada:
echo   %NOX_DIR%
echo.

REM Le o PATH atual do usuario (registro do Windows)
set "CURRENT_PATH="
for /f "usebackq tokens=2,*" %%A in (`reg query "HKCU\Environment" /v Path 2^>nul`) do set "CURRENT_PATH=%%B"

REM Verifica se a pasta ja esta no PATH
echo !CURRENT_PATH! | find /i "%NOX_DIR%" >nul
if !errorlevel! == 0 (
    echo O comando "nox" ja esta instalado neste computador.
    echo.
    goto fim
)

REM Adiciona a pasta do projeto ao PATH do usuario (permanente)
if defined CURRENT_PATH (
    setx PATH "!CURRENT_PATH!;%NOX_DIR%" >nul
) else (
    setx PATH "%NOX_DIR%" >nul
)

echo Comando "nox" instalado com sucesso!
echo.

:fim
echo ==========================================================
echo   IMPORTANTE: feche este terminal e abra um novo (ou
echo   reinicie o PC) para o comando "nox" funcionar.
echo.
echo   Depois disso, basta digitar:
echo.
echo       nox
echo.
echo   em qualquer pasta do cmd ou PowerShell, e o projeto
echo   abre e a IA ja ativa na hora.
echo ==========================================================
pause
