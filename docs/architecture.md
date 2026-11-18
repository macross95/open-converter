# Arquitectura

Open Converter está separado en capas para que la ventana, la línea de comandos y las
pruebas usen el mismo núcleo.

| Capa | Ubicación | Qué hace |
|---|---|---|
| Registro de formatos | `core/registry.py` | Elige el adaptador según el contenido o la extensión del archivo. |
| Adaptadores | `adapters/` | Leen y escriben cada formato (Pillow, HEIF, RAW, SVG, imageio). |
| Pipeline | `core/pipeline.py` | Transformaciones encadenables: redimensionar, recortar, rotar, voltear, grises. |
| Metadatos | `core/metadata.py` | Políticas `preserve`, `selective` y `strip` para EXIF y perfil de color. |
| Conversor | `core/converter.py` | Une lo anterior: leer → transformar → guardar. |
| Trabajos | `core/jobs.py` | Conversión en lote con varios hilos (línea de comandos). |
| Interfaz | `gui/tk_app.py` | Ventana en CustomTkinter, diseño adaptable y arrastrar y soltar. |
| Barra de título | `gui/win_frame.py` | Solo Windows: quita la barra del sistema y conserva redimensionar, maximizar y Aero Snap. |
| Botones | `gui/gradient_button.py` | Botones con degradado y resplandor (sólidos) o efecto vidrio (secundarios), dibujados con Pillow. |
| Línea de comandos | `cli/main.py` | `openconverter convert/batch/info/formats/presets/gui`. |
| Una sola ventana | `single_instance.py` | Si el programa ya está abierto, lo trae al frente. |

## Metadatos

- **preserve**: copia el EXIF completo (fecha, cámara, GPS) y el perfil de color.
- **selective**: copia el EXIF sin GPS, sin números de serie ni nombre del dueño.
- **strip**: no copia EXIF; solo el perfil de color.

En todas, la orientación EXIF queda en 1 porque los píxeles ya se giraron al leer la imagen.
TIFF comprimido solo admite el bloque principal del EXIF (marca, modelo y fecha), sin GPS.

## Agregar un formato

Ver [adding-a-format.md](adding-a-format.md).

## Windows, macOS y Linux

Lo que cambia entre sistemas está en `platform_utils.py` (carpeta de ajustes, abrir archivos y carpetas,
tipografías, tecla de atajos). En Windows la ventana usa barra de título propia y los íconos de la
fuente Segoe Fluent; en macOS y Linux usa la barra nativa y los íconos que dibuja `gui/vector_icons.py`.
La instancia única usa un mutex en Windows y un archivo bloqueado (`fcntl`) en los demás.
