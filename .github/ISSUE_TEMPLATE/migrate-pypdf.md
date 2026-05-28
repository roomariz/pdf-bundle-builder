---
name: "Tech debt: migrate PyPDF2 → pypdf"
about: "Track future dependency migration (do not change v0.1.0 behavior)"
title: "Migrate from PyPDF2 to pypdf"
labels: ["tech debt"]
---

## Goal

Migrate from `PyPDF2` to `pypdf` in a future release, keeping behavior identical.

## Constraints

- Do **not** change merge logic, CLI behavior, or GUI behavior as part of this issue.
- Keep `v0.1.0` stable; do this in a later version with a clear changelog entry.

## Notes / Checklist

- Inventory current `PyPDF2` usage in `src/pdf_merger/`
- Replace imports/APIs with `pypdf` equivalents
- Re-run:
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run python scripts/generate_demo_assets.py`
- Confirm demo output PDF rendering stays the same (TOC, dividers, page numbers)
