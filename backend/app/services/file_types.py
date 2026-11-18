"""Content-based file type detection. Filenames and client MIME types are not trusted."""
from __future__ import annotations

SIGNATURES = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpeg": (b"\xff\xd8\xff",),
}
CONTENT_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpeg": "image/jpeg"}
EXTENSIONS = {"pdf": {".pdf"}, "png": {".png"}, "jpeg": {".jpg", ".jpeg"}}


def sniff(head: bytes) -> str | None:
    for kind, sigs in SIGNATURES.items():
        if any(head.startswith(s) for s in sigs):
            return kind
    return None
