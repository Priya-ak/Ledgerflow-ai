"""Render synthetic invoice PDFs/images for each demo scenario.

Usage:  python -m app.demo.generate_documents [output_dir]
"""
from __future__ import annotations

import io
import random
import sys
from pathlib import Path

from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.demo.scenarios import BUYER, SCENARIOS, SUPPLIERS, Scenario
from app.services.money import q2

DEFAULT_OUT = Path(__file__).resolve().parents[3] / "sample-data" / "synthetic-invoices"


def inr(v) -> str:
    """Indian digit grouping: 1,23,456.78"""
    s = f"{q2(v):.2f}"
    whole, frac = s.split(".")
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}{whole}.{frac}"


def render_pdf(sc: Scenario) -> bytes:
    sup = SUPPLIERS[sc.supplier]
    t = sc.totals()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    x0, y = 18 * mm, H - 20 * mm
    c.setTitle(f"Synthetic invoice {sc.key}")
    c.setFont("Helvetica-Bold", 15)
    c.drawString(x0, y, sup["name"])
    c.setFont("Helvetica", 9)
    c.drawString(x0, y - 13, sup["address"])
    c.drawString(x0, y - 25, f"Phone: {sup['phone']}  Email: {sup['email']}")
    c.drawString(x0, y - 37, f"GSTIN: {sup['gstin']}")
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(W - x0, y, "TAX INVOICE")
    c.setFont("Helvetica", 9)
    ry = y - 14
    if sc.number:
        c.drawRightString(W - x0, ry, f"Invoice No: {sc.number}"); ry -= 12
    if sc.inv_date:
        c.drawRightString(W - x0, ry, f"Invoice Date: {sc.inv_date.strftime('%d/%m/%Y')}"); ry -= 12
        from datetime import timedelta
        due = sc.inv_date + timedelta(days=sup["terms"])
        c.drawRightString(W - x0, ry, f"Due Date: {due.strftime('%d/%m/%Y')}"); ry -= 12
    if sc.po_number:
        c.drawRightString(W - x0, ry, f"PO No: {sc.po_number}"); ry -= 12

    y -= 62
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(x0, y + 8, W - x0, y + 8)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y - 4, "Bill To:")
    c.setFont("Helvetica", 9)
    c.drawString(x0, y - 16, BUYER["name"])
    c.drawString(x0, y - 28, BUYER["address"])
    if not sc.hide_buyer_gstin:
        c.drawString(x0, y - 40, f"GSTIN: {BUYER['gstin']}")
    c.drawRightString(W - x0, y - 4, f"Place of Supply: {'Tamil Nadu (33)'}")

    # table
    y -= 66
    cols = [("#", 0), ("Description", 8), ("HSN", 78), ("Qty", 93), ("Unit", 106), ("Rate", 120),
            ("Disc", 138), ("Taxable", 150), ("GST", 165), ("Tax", 174), ("Total", 190)]
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(x0 - 2, y - 4, W - 2 * x0 + 4, 14, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    for name, off in cols:
        c.drawString(x0 + off * mm * 0.9, y, name)
    c.setFont("Helvetica", 8)
    for i, ln in enumerate(sc.lines, 1):
        y -= 15
        vals = [str(i), ln.desc, ln.hsn, f"{ln.qty.normalize():f}", ln.unit, inr(ln.price), inr(ln.disc),
                inr(ln.taxable), f"{ln.rate.normalize():f}", inr(ln.tax), inr(ln.total)]
        for (name, off), v in zip(cols, vals):
            c.drawString(x0 + off * mm * 0.9, y, v)
    y -= 10
    c.line(x0, y, W - x0, y)

    # summary
    sx = W - x0 - 75 * mm
    rows = [("Sub Total", t["subtotal"]), ("Discount", t["discount"]), ("Taxable Amount", t["taxable"])]
    if sc.intra:
        rows += [("CGST", t["cgst"]), ("SGST", t["sgst"])]
    else:
        rows += [("IGST", t["igst"])]
    rows += [("Total Tax", t["tax"]), ("Grand Total", t["grand"])]
    for label, val in rows:
        y -= 14
        c.setFont("Helvetica-Bold" if label == "Grand Total" else "Helvetica", 9)
        c.drawString(sx, y, label)
        c.drawRightString(W - x0, y, f"Rs. {inr(val)}")
    y -= 30
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(x0, y, "Bank and payment details intentionally omitted.")
    c.drawString(x0, 14 * mm, "SYNTHETIC SAMPLE DOCUMENT - FICTIONAL DATA FOR LEDGERFLOW AI DEMO - NOT A REAL INVOICE")
    c.showPage()
    c.save()
    return buf.getvalue()


def pdf_to_image(pdf: bytes, dpi: int) -> Image.Image:
    import fitz
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        pix = doc.load_page(0).get_pixmap(dpi=dpi)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def degrade(img: Image.Image, seed: int = 7) -> Image.Image:
    rnd = random.Random(seed)
    img = img.rotate(1.2, expand=True, fillcolor="white", resample=Image.BICUBIC)
    px = img.load()
    for _ in range(img.width * img.height // 60):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        g = rnd.randint(120, 220)
        px[x, y] = (g, g, g)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def generate(out: Path = DEFAULT_OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for sc in SCENARIOS:
        pdf = render_pdf(sc)
        if sc.fmt == "pdf":
            p = out / f"{sc.key}.pdf"
            p.write_bytes(pdf)
        elif sc.fmt == "png":
            p = out / f"{sc.key}.png"
            pdf_to_image(pdf, 170).save(p, optimize=True)
        else:
            p = out / f"{sc.key}.jpg"
            degrade(pdf_to_image(pdf, 150)).save(p, quality=62)
        paths.append(p)
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for p in generate(target):
        print(p)
