# Agregar un formato

1. Crea `src/openconverter/adapters/miformato_adapter.py`.
2. Hereda de `FormatAdapter` y define `id`, `extensions`, `mime_types` y `capabilities`.
3. Implementa `can_decode`, `decode` y `encode`.
4. Regístralo en `core/registry.py`, dentro de `build_default_registry`
   (envuelto en `try/except` si depende de una librería opcional).
5. Si el formato guarda EXIF o perfil de color, agrégalo a `METADATA_FORMATS`
   en `core/metadata.py` y en `gui/tk_app.py`.
6. Agrega pruebas en `tests/`.
7. Menciónalo en la lista de formatos del README.
