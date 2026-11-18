#!/usr/bin/env sh
# Ejecuta Open Converter desde el código fuente (macOS y Linux).
# Sin argumentos abre la ventana; con argumentos funciona como la línea de comandos.
cd "$(dirname "$0")" || exit 1
PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m openconverter "$@"
