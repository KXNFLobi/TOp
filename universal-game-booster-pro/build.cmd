@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.cmd
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name UniversalGameBoosterPro main.py
if errorlevel 1 exit /b 1
echo Executavel criado em dist\UniversalGameBoosterPro\UniversalGameBoosterPro.exe
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
 "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\UniversalGameBoosterPro.iss
 if errorlevel 1 exit /b 1
 echo Instalador criado em dist\installer\UniversalGameBoosterPro-Setup.exe
) else (
 echo Para gerar o Setup, instale Inno Setup 6 e compile installer\UniversalGameBoosterPro.iss.
)
pause
