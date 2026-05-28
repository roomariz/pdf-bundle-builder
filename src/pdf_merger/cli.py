from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from pdf_merger.merge_pdfs import merge_pdfs


def _open_file(path: Path) -> None:
    if sys.platform.startswith("win"):
        subprocess.Popen(["cmd", "/c", "start", "", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-bundle-builder",
        description="Offline PDF bundle builder (TOC + dividers + deterministic ordering).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_parser = subparsers.add_parser("merge", help="Merge PDFs into one bundle.")
    merge_parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Folder containing PDFs to merge.",
    )
    merge_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PDF file path. Defaults to <input>/../output/merged_documents_final_<timestamp>.pdf",
    )
    merge_parser.add_argument(
        "--open",
        action="store_true",
        help="Open the merged PDF after creation.",
    )
    merge_parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Do not include a Table of Contents page.",
    )
    merge_parser.add_argument(
        "--no-dividers",
        action="store_true",
        help="Do not include divider pages.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "merge":
        merged = merge_pdfs(
            input_dir=args.input,
            output_file=args.output,
            include_toc=not args.no_toc,
            include_dividers=not args.no_dividers,
        )
        if args.open:
            _open_file(merged)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

