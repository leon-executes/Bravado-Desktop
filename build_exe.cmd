@echo off
rem SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
rem Leon-Executes / release bench.
setlocal
cd /d "%~dp0"
rem PyInstaller cleans its output folder. Never erase a used portable app.
if exist "dist\Bravado\bravado-data" (
  echo Build stopped: dist\Bravado contains saved application data.
  echo Close Bravado and move the complete dist\Bravado folder elsewhere before rebuilding.
  exit /b 1
)
if defined BRAVADO_PYTHON (
  "%BRAVADO_PYTHON%" -m venv .build-venv
) else (
  py -3.12 -m venv .build-venv
)
if errorlevel 1 goto :failed
set "BUILD_PYTHON=%CD%\.build-venv\Scripts\python.exe"
"%BUILD_PYTHON%" -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Use CPython 3.12 x64'"
if errorlevel 1 goto :failed
"%BUILD_PYTHON%" -m pip install --disable-pip-version-check --no-cache-dir -r requirements-build.txt
if errorlevel 1 goto :failed
if not exist build mkdir build
"%BUILD_PYTHON%" bravado.py --self-test --report build\source-tests.txt
if errorlevel 1 goto :failed
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name Bravado --icon "%CD%\bravado.ico" --add-data "%CD%\bravado.ico;." --exclude-module webview.platforms.cef --exclude-module webview.platforms.qt --specpath build --workpath build\pyinstaller --distpath dist bravado.py
if errorlevel 1 goto :failed
for %%F in (README.md DEPENDENCIES.md PRESETS.md LICENSE THIRD_PARTY_NOTICES.txt requirements-build.txt) do (
  copy /y "%%F" "dist\Bravado\%%F" >nul
  if errorlevel 1 goto :failed
)
start "" /wait "dist\Bravado\Bravado.exe" --self-test --report "%CD%\build\packaged-tests.txt"
if errorlevel 1 goto :failed
echo Built dist\Bravado\Bravado.exe. Keep its _internal folder alongside it.
echo Equalizer APO is required separately for system audio processing.
exit /b 0
:failed
echo Build failed. Review the output and build\*-tests.txt.
exit /b 1

