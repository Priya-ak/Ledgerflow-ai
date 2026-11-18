"""Text extraction: PyMuPDF for digital PDFs, Tesseract OCR for scans and images.

Memory-conscious: pages are processed one at a time and rendered images are
released immediately, so a 4 GB machine can process multi-page scans.
"""
from __future__ import annotations

import io
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from app.core.config import settings

log = logging.getLogger("ledgerflow.ocr")

MIN_TEXT_CHARS = 30  # below this, a PDF page is treated as scanned


@dataclass
class TextResult:
    text: str
    method: str  # pdf_text | ocr | mixed
    page_count: int
    ocr_confidence: float | None = None
    warnings: list[str] = field(default_factory=list)


class OcrUnavailable(RuntimeError):
    pass


def _tesseract():
    import pytesseract
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    elif not shutil.which("tesseract"):
        raise OcrUnavailable("Tesseract is not installed or TESSERACT_CMD is not set.")
    return pytesseract


def ocr_available() -> bool:
    if settings.OCR_ENGINE == "none":
        return False
    try:
        _tesseract().get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")
    # Upscale small images; Tesseract works best around 300 DPI equivalent.
    if img.width < 1400:
        scale = 1400 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(3))
    return img


def _ocr_image(img: Image.Image) -> tuple[str, float | None]:
    if settings.OCR_ENGINE == "none":
        raise OcrUnavailable("OCR is disabled (OCR_ENGINE=none).")
    pt = _tesseract()
    img = _preprocess(img)
    data = pt.image_to_data(img, config="--psm 6", output_type=pt.Output.DICT)
    lines: dict[tuple, list[str]] = {}
    confs: list[float] = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        try:
            c = float(data["conf"][i])
            if c >= 0:
                confs.append(c)
        except (TypeError, ValueError):
            pass
    text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return text, (round(sum(confs) / len(confs), 1) if confs else None)


def _pdf_page_lines(page) -> str:
    """Rebuild visual lines from word boxes so table rows stay on one line."""
    words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, wordno
    rows: list[list] = []
    for w in sorted(words, key=lambda w: (round(w[3], 0), w[0])):
        y = (w[1] + w[3]) / 2
        if rows and abs(rows[-1][0] - y) <= 3.0:
            rows[-1][1].append(w)
        else:
            rows.append([y, [w]])
    out = []
    for _, ws in rows:
        ws.sort(key=lambda w: w[0])
        out.append(" ".join(w[4] for w in ws))
    return "\n".join(out)


def extract_text(path: Path, kind: str) -> TextResult:
    if kind == "pdf":
        return _extract_pdf(path)
    with Image.open(path) as img:
        text, conf = _ocr_image(img)
    warnings = [] if conf is None or conf >= 70 else [f"Low OCR confidence ({conf}%). Review all fields carefully."]
    return TextResult(text=text, method="ocr", page_count=1, ocr_confidence=conf, warnings=warnings)


def _extract_pdf(path: Path) -> TextResult:
    import fitz  # PyMuPDF

    parts: list[str] = []
    methods: set[str] = set()
    confs: list[float] = []
    warnings: list[str] = []
    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("Password-protected PDFs are not supported.")
        n = doc.page_count
        limit = min(n, settings.MAX_PDF_PAGES)
        if n > limit:
            warnings.append(f"Only the first {limit} of {n} pages were processed.")
        for i in range(limit):
            page = doc.load_page(i)
            text = _pdf_page_lines(page)
            if len(text.strip()) >= MIN_TEXT_CHARS:
                parts.append(text)
                methods.add("pdf_text")
            else:
                try:
                    pix = page.get_pixmap(dpi=settings.OCR_DPI, colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    del pix
                    t, conf = _ocr_image(img)
                    img.close()
                    parts.append(t)
                    methods.add("ocr")
                    if conf is not None:
                        confs.append(conf)
                except OcrUnavailable as e:
                    warnings.append(f"Page {i + 1} looks scanned but OCR is unavailable: {e}")
            page = None  # release page resources
    method = "mixed" if len(methods) > 1 else (methods.pop() if methods else "pdf_text")
    conf = round(sum(confs) / len(confs), 1) if confs else None
    if conf is not None and conf < 70:
        warnings.append(f"Low OCR confidence ({conf}%). Review all fields carefully.")
    return TextResult(text="\n".join(parts), method=method, page_count=n, ocr_confidence=conf, warnings=warnings)
