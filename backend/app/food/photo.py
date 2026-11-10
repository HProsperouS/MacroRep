"""Checking a meal photo before it goes to the model (plan.md §17), then rebuilding it.

``check_photo`` is the cheap gate on the request: an allowed type, judged by its bytes as well
as its label, and a bounded size. ``reencode_photo`` then decodes the pixels and writes a fresh
JPEG, so whatever else the upload carried (EXIF and GPS, trailing or embedded data, a second
format hidden in the same file) never reaches the model. The photo is never stored.
"""

from __future__ import annotations

import base64
import binascii
import re
import warnings
from io import BytesIO

from PIL import Image, ImageOps

# The app sends a downscaled JPEG of about 100–300 KB; this leaves room for an original.
MAX_PHOTO_BYTES = 4 * 1024 * 1024
# Base64 grows the bytes by a third, plus the "data:image/...;base64," prefix.
MAX_PHOTO_DATA_URL_LENGTH = MAX_PHOTO_BYTES * 4 // 3 + 64

# Longest side the model gets, as the app itself sends (frontend/src/lib/photo.ts MAX_SIDE).
MAX_PHOTO_SIDE = 1024
# Refused before decoding: a 48 MP phone original fits, a decompression bomb doesn't.
MAX_PHOTO_PIXELS = 50_000_000
REENCODE_QUALITY = 85

_DATA_URL = re.compile(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/]+={0,2})")
# Only these decoders ever run on an upload.
_FORMATS = ("JPEG", "PNG", "WEBP")
_UNREADABLE = "The photo couldn't be read"


class UnreadablePhoto(ValueError):
    """The upload passed the checks but isn't a whole, decodable image."""


def _looks_like(kind: str, data: bytes) -> bool:
    if kind == "jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if kind == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def check_photo(data_url: str) -> str:
    """The data URL unchanged if it holds a JPEG, PNG or WebP image within the size limit."""

    match = _DATA_URL.fullmatch(data_url)
    if match is None:
        raise ValueError("Send the photo as a JPEG, PNG or WebP data URL")
    try:
        data = base64.b64decode(match[2], validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(_UNREADABLE) from None
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError(f"The photo is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB")
    if not _looks_like(match[1], data):
        raise ValueError("The photo isn't the image type it says it is")
    return data_url


def _decode(data: bytes) -> Image.Image:
    """The first frame's pixels, fully loaded, or UnreadablePhoto."""

    with warnings.catch_warnings():
        # Pillow only warns between its own limit and twice it; treat that as a bomb too.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(BytesIO(data), formats=_FORMATS)
            # The header says how big the pixels will be: refuse before any are decoded.
            width, height = image.size
            if width * height > MAX_PHOTO_PIXELS:
                raise UnreadablePhoto("The photo has too many pixels")
            image.seek(0)  # an animated WebP or PNG keeps its first frame
            image.load()
        except UnreadablePhoto:
            raise
        except (
            OSError,
            ValueError,
            SyntaxError,
            EOFError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            raise UnreadablePhoto(_UNREADABLE) from None
    return image


def _flatten(image: Image.Image) -> Image.Image:
    """RGB, with any transparency laid on white rather than turned black."""

    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode in ("RGBA", "LA", "PA"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def reencode_photo(data_url: str) -> str:
    """A fresh JPEG data URL built from the photo's pixels only.

    ``data_url`` must already have passed :func:`check_photo`. The result carries no metadata
    and none of the original's bytes, is upright (EXIF orientation applied before it's
    dropped), and is at most ``MAX_PHOTO_SIDE`` on its longest side. Raises UnreadablePhoto for
    a truncated or corrupt image, or one with too many pixels.
    """

    data = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    image = _decode(data)
    try:
        image = ImageOps.exif_transpose(image)
    except (OSError, ValueError, SyntaxError):
        pass  # a broken orientation tag: keep the pixels as they are
    image = _flatten(image)
    image.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))

    out = BytesIO()
    # No exif= or icc_profile=: nothing from the upload is carried over.
    image.save(out, "JPEG", quality=REENCODE_QUALITY, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
