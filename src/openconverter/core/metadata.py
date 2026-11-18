"""Metadata handling (EXIF/XMP/IPTC/ICC).

Políticas al guardar:
- preserve:  conserva el EXIF completo (fecha, cámara, GPS…) y el perfil de color.
- selective: conserva el EXIF sin GPS ni datos que identifican al dueño o al equipo
             (números de serie, nombre del dueño, MakerNote) y el perfil de color.
- strip:     quita todo el EXIF; solo deja el perfil de color para que los colores no cambien.

TIFF (comprimido con libtiff) solo admite el bloque principal del EXIF: guarda marca,
modelo, fecha, autor y copyright, pero no la ubicación GPS.

En todas, la orientación EXIF queda en 1 porque los píxeles ya se giraron al decodificar.
"""

from typing import Any, Dict, Optional, Tuple

from PIL import Image

from ..core.document import MetadataBag

ORIENTATION = 0x0112
DATE_TIME = 0x0132
DATE_ORIGINAL = 0x9003
EXIF_IFD = 0x8769
GPS_IFD = 0x8825
INTEROP_IFD = 0xA005
PIXEL_X = 0xA002
PIXEL_Y = 0xA003
# Datos personales o del equipo que se quitan en el modo selectivo
PRIVATE_IFD0_TAGS = {0xC62F}  # CameraSerialNumber (DNG)
PRIVATE_EXIF_TAGS = {
    0xA430,  # CameraOwnerName
    0xA431,  # BodySerialNumber
    0xA435,  # LensSerialNumber
    0x927C,  # MakerNote (suele incluir números de serie)
}
# Formatos de Pillow que pueden guardar EXIF y perfil de color
METADATA_FORMATS = {"JPEG", "MPO", "WEBP", "PNG", "TIFF", "AVIF", "HEIF"}
# Claves de img.info que algunos formatos (TIFF, HEIF, PNG, AVIF) copian solos al guardar
INFO_METADATA_KEYS = ("exif", "icc_profile", "xmp", "XML:com.adobe.xmp")


def read_metadata(img: "Image.Image") -> MetadataBag:
    bag = MetadataBag()
    try:
        exif = img.getexif()
        if exif is not None and len(exif):
            bag.exif = {str(k): str(v) for k, v in exif.items()}
            try:
                bag.exif_raw = exif.tobytes()
            except Exception:
                bag.exif_raw = None
    except Exception:
        pass
    try:
        icc = img.info.get("icc_profile")
        if icc:
            bag.icc_profile = icc
    except Exception:
        pass
    try:
        bag.orientation = int(bag.exif.get("274", 1)) if "274" in bag.exif else 1
    except Exception:
        bag.orientation = 1
    # XMP
    try:
        xmp = img.info.get("xmp")
        if xmp:
            bag.xmp = xmp.decode("utf-8", "replace") if isinstance(xmp, (bytes, bytearray)) else str(xmp)
    except Exception:
        pass
    return bag


def basic_exif(exif_bytes: bytes) -> Optional[bytes]:
    """Solo el bloque principal del EXIF (marca, modelo, fecha, autor, copyright).

    TIFF comprimido se guarda con libtiff, que no puede escribir los sub-bloques
    EXIF/GPS. La fecha de captura se copia a la fecha principal si falta.
    """
    try:
        exif = Image.Exif()
        exif.load(exif_bytes)
        if EXIF_IFD in exif:
            taken = exif.get_ifd(EXIF_IFD).get(DATE_ORIGINAL)
            if taken and DATE_TIME not in exif:
                exif[DATE_TIME] = taken
        for tag in (EXIF_IFD, GPS_IFD, INTEROP_IFD):
            if tag in exif:
                del exif[tag]
        return exif.tobytes() if len(exif) else None
    except Exception:
        return None


def build_exif(bag: MetadataBag, policy: str = "preserve",
               size: Optional[Tuple[int, int]] = None) -> Optional[bytes]:
    """EXIF listo para guardar según la política, o None si no corresponde escribir EXIF."""
    if policy == "strip" or not bag.exif_raw:
        return None
    try:
        exif = Image.Exif()
        exif.load(bag.exif_raw)
        if ORIENTATION in exif:
            exif[ORIENTATION] = 1
        if policy == "selective":
            for tag in (GPS_IFD, *PRIVATE_IFD0_TAGS):
                if tag in exif:
                    del exif[tag]
        if EXIF_IFD in exif:
            sub = exif.get_ifd(EXIF_IFD)
            if policy == "selective":
                for tag in PRIVATE_EXIF_TAGS:
                    sub.pop(tag, None)
            if size:
                if PIXEL_X in sub:
                    sub[PIXEL_X] = int(size[0])
                if PIXEL_Y in sub:
                    sub[PIXEL_Y] = int(size[1])
        return exif.tobytes()
    except Exception:
        # Si el EXIF no se puede reescribir, no se copia (evita orientación doble o datos a medias).
        return None


def metadata_save_kwargs(bag: MetadataBag, policy: str, pillow_format: str,
                         size: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """Argumentos de Image.save() con los metadatos que el formato de salida admite."""
    if (pillow_format or "").upper() not in METADATA_FORMATS:
        return {}
    kwargs: Dict[str, Any] = {}
    if bag.icc_profile:
        kwargs["icc_profile"] = bag.icc_profile
    exif = build_exif(bag, policy, size)
    if exif and pillow_format.upper() == "TIFF":
        exif = basic_exif(exif)
    if exif:
        kwargs["exif"] = exif
    return kwargs


def clear_info_metadata(img: "Image.Image") -> None:
    """Quita los metadatos de img.info para que Pillow no los copie por su cuenta al guardar."""
    for key in INFO_METADATA_KEYS:
        img.info.pop(key, None)
    # Pillow guarda en caché el EXIF leído (img.getexif()); pillow_heif lo usa como respaldo.
    if hasattr(img, "_exif"):
        img._exif = None


def apply_metadata_to_pillow(img: "Image.Image", bag: MetadataBag, policy: str = "preserve") -> None:
    """Deja en img.info los metadatos que corresponden a la política: preserve | strip | selective."""
    clear_info_metadata(img)
    if bag.icc_profile:
        img.info["icc_profile"] = bag.icc_profile
    exif = build_exif(bag, policy, img.size)
    if exif:
        img.info["exif"] = exif


def strip_gps(exif_dict: Dict[str, Any]) -> Dict[str, Any]:
    gps_keys = {"34853", "GPSInfo"}
    return {k: v for k, v in exif_dict.items() if k not in gps_keys}
