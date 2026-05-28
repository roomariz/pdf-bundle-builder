from pathlib import Path


def test_sample_input_contains_five_pdfs() -> None:
    root = Path(__file__).resolve().parents[1]
    sample_dir = root / "sample-input"
    assert sample_dir.exists()
    pdfs = sorted(p.name for p in sample_dir.glob("*.pdf"))
    assert len(pdfs) == 5
    assert pdfs[0].startswith("01.")
    assert pdfs[-1].startswith("05.")

