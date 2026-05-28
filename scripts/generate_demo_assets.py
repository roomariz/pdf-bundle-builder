from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SAMPLE_INPUT = REPO_ROOT / "sample-input"
DEMO_OUTPUT_DIR = REPO_ROOT / "docs" / "demo-output"
SCREENSHOTS_DIR = REPO_ROOT / "docs" / "screenshots"
SAMPLE_BUNDLE = DEMO_OUTPUT_DIR / "sample_bundle.pdf"

A4_POINTS = (595.275590551, 841.88976378)
SCALE = 2
PNG_SIZE = (int(A4_POINTS[0] * SCALE), int(A4_POINTS[1] * SCALE))


def _ensure_import_path() -> None:
    src = str(SRC_ROOT)
    if src not in sys.path:
        sys.path.insert(0, src)


def _ensure_sample_input() -> None:
    if SAMPLE_INPUT.exists():
        pdfs = sorted(SAMPLE_INPUT.glob("*.pdf"))
        if pdfs:
            print(f"Using existing safe sample PDFs from: {SAMPLE_INPUT}")
            return

    print("sample-input/ is missing or empty; generating safe sample PDFs.")
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from generate_sample_pdfs import main as generate_sample_pdfs

    generate_sample_pdfs()


def _merge_sample_bundle() -> None:
    from pdf_merger.merge_pdfs import merge_pdfs

    DEMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Merging sample PDFs into: {SAMPLE_BUNDLE}")
    merge_pdfs(input_dir=SAMPLE_INPUT, output_file=SAMPLE_BUNDLE)


def _run_checked(command: list[str]) -> bool:
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _render_with_pymupdf(pdf_path: Path, page_index: int, output_png: Path) -> bool:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return False

    try:
        doc = fitz.open(str(pdf_path))
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pix.save(str(output_png))
        doc.close()
    except Exception:
        return False

    return output_png.exists()


def _render_with_pypdfium2(pdf_path: Path, page_index: int, output_png: Path) -> bool:
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
    except ImportError:
        return False

    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        page = pdf[page_index]
        image = page.render(scale=2).to_pil()
        image.save(output_png)
        page.close()
        pdf.close()
    except Exception:
        return False

    return output_png.exists()


def _render_with_cli(pdf_path: Path, page_number: int, output_png: Path) -> bool:
    output_png.parent.mkdir(parents=True, exist_ok=True)

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "page"
            if _run_checked(
                [
                    pdftoppm,
                    "-png",
                    "-f",
                    str(page_number),
                    "-singlefile",
                    "-r",
                    "144",
                    str(pdf_path),
                    str(prefix),
                ]
            ):
                rendered = prefix.with_suffix(".png")
                if rendered.exists():
                    shutil.copyfile(rendered, output_png)
                    return True

    mutool = shutil.which("mutool")
    if mutool:
        with tempfile.TemporaryDirectory() as tmp:
            pattern = Path(tmp) / "page-%d.png"
            if _run_checked(
                [
                    mutool,
                    "draw",
                    "-r",
                    "144",
                    "-o",
                    str(pattern),
                    str(pdf_path),
                    str(page_number),
                ]
            ):
                rendered = Path(tmp) / f"page-{page_number}.png"
                if rendered.exists():
                    shutil.copyfile(rendered, output_png)
                    return True

    magick = shutil.which("magick") or shutil.which("convert")
    if magick:
        page_ref = f"{pdf_path}[{page_number - 1}]"
        if _run_checked([magick, "-density", "144", page_ref, str(output_png)]):
            return output_png.exists()

    return False


def _render_pdf_page_to_png(pdf_path: Path, page_number: int, output_png: Path) -> bool:
    page_index = page_number - 1
    return (
        _render_with_pymupdf(pdf_path, page_index, output_png)
        or _render_with_pypdfium2(pdf_path, page_index, output_png)
        or _render_with_cli(pdf_path, page_number, output_png)
    )


def _font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/{name}.ttf",
        f"/Library/Fonts/{name}.ttf",
        f"C:/Windows/Fonts/{name}.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = xy[0] - (bbox[2] - bbox[0]) // 2
    y = xy[1] - (bbox[3] - bbox[1]) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _draw_right(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (bbox[2] - bbox[0]), xy[1]), text, font=font, fill=fill)


def _pt(value: float) -> int:
    return int(value * SCALE)


