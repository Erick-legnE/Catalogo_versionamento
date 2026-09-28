@echo off
chcp 65001 > nul
title Atualizar Catalogo Brasil Botoes

echo.
echo ====================================================
echo   Brasil Botoes ^| Atualizando Catalogo e Portal
echo ====================================================
echo.

cd /d "%~dp0"

echo [1/3] Gerando dados do catalogo geral...
python "%~dp0gerar_json_aprendiz.py"
if %errorlevel% neq 0 (
    echo.
    echo  ERRO ao gerar o JSON do catalogo geral.
    echo  Verifique se a planilha esta fechada e tente novamente.
    pause
    exit /b 1
)

echo.
echo [2/3] Gerando subsites (Representantes, Clientes, Modelos, Cores)...
python "%~dp0gerador.py"
if %errorlevel% neq 0 (
    echo.
    echo  ERRO ao gerar os subsites.
    echo  Verifique se a planilha de Clientes esta fechada e tente novamente.
    pause
    exit /b 1
)

echo.
echo [3/3] Enviando para o GitHub...
git add -A
git commit -m "Atualizacao Portal e Catalogos %date%"
if %errorlevel% neq 0 (
    echo  Nenhuma alteracao detectada ou erro no commit.
)
git pull origin main --rebase
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo  ERRO ao enviar para o GitHub.
    echo  Verifique sua conexao com a internet.
    pause
    exit /b 1
)

@echo off
echo Running catalog build and versioning script...
python gerador.py
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Build completed at %DATE% %TIME%
) else (
    echo [ERROR] Build failed! Check Python errors.
)
pause

echo.
echo ====================================================
echo  Portal e Catalogos atualizados com sucesso!
echo ====================================================
timeout /t 5