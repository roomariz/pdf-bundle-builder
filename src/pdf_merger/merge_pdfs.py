import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Mapping

from PyPDF2 import PdfMerger, PdfReader

from pdf_merger.design import create_section_pdf, create_toc_pdf


def get_prefix_number(file_path: Path) -> int:
    match = re.match(r"^\s*(\d+)", file_path.stem)

    if not match:
        raise ValueError(
            f"File has no numeric prefix: {file_path.name}\n"
            "Please rename it like: 1.Passport.pdf or 01.Passport.pdf"
        )

    return int(match.group(1))


def clean_title(file_path: Path) -> str:
    name = file_path.stem
    name = re.sub(r"^\s*\d+[\s._-]*", "", name)
    return name.replace("_", " ").replace("-", " ").strip()


def get_ordered_pdf_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")

    pdf_files = list(input_dir.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {input_dir}")

    prefixes_to_files: dict[int, list[Path]] = {}
    for pdf_file in pdf_files:
        prefix = get_prefix_number(pdf_file)
        prefixes_to_files.setdefault(prefix, []).append(pdf_file)

    duplicates = {k: v for k, v in prefixes_to_files.items() if len(v) > 1}
    if duplicates:
        parts: list[str] = ["Duplicate numeric prefixes detected:"]
        for prefix in sorted(duplicates):
            names = ", ".join(sorted(p.name for p in duplicates[prefix]))
            parts.append(f"- {prefix}: {names}")
        raise ValueError("\n".join(parts))

    return sorted(pdf_files, key=get_prefix_number)


def _get_pdf_page_count(pdf_path: Path) -> int:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to read PDF (corrupt or unsupported): {pdf_path}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            result = reader.decrypt("")  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Encrypted PDF is not supported: {pdf_path}") from exc
        if result == 0:
            raise ValueError(f"Encrypted PDF is not supported: {pdf_path}")

    try:
        return len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to read PDF pages: {pdf_path}") from exc


def _calculate_section_start_pages(
    pdf_files: list[Path],
    *,
    toc_pages: int,
    include_toc: bool,
    include_dividers: bool,
    progress_callback: Callable[[str], None] | None = None,
) -> Mapping[int, int]:
    current_page = toc_pages if include_toc else 0
    start_pages: dict[int, int] = {}

    for index, pdf_file in enumerate(pdf_files, start=1):
        if progress_callback:
            progress_callback(f"Counting pages {index}/{len(pdf_files)}: {pdf_file.name}")

        pdf_pages = _get_pdf_page_count(pdf_file)

        # The "section begins" at the divider page if dividers are enabled,
        # otherwise at the first page of the PDF itself.
        start_pages[index] = current_page + 1

        if include_dividers:
            current_page += 1

        current_page += pdf_pages

    return start_pages


def _render_toc_and_count_pages(
    pdf_files: list[Path],
    *,
    section_start_pages: Mapping[int, int] | None,
) -> tuple[bytes, int]:
    toc_buffer = create_toc_pdf(pdf_files, clean_title, section_start_pages=section_start_pages)
    toc_pages = len(PdfReader(toc_buffer).pages)
    data = toc_buffer.getvalue()
    return data, toc_pages


def merge_pdfs(
    input_dir: Path,
    output_file: Path | None = None,
    *,
    include_toc: bool = True,
    include_dividers: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> Path:
    pdf_files = get_ordered_pdf_files(input_dir)

    if output_file is None:
        # Default: write next to the input folder (commonly <project>/input -> <project>/output)
        output_dir = input_dir.parent / "output"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"merged_documents_final_{timestamp}.pdf"
    else:
        output_file.parent.mkdir(parents=True, exist_ok=True)

    merger = PdfMerger()
    current_page = 0

    if include_toc:
        if progress_callback:
            progress_callback("Building table of contents...")

        # Two-pass TOC generation:
        # 1) render to measure TOC page count (independent of page numbers),
        # 2) compute section start pages using the measured TOC page count,
        # 3) render final TOC including those start pages.
        toc_bytes_pass1, toc_pages_pass1 = _render_toc_and_count_pages(
            pdf_files,
            section_start_pages=None,
        )
        section_start_pages = _calculate_section_start_pages(
            pdf_files,
            toc_pages=toc_pages_pass1,
            include_toc=True,
            include_dividers=include_dividers,
            progress_callback=progress_callback,
        )
        toc_bytes_pass2, toc_pages_pass2 = _render_toc_and_count_pages(
            pdf_files,
            section_start_pages=section_start_pages,
        )

        # Extremely defensive: if TOC pagination changes (shouldn't), recompute once.
        if toc_pages_pass2 != toc_pages_pass1:
            section_start_pages = _calculate_section_start_pages(
                pdf_files,
                toc_pages=toc_pages_pass2,
                include_toc=True,
                include_dividers=include_dividers,
                progress_callback=progress_callback,
            )
            toc_bytes_pass2, toc_pages_pass2 = _render_toc_and_count_pages(
                pdf_files,
                section_start_pages=section_start_pages,
            )

        merger.append(BytesIO(toc_bytes_pass2))
        current_page += toc_pages_pass2

    for index, pdf_file in enumerate(pdf_files, start=1):
        title = clean_title(pdf_file)
        if progress_callback:
            progress_callback(f"Reading PDF {index}/{len(pdf_files)}: {pdf_file.name}")
        pdf_pages = _get_pdf_page_count(pdf_file)

        if include_dividers:
            divider_page_number = current_page + 1
            if progress_callback:
                progress_callback(f"Adding divider {index:02} (page {divider_page_number})")
            merger.append(create_section_pdf(index, title, divider_page_number))
            current_page += 1

        if progress_callback:
            progress_callback(f"Appending PDF {index}/{len(pdf_files)}: {pdf_file.name}")
        merger.append(str(pdf_file))
        current_page += pdf_pages

    merger.write(str(output_file))
    merger.close()

    print(f"Done: {output_file}")
    return output_file


if __name__ == "__main__":
    # CLI default: merge PDFs from ./input into ./output
    merge_pdfs(input_dir=Path.cwd() / "input")
