"""Punto de entrada del ejecutable de Windows (PyInstaller).

Sin argumentos abre la ventana; con argumentos funciona como la línea de comandos.
"""

import sys

from openconverter.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
