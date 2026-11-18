@echo off
rem Instala Open Converter en modo desarrollo con todos los formatos opcionales.
setlocal
cd /d "%~dp0"
python -m pip install -e ".[all]"
echo.
echo Listo. Abre la ventana con: openconverter
echo O convierte por consola:    openconverter convert entrada.png salida.webp
