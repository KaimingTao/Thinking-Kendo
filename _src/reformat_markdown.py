#!/usr/bin/env python3
"""Conservative Markdown reformatter for prose-heavy notes.

This script is designed for small writing repos where readability matters more
than strict Markdown tooling conventions. It:

- trims trailing whitespace
- normalizes excessive blank lines
- keeps one blank line around headings and thematic breaks
- reflows plain prose paragraphs to a target width
- preserves fenced code blocks, block quotes, and list items as written

Usage:
  python3 reformat_markdown.py
  python3 reformat_markdown.py --check
  python3 reformat_markdown.py --width 72 docs notes
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path


DEFAULT_WIDTH = 88
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown"}


def is_markdown_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MARKDOWN_SUFFIXES


def iter_markdown_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            if is_markdown_file(path):
                files.append(path)
            continue
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if is_markdown_file(candidate):
                    files.append(candidate)
    deduped = sorted(dict.fromkeys(files))
    return deduped


def is_fence(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def is_heading(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}#{1,6}\s+\S", line))


def is_thematic_break(line: str) -> bool:
    stripped = line.strip()
    return stripped in {"---", "***", "___"}


def is_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-+*]|\d+[.)])\s+\S", line))


def is_block_quote(line: str) -> bool:
    return bool(re.match(r"^\s*>\s?", line))


def flush_paragraph(buffer: list[str], width: int, out: list[str]) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    if not text:
        buffer.clear()
        return
    wrapped = textwrap.fill(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    out.extend(wrapped.splitlines())
    buffer.clear()


def normalize_blank_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    blank_run = 0
    for line in lines:
        if line.strip():
            blank_run = 0
            normalized.append(line.rstrip())
            continue
        blank_run += 1
        if blank_run <= 1:
            normalized.append("")
    while normalized and normalized[-1] == "":
        normalized.pop()
    return normalized


def ensure_spacing(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        special = is_heading(line) or is_thematic_break(line)
        if special and out and out[-1] != "":
            out.append("")
        out.append(line)
        if special:
            out.append("")
    collapsed: list[str] = []
    blank_run = 0
    for line in out:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append(line)
        else:
            blank_run = 0
            collapsed.append(line)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return collapsed


def format_markdown(text: str, width: int) -> str:
    source_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    source_lines = normalize_blank_lines(source_lines)

    out: list[str] = []
    paragraph: list[str] = []
    in_fence = False

    for line in source_lines:
        stripped = line.strip()

        if is_fence(line):
            flush_paragraph(paragraph, width, out)
            out.append(line.rstrip())
            in_fence = not in_fence
            continue

        if in_fence:
            out.append(line.rstrip())
            continue

        if not stripped:
            flush_paragraph(paragraph, width, out)
            out.append("")
            continue

        if (
            is_heading(line)
            or is_thematic_break(line)
            or is_list_item(line)
            or is_block_quote(line)
        ):
            flush_paragraph(paragraph, width, out)
            out.append(line.rstrip())
            continue

        paragraph.append(line)

    flush_paragraph(paragraph, width, out)
    out = ensure_spacing(normalize_blank_lines(out))
    return "\n".join(out) + "\n"


def process_file(path: Path, width: int, check_only: bool) -> bool:
    original = path.read_text(encoding="utf-8")
    formatted = format_markdown(original, width)
    changed = formatted != original
    if changed and not check_only:
        path.write_text(formatted, encoding="utf-8")
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Markdown files or directories to process.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"Wrap prose paragraphs to this width. Default: {DEFAULT_WIDTH}.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files that would change without rewriting them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [Path(item) for item in args.paths]
    files = iter_markdown_files(paths)

    if not files:
        print("No Markdown files found.", file=sys.stderr)
        return 1

    changed_files: list[Path] = []
    for path in files:
        if process_file(path, width=args.width, check_only=args.check):
            changed_files.append(path)

    if args.check:
        if changed_files:
            for path in changed_files:
                print(path)
            print(f"{len(changed_files)} file(s) would be reformatted.")
            return 1
        print("All Markdown files already match the formatter.")
        return 0

    for path in changed_files:
        print(f"Reformatted {path}")
    if not changed_files:
        print("No changes needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
