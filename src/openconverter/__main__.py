"""Permite ejecutar `python -m openconverter` (sin argumentos abre la ventana)."""

import sys

from .cli.main import main

sys.exit(main())
