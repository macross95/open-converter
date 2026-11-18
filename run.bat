@echo off
rem Ejecuta Open Converter desde el código fuente (sin argumentos abre la ventana).
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
python -m openconverter %*
