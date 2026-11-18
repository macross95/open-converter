#!/usr/bin/env sh
# Instala Open Converter en un entorno virtual (.venv) con todos los formatos opcionales.
# Linux (Ubuntu/Debian) necesita antes:  sudo apt install python3-venv python3-tk
# macOS necesita Python con Tk:          brew install python-tk
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[all]"
echo
echo "Listo. Abre la ventana con: .venv/bin/openconverter"
echo "O convierte por consola:    .venv/bin/openconverter convert entrada.png salida.webp"
