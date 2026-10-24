@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
 echo Instale Python 3.12 de https://www.python.org/downloads/windows/ e execute novamente.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
 echo Falha na instalacao. Confira a conexao e a mensagem acima.
 pause
 exit /b 1
)
echo Instalacao concluida. Abra run.cmd.
