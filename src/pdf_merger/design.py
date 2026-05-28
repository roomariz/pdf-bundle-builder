from io import BytesIO
from pathlib import Path
from typing import Callable, Mapping

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

WHITE = HexColor("#FFFFFF")
DARK = HexColor("#1E1E1E")

ACCENT = HexColor("#C9784A")
ACCENT_LIGHT = HexColor("#E9C7B1")

GREY = HexColor("#7A7A7A")
LIGHT_GREY = HexColor("#E8E8E8")


def add_page_number(c: canvas.Canvas, page_number: int) -> None:
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    c.drawRightString(530, 30, str(page_number))


def draw_background(c: canvas.Canvas, width: float, height: float) -> None:
    c.setFillColor(WHITE)
    c.rect(0, 0, width, height, fill=1, stroke=0)


def create_toc_pdf(
    pdf_files: list[Path],
    clean_title: Callable[[Path], str],
    section_start_pages: Mapping[int, int] | None = None,
) -> BytesIO:
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    page_number = 1
    draw_background(c, width, height)

    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 60, "DOCUMENT BUNDLE")

    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 95, "Table of Contents")

    c.setStrokeColor(ACCENT_LIGHT)
    c.setLineWidth(1)
    c.line(80, height - 125, width - 80, height - 125)

    y = height - 175

    for index, pdf_file in enumerate(pdf_files, start=1):
        title = clean_title(pdf_file)
        start_page = section_start_pages.get(index) if section_start_pages else None

        c.setFillColor(ACCENT)
        c.circle(102, y + 2, 13, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(102, y - 1, f"{index:02}")

        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(140, y, title[:62])

        if start_page is not None:
            c.setFillColor(DARK)
            c.setFont("Helvetica-Bold", 12)
            c.drawRightString(width - 90, y, str(start_page))

        c.setStrokeColor(ACCENT_LIGHT)
        c.setLineWidth(0.8)
        c.line(90, y - 18, width - 90, y - 18)

        y -= 48

        if y < 80:
            add_page_number(c, page_number)
            c.showPage()
            page_number += 1
            draw_background(c, width, height)
            y = height - 90

    add_page_number(c, page_number)
    c.save()

    buffer.seek(0)
    return buffer


def create_section_pdf(index: int, title: str, page_number: int) -> BytesIO:
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    draw_background(c, width, height)

    c.setFillColor(GREY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height / 2 + 45, "Document")

    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(width / 2, height / 2 + 5, f"{index:02}")

    c.setFillColor(DARK)
    c.setFont("Helvetica", 15)
    c.drawCentredString(width / 2, height / 2 - 38, title)

    add_page_number(c, page_number)

    c.save()

    buffer.seek(0)
    return buffer
