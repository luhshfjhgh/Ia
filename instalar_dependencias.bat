@echo off
echo ==========================================
echo   Instalador de Dependencias - NOX AI v4
echo ==========================================
echo.
echo Verificando instalacao do Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado! Por favor, instale o Python em python.org
    pause
    exit /b
)

echo Instalando bibliotecas necessarias...
pip install -r requirements.txt

echo.
echo ==========================================
echo   Instalacao Concluida!
echo   Agora voce pode rodar: python main.py
echo ==========================================
pause
