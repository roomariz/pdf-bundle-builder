# PDF Bundle Builder (Offline)

Create a professional, privacy-first merged PDF evidence bundle offline:

- Styled table of contents
- Section divider pages
- Deterministic ordering via numeric filename prefixes
- Desktop GUI (CustomTkinter) and CLI workflow

Typical use cases: immigration/citizenship applications, legal evidence bundles, university/HR/tenancy document packs.

## Screenshots

Add these to `docs/` and link them here:

- Desktop app main window (with file list)
- Example TOC page
- Example section divider page

## How It Works

1. Put PDFs into `input/` and prefix filenames with numbers (e.g. `01.Passport.pdf`).
2. Run the CLI or desktop app.
3. The tool generates a TOC + divider pages and merges everything into one PDF.

## File Naming Rules

The tool sorts by the leading number in the filename:

```text
01.Passport.pdf
02.Language Certificate.pdf
03.Payslips.pdf
```

Original PDFs are never modified or renamed.

## Install

```powershell
uv sync
```

## Run (CLI)

```powershell
uv run pdf-bundle-builder merge --input /path/to/pdfs --output /path/to/output.pdf
```

Defaults:

- Includes TOC + divider pages
- Uses numeric filename prefixes for ordering
- If `--output` is omitted: writes to `<input>/../output/merged_documents_final_<timestamp>.pdf`

Optional flags:

- `--open` to open the merged PDF after creation
- `--no-toc` to omit the TOC
- `--no-dividers` to omit divider pages

## TOC Page Numbers

When the Table of Contents is enabled, each entry shows the *final* starting page number for that section in the merged PDF. This stays correct even when the TOC spans multiple pages and when PDFs have different page counts.

## Run (Desktop App)

```powershell
uv run python -m pdf_merger.app
```

The desktop app lets you pick any folder containing numbered PDFs and choose where to save the final PDF.

## Privacy

All processing happens locally. No uploads, no telemetry.

## Repository Safety

Never commit personal documents.

The repo’s `.gitignore` excludes:

- `input/`, `output/`
- `*.pdf`

## Tests

Install dev dependencies:

```powershell
uv sync --extra dev
```

Run tests:

```powershell
uv run pytest
```

## Roadmap (Suggested)

- Optional per-entry page counts in the TOC
- One-file executable releases (Windows/macOS/Linux)
