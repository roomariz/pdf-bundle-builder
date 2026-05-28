from __future__ import annotations

from pathlib import Path

import pytest
try:
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("Project dependencies not installed (PyPDF2/ReportLab).", allow_module_level=True)

from pdf_merger.merge_pdfs import _calculate_section_start_pages, _get_pdf_page_count, merge_pdfs


def _make_pdf(path: Path, pages: int) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for i in range(pages):
        c.setFont("Helvetica", 12)
        c.drawString(72, 720, f"Page {i+1}")
        c.showPage()
    c.save()


def test_get_pdf_page_count_counts_pages(tmp_path: Path) -> None:
    p = tmp_path / "a.pdf"
    _make_pdf(p, pages=3)
    assert _get_pdf_page_count(p) == 3


def test_calculate_section_start_pages_with_toc_and_dividers(tmp_path: Path) -> None:
    pdf1 = tmp_path / "01.A.pdf"
    pdf2 = tmp_path / "02.B.pdf"
    _make_pdf(pdf1, pages=2)
    _make_pdf(pdf2, pages=3)

    # Pretend TOC renders to 2 pages.
    start_pages = _calculate_section_start_pages(
        [pdf1, pdf2],
        toc_pages=2,
        include_toc=True,
        include_dividers=True,
    )
    # With TOC=2 pages, first divider starts at page 3, second divider starts at page 6:
    # p1: divider(1) + 2 pages => total 3 pages after TOC
    assert start_pages[1] == 3
    assert start_pages[2] == 6


def test_calculate_section_start_pages_no_toc_no_dividers(tmp_path: Path) -> None:
    pdf1 = tmp_path / "01.A.pdf"
    pdf2 = tmp_path / "02.B.pdf"
    _make_pdf(pdf1, pages=2)
    _make_pdf(pdf2, pages=3)

    start_pages = _calculate_section_start_pages(
        [pdf1, pdf2],
        toc_pages=0,
        include_toc=False,
        include_dividers=False,
    )
    assert start_pages[1] == 1
    assert start_pages[2] == 3


def test_merge_pdfs_output_exists_and_has_expected_total_pages(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _make_pdf(input_dir / "01.A.pdf", pages=2)
    _make_pdf(input_dir / "02.B.pdf", pages=3)

    out = tmp_path / "out.pdf"
    merged = merge_pdfs(input_dir=input_dir, output_file=out)

    assert merged.exists()
    reader = PdfReader(str(merged))
    # TOC is 1 page for 2 items, plus 2 divider pages, plus 2+3 pdf pages.
    assert len(reader.pages) == 1 + 2 + (2 + 3)

    toc_text = (reader.pages[0].extract_text() or "").replace("\n", " ")
    # Document 01 divider starts on page 2 (TOC is 1 page), document 02 divider starts on page 5.
    assert "2" in toc_text
    assert "5" in toc_text


def test_merge_pdfs_errors_on_encrypted_pdf(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    plain = input_dir / "01.Plain.pdf"
    _make_pdf(plain, pages=1)

    encrypted = input_dir / "02.Secret.pdf"
    _make_pdf(encrypted, pages=1)

    # Encrypt the second PDF.
    r = PdfReader(str(encrypted))
    w = PdfWriter()
    for page in r.pages:
        w.add_page(page)
    w.encrypt("pw")
    with encrypted.open("wb") as f:
        w.write(f)

    with pytest.raises(ValueError, match="Encrypted PDF"):
        merge_pdfs(input_dir=input_dir, output_file=tmp_path / "out.pdf")


def test_merge_pdfs_errors_on_corrupt_pdf(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    good = input_dir / "01.Good.pdf"
    _make_pdf(good, pages=1)

    bad = input_dir / "02.Bad.pdf"
    bad.write_bytes(b"this is not a real pdf")

    with pytest.raises(ValueError, match="Failed to read PDF"):
        merge_pdfs(input_dir=input_dir, output_file=tmp_path / "out.pdf")
