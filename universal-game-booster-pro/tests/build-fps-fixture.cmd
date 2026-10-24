@echo off
setlocal
cd /d "%~dp0\.."
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "BOOSTER_VS_ROOT=%%i"
if not defined BOOSTER_VS_ROOT exit /b 1
call "%BOOSTER_VS_ROOT%\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
if not exist build mkdir build
cl /nologo /EHsc tests\fps_fixture.cpp /Fo:build\fps_fixture.obj /Fe:build\fps_fixture.exe /link user32.lib d3d11.lib dxgi.lib /SUBSYSTEM:WINDOWS
exit /b %errorlevel%