def _fallback_toc_png(output_png: Path) -> None:
    from pdf_merger.merge_pdfs import clean_title, get_ordered_pdf_files

    pdf_files = get_ordered_pdf_files(SAMPLE_INPUT)
    reader_pages = [len(PdfReader(str(pdf)).pages) for pdf in pdf_files]

    start_pages: dict[int, int] = {}
    current_page = 1
    for index, page_count in enumerate(reader_pages, start=1):
        start_pages[index] = current_page + 1
        current_page += 1 + page_count

    image = Image.new("RGB", PNG_SIZE, "#FFFFFF")
    draw = ImageDraw.Draw(image)
    width, height = PNG_SIZE

    accent = "#C9784A"
    accent_light = "#E9C7B1"
    dark = "#1E1E1E"
    grey = "#7A7A7A"
    white = "#FFFFFF"

    _draw_centered(draw, (width // 2, _pt(60)), "DOCUMENT BUNDLE", _font("DejaVuSans-Bold", 24), accent)
    _draw_centered(
        draw,
        (width // 2, _pt(95)),
        "Table of Contents",
        _font("DejaVuSans-Bold", 56),
        dark,
    )
    draw.line((_pt(80), _pt(125), width - _pt(80), _pt(125)), fill=accent_light, width=2)

    y = _pt(175)
    for index, pdf_file in enumerate(pdf_files, start=1):
        title = clean_title(pdf_file)[:62]
        draw.ellipse((_pt(89), y - _pt(11), _pt(115), y + _pt(15)), fill=accent)
        _draw_centered(draw, (_pt(102), y + _pt(2)), f"{index:02}", _font("DejaVuSans-Bold", 18), white)
        draw.text((_pt(140), y - _pt(9)), title, font=_font("DejaVuSans-Bold", 24), fill=dark)
        _draw_right(
            draw,
            (width - _pt(90), y - _pt(9)),
            str(start_pages[index]),
            _font("DejaVuSans-Bold", 24),
            dark,
        )
        draw.line((_pt(90), y + _pt(18), width - _pt(90), y + _pt(18)), fill=accent_light, width=2)
        y += _pt(48)

    _draw_right(draw, (width - _pt(65), height - _pt(35)), "1", _font("DejaVuSans", 18), grey)
    image.save(output_png)


def _fallback_divider_png(output_png: Path) -> None:
    from pdf_merger.merge_pdfs import clean_title, get_ordered_pdf_files

    title = clean_title(get_ordered_pdf_files(SAMPLE_INPUT)[0])
    image = Image.new("RGB", PNG_SIZE, "#FFFFFF")
    draw = ImageDraw.Draw(image)
    width, height = PNG_SIZE

    _draw_centered(draw, (width // 2, height // 2 - _pt(45)), "Document", _font("DejaVuSans", 22), "#7A7A7A")
    _draw_centered(draw, (width // 2, height // 2 - _pt(5)), "01", _font("DejaVuSans-Bold", 84), "#C9784A")
    _draw_centered(draw, (width // 2, height // 2 + _pt(38)), title, _font("DejaVuSans", 30), "#1E1E1E")
    _draw_right(draw, (width - _pt(65), height - _pt(35)), "2", _font("DejaVuSans", 18), "#7A7A7A")
    image.save(output_png)


def _capture_toc_and_divider() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    toc_png = SCREENSHOTS_DIR / "toc.png"
    divider_png = SCREENSHOTS_DIR / "divider.png"

    toc_ok = _render_pdf_page_to_png(SAMPLE_BUNDLE, 1, toc_png)
    divider_ok = _render_pdf_page_to_png(SAMPLE_BUNDLE, 2, divider_png)

    if not toc_ok:
        print("No PDF rasterizer found for TOC; creating a safe Pillow-rendered TOC PNG.")
        _fallback_toc_png(toc_png)
    if not divider_ok:
        print("No PDF rasterizer found for divider; creating a safe Pillow-rendered divider PNG.")
        _fallback_divider_png(divider_png)

    print(f"Wrote: {toc_png}")
    print(f"Wrote: {divider_png}")


def _capture_gui() -> bool:
    if not os.environ.get("DISPLAY") and sys.platform.startswith("linux"):
        print("Skipping GUI screenshot: no DISPLAY is available.")
        return False

    try:
        from PIL import ImageGrab

        from pdf_merger.app import PDFBundleBuilderApp
    except Exception as error:
        print(f"Skipping GUI screenshot: GUI dependencies are unavailable ({error}).")
        return False

    app = None
    try:
        app = PDFBundleBuilderApp()
        app.input_folder = SAMPLE_INPUT
        app.folder_label.configure(text=f"Input folder: {SAMPLE_INPUT}")
        app.load_pdf_list()
        app.update_idletasks()
        app.update()
        app.lift()
        app.focus_force()
        time.sleep(0.5)
        app.update()

        x = app.winfo_rootx()
        y = app.winfo_rooty()
        w = app.winfo_width()
        h = app.winfo_height()
        if w <= 1 or h <= 1:
            print("Skipping GUI screenshot: app window did not report a usable size.")
            return False

        image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        image.save(SCREENSHOTS_DIR / "app.png")
    except Exception as error:
        print(f"Skipping GUI screenshot: capture failed ({error}).")
        return False
    finally:
        if app is not None:
            app.destroy()

    print(f"Wrote: {SCREENSHOTS_DIR / 'app.png'}")
    return True


def _print_gui_instructions() -> None:
    print()
    print("GUI screenshot was not captured in this environment.")
    print("To create it locally:")
    print("  1. Run: uv run python scripts/generate_demo_assets.py")
    print("  2. If docs/screenshots/app.png is still skipped, run the desktop app:")
    print("     uv run python -m pdf_merger.app")
    print("  3. Select sample-input/ and save a screenshot as docs/screenshots/app.png")


def main() -> int:
    _ensure_import_path()
    _ensure_sample_input()
    _merge_sample_bundle()
    _capture_toc_and_divider()
    if not _capture_gui():
        _print_gui_instructions()

    print()
    print("Demo asset generation complete.")
    print("All generated assets are based on sample-input/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
