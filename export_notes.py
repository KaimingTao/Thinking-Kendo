#!/usr/bin/env python3
"""Export Markdown notes to CSV, then build notes.json from that CSV."""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
import re
import subprocess

import markdown


ROOT = Path(__file__).resolve().parent
CSV_OUTPUT = ROOT / "notes.csv"
JSON_OUTPUT = ROOT / "notes.json"
EXCLUDED_DIRECTORIES = {".git", ".venv", "__pycache__"}
RAW_URL_PATTERN = re.compile(r"(?<!\]\()(https?://[^\s<>\"\]]+)")
PROTECTED_MARKDOWN_PATTERN = re.compile(
    r"(```[\s\S]*?```|`[^`]*`|!?\[[^\]]*\]\([^\n)]*\))"
)


def is_included_markdown(path: Path) -> bool:
    relative_path = path.relative_to(ROOT)
    return (
        path.is_file()
        and relative_path != Path("README.md")
        and not EXCLUDED_DIRECTORIES.intersection(relative_path.parts)
    )


def update_date(path: Path) -> str:
    """Return the latest Git commit time for a file, or mtime if it is untracked."""
    relative_path = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cI", "--", relative_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    git_date = result.stdout.strip()
    if git_date:
        return git_date
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


def linkify_bare_urls(content: str) -> str:
    """Turn standalone URLs into Markdown links without changing existing links."""

    def replacement(match: re.Match[str]) -> str:
        url = match.group(1)
        trailing = ""
        while url and url[-1] in ".,;:!?":
            trailing = url[-1] + trailing
            url = url[:-1]
        # A closing parenthesis is usually sentence punctuation unless balanced
        # by an opening parenthesis in the URL itself.
        while url.endswith(")") and url.count(")") > url.count("("):
            trailing = ")" + trailing
            url = url[:-1]
        return f"[{url}]({url}){trailing}"

    # Do not alter URLs in fenced or inline code, where they are literal text.
    parts = PROTECTED_MARKDOWN_PATTERN.split(content)
    return "".join(
        part
        if PROTECTED_MARKDOWN_PATTERN.fullmatch(part)
        else RAW_URL_PATTERN.sub(replacement, part)
        for part in parts
    )


def markdown_to_html(content: str) -> str:
    """Convert a note's Markdown to HTML suitable for the local notes page."""
    prepared_content = linkify_bare_urls(content)
    return markdown.markdown(prepared_content, extensions=["extra", "sane_lists", "nl2br"])


def existing_ids() -> tuple[dict[str, int], int]:
    """Load stable IDs from an earlier notes.csv, if one exists."""
    if not CSV_OUTPUT.exists():
        return {}, 0

    ids_by_path: dict[str, int] = {}
    maximum_id = 0
    with CSV_OUTPUT.open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            try:
                note_id = int(row["id"])
                relative_path = row["relative_path"]
            except (KeyError, TypeError, ValueError):
                continue
            ids_by_path[relative_path] = note_id
            maximum_id = max(maximum_id, note_id)
    return ids_by_path, maximum_id


def write_csv() -> int:
    """Scan project Markdown files and save their source data to notes.csv."""
    rows = []
    ids_by_path, maximum_id = existing_ids()
    markdown_files = (
        path
        for path in ROOT.rglob("*.md")
        if is_included_markdown(path)
    )
    # Keep the JSON (and therefore the page) in filesystem creation-date order.
    # Some platforms do not expose a birth time, so fall back to modification time.
    for path in sorted(
        markdown_files,
        key=lambda item: getattr(item.stat(), "st_birthtime", item.stat().st_mtime),
    ):
        relative_path = path.relative_to(ROOT).as_posix()
        note_id = ids_by_path.get(relative_path)
        if note_id is None:
            maximum_id += 1
            note_id = maximum_id
        content = path.read_text(encoding="utf-8")
        rows.append(
            {
                "id": note_id,
                "relative_path": relative_path,
                "stem_name": path.stem,
                "md_content": content,
                "update_date": update_date(path),
            }
        )

    fieldnames = ["id", "relative_path", "stem_name", "md_content", "update_date"]
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} Markdown files to {CSV_OUTPUT}")
    return len(rows)


def write_json_from_csv() -> int:
    """Read notes.csv and create the JSON consumed by index.html."""
    with CSV_OUTPUT.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    notes = [
        {
            "id": int(row["id"]),
            "relative_path": row["relative_path"],
            "filename": row["stem_name"],
            "content": row["md_content"],
            "html_content": markdown_to_html(row["md_content"]),
            "update_date": row["update_date"],
        }
        for row in rows
    ]
    JSON_OUTPUT.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(notes)} notes from {CSV_OUTPUT} to {JSON_OUTPUT}")
    return len(notes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export project notes to CSV and JSON")
    parser.add_argument(
        "--from-csv",
        action="store_true",
        help="skip scanning Markdown files and rebuild only notes.json from notes.csv",
    )
    args = parser.parse_args()

    if not args.from_csv:
        write_csv()
    write_json_from_csv()


if __name__ == "__main__":
    main()
