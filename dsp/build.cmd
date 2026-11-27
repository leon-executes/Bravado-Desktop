@echo off
setlocal
cd /d "%~dp0"
gcc -std=c11 -Wall -Wextra -Werror -O3 -shared -static-libgcc -s -Wl,--no-insert-timestamp,--image-base,0x180000000 -o BravadoSpectral.dll spectral.c
if errorlevel 1 exit /b 1
gcc -std=c11 -Wall -Wextra -Werror -O3 -shared -static-libgcc -s -Wl,--no-insert-timestamp,--image-base,0x180000000 -DBRAVADO_SIDECHAIN=1 -o BravadoCrevasse.dll spectral.c
if errorlevel 1 exit /b 1
for %%F in (BravadoSpectral.dll BravadoCrevasse.dll) do certutil -hashfile %%F SHA256
echo Update processor hashes in bravado.py after a deliberate change, then run build_exe.cmd.
