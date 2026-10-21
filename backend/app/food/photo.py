"""Checking a meal photo before it goes to the model (plan.md §17): an allowed type, judged by
its bytes as well as its label, and a bounded size. The photo is never stored."""

from __future__ import annotations

import base64
import binascii
import re

# The app sends a downscaled JPEG of about 100–300 KB; this leaves room for an original.
MAX_PHOTO_BYTES = 4 * 1024 * 1024
# Base64 grows the bytes by a third, plus the "data:image/...;base64," prefix.
MAX_PHOTO_DATA_URL_LENGTH = MAX_PHOTO_BYTES * 4 // 3 + 64

_DATA_URL = re.compile(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/]+={0,2})")


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
        raise ValueError("The photo couldn't be read") from None
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError(f"The photo is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB")
    if not _looks_like(match[1], data):
        raise ValueError("The photo isn't the image type it says it is")
    return data_url
