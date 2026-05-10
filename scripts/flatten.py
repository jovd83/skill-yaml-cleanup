"""
flatten.py — Convert vertical YAML lists inside the metadata section to
comma-separated inline values.

Before:
    dispatcher-capabilities:
      - foo
      - bar

After:
    dispatcher-capabilities: foo, bar

Usage:
    python scripts/flatten.py --file <path/to/SKILL.md>
    python scripts/flatten.py --file <path/to/SKILL.md> --dry-run
    python scripts/flatten.py --file <path/to/SKILL.md> --backup
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import extract_frontmatter, reassemble, read_file, write_file, emit


def flatten_frontmatter(raw_fm: str) -> str:
    """Convert vertical YAML lists under metadata keys to inline comma-separated values."""
    lines = raw_fm.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # Match a metadata key (2-space indented) with no inline value
        match = re.match(r"^(  [\w-]+:)\s*$", line.rstrip())
        if match:
            key_part = match.group(1)
            # Peek ahead for 4-space indented list items
            items: list[str] = []
            j = i + 1
            while j < len(lines):
                item_match = re.match(r"^    - (.+)", lines[j].rstrip())
                if item_match:
                    items.append(item_match.group(1).strip())
                    j += 1
                else:
                    break
            if items:
                result.append(f"{key_part} {', '.join(items)}")
                i = j
                continue
        result.append(line)
        i += 1

    return "\n".join(result)


def process(path: str, *, dry_run: bool = False, backup: bool = False):
    """Flatten vertical lists in a single file's frontmatter."""
    content = read_file(path)
    fm, body = extract_frontmatter(content)

    if fm is None:
        emit(f"SKIP: No frontmatter in {path}")
        return

    new_fm = flatten_frontmatter(fm)
    new_content = reassemble(new_fm, body)

    before = len(fm)
    after = len(new_fm)
    emit(f"{path}: {before} -> {after} chars (saved {before - after})")

    if not dry_run:
        write_file(path, new_content, backup=backup)


def main():
    parser = argparse.ArgumentParser(description="Flatten vertical YAML lists to inline values.")
    parser.add_argument("--file", required=True, help="Path to SKILL.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--backup", action="store_true", help="Create a .bak backup before writing")
    args = parser.parse_args()
    process(args.file, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
