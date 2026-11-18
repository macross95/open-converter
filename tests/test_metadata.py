"""Metadatos al convertir: conservar, selectivo y eliminar."""

import os
import tempfile

import pytest
from PIL import Image, ImageCms

from openconverter.core.converter import Converter

MAKE, ORIENTATION, EXIF_IFD, GPS_IFD = 0x010F, 0x0112, 0x8769, 0x8825
SERIAL, PIXEL_X, DATE_ORIGINAL, DATE_TIME = 0xA431, 0xA002, 0x9003, 0x0132


def _photo(path):
    """Foto 60x40 con EXIF completo, orientación 6 (girada 90°) y perfil sRGB."""
    exif = Image.Exif()
    exif[MAKE] = "Canon"
    exif[ORIENTATION] = 6
    exif[EXIF_IFD] = {DATE_ORIGINAL: "2026:11:09 10:00:00", SERIAL: "SERIE123", PIXEL_X: 60}
    exif[GPS_IFD] = {1: "S", 2: (33.0, 2.0, 0.0), 3: "W", 4: (71.0, 37.0, 0.0)}
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (60, 40), "blue").save(path, format="JPEG", exif=exif.tobytes(), icc_profile=icc)


def _convert(fmt, policy, ext):
    d = tempfile.mkdtemp()
    src = os.path.join(d, "foto.jpg")
    dst = os.path.join(d, "salida." + ext)
    _photo(src)
    Converter().convert(src, dst, format=fmt, metadata=policy)
    img = Image.open(dst)
    img.load()
    return img, img.getexif()


@pytest.mark.parametrize("fmt,ext", [("webp", "webp"), ("jpeg", "jpg"), ("png", "png")])
def test_preserve_keeps_exif_and_fixes_orientation(fmt, ext):
    img, exif = _convert(fmt, "preserve", ext)
    assert exif.get(MAKE) == "Canon"
    assert exif.get_ifd(GPS_IFD), "la ubicación debe conservarse"
    assert exif.get(ORIENTATION) == 1, "los píxeles ya vienen girados"
    assert img.size == (40, 60)
    assert exif.get_ifd(EXIF_IFD).get(PIXEL_X) == 40, "el ancho EXIF debe ser el nuevo"
    assert img.info.get("icc_profile")


def test_preserve_tiff_keeps_basic_exif():
    img, exif = _convert("tiff", "preserve", "tiff")
    assert exif.get(MAKE) == "Canon"
    assert exif.get(DATE_TIME) == "2026:11:09 10:00:00", "la fecha de captura pasa a la fecha principal"
    assert exif.get(ORIENTATION) == 1
    assert not exif.get_ifd(GPS_IFD), "TIFF comprimido no puede guardar GPS"
    assert img.size == (40, 60)
    assert img.info.get("icc_profile")


@pytest.mark.parametrize("fmt,ext", [("jpeg", "jpg"), ("webp", "webp")])
def test_selective_drops_gps_and_serials(fmt, ext):
    img, exif = _convert(fmt, "selective", ext)
    assert exif.get(MAKE) == "Canon"
    assert exif.get_ifd(EXIF_IFD).get(DATE_ORIGINAL) == "2026:11:09 10:00:00"
    assert not exif.get_ifd(GPS_IFD)
    assert SERIAL not in exif.get_ifd(EXIF_IFD)
    assert img.info.get("icc_profile")


@pytest.mark.parametrize("fmt,ext", [("png", "png"), ("tiff", "tiff"), ("webp", "webp"), ("jpeg", "jpg")])
def test_strip_removes_exif_but_keeps_color_profile(fmt, ext):
    img, exif = _convert(fmt, "strip", ext)
    assert MAKE not in exif
    assert not exif.get_ifd(GPS_IFD)
    assert img.info.get("icc_profile"), "sin perfil de color los colores podrían cambiar"


def test_format_without_metadata_still_converts():
    img, exif = _convert("bmp", "preserve", "bmp")
    assert img.size == (40, 60)


def test_heif_keeps_exif_and_strip_removes_it():
    pytest.importorskip("pillow_heif")
    img, exif = _convert("heif", "preserve", "heic")
    assert exif.get(MAKE) == "Canon"
    assert img.size == (40, 60)
    img, exif = _convert("heif", "strip", "heic")
    assert MAKE not in exif
    assert not exif.get_ifd(GPS_IFD), "HEIF no debe copiar el GPS original por su cuenta"
