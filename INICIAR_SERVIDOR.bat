@echo off
cd /d "%~dp0"
title Brasil Botoes - Catalogo + Automacao Server

py -c "import fastapi,uvicorn,multipart,reportlab,PIL,fontTools" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias do servidor...
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Falha ao instalar dependencias.
        pause
        exit /b 1
    )
)

echo.
py server.py
pause
