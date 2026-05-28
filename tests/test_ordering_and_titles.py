from pathlib import Path

import pytest

from pdf_merger.merge_pdfs import clean_title, get_ordered_pdf_files, get_prefix_number


def test_get_prefix_number_parses_leading_digits(tmp_path: Path) -> None:
    p = tmp_path / "01.Passport.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    assert get_prefix_number(p) == 1


def test_get_prefix_number_missing_prefix_raises(tmp_path: Path) -> None:
    p = tmp_path / "Passport.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    with pytest.raises(ValueError, match="no numeric prefix"):
        get_prefix_number(p)


def test_clean_title_strips_prefix_and_separators(tmp_path: Path) -> None:
    assert clean_title(tmp_path / "01.Passport.pdf") == "Passport"
    assert clean_title(tmp_path / "2_Payslips-2024.pdf") == "Payslips 2024"
    assert clean_title(tmp_path / "003. Naturalisation_Test.pdf") == "Naturalisation Test"


def test_get_ordered_pdf_files_orders_by_prefix(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for name in ["10.Ten.pdf", "2.Two.pdf", "01.One.pdf"]:
        (input_dir / name).write_bytes(b"%PDF-1.4\n%fake\n")

    ordered = get_ordered_pdf_files(input_dir)
    assert [p.name for p in ordered] == ["01.One.pdf", "2.Two.pdf", "10.Ten.pdf"]


def test_get_ordered_pdf_files_duplicate_prefix_raises(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "01.A.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    (input_dir / "01.B.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

    with pytest.raises(ValueError, match="Duplicate numeric prefixes"):
        get_ordered_pdf_files(input_dir)

