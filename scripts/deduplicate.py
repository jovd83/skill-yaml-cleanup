"""
deduplicate.py — Merge duplicate top-level keys and duplicate metadata blocks
in SKILL.md frontmatter.

Usage:
    python scripts/deduplicate.py --file <path/to/SKILL.md>
    python scripts/deduplicate.py --file <path/to/SKILL.md> --dry-run
    python scripts/deduplicate.py --file <path/to/SKILL.md> --backup
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import extract_frontmatter, reassemble, read_file, write_file, emit


def deduplicate_frontmatter(raw_fm: str) -> str:
    """Merge duplicate top-level keys and duplicate metadata sub-keys.

    If a key appears multiple times, values are merged (deduplicated).
    The 'metadata:' block is consolidated into a single occurrence.
    """
    lines = raw_fm.splitlines()
    top_level: dict[str, list[str]] = {}
    metadata: dict[str, list[str]] = {}
    top_order: list[str] = []
    meta_order: list[str] = []
    in_metadata = False
    current_key = None
    current_section = top_level

    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            continue

        # Top-level key
        top_match = re.match(r"^([\w-]+):\s*(.*)", stripped)
        if top_match:
            key, value = top_match.groups()
            if key == "metadata":
                in_metadata = True
                current_section = metadata
                current_key = None
                continue
            else:
                in_metadata = False
                current_section = top_level
                current_key = key
                if key not in top_level:
                    top_level[key] = []
                    top_order.append(key)
                if value.strip() and value.strip() not in top_level[key]:
                    top_level[key].append(value.strip())
                continue

        # Metadata-level key (2-space indent)
        meta_match = re.match(r"^\s{2}([\w-]+):\s*(.*)", stripped)
        if meta_match and in_metadata:
            key, value = meta_match.groups()
            current_key = key
            if key not in metadata:
                metadata[key] = []
                meta_order.append(key)
            if value.strip() and value.strip() not in metadata[key]:
                metadata[key].append(value.strip())
            continue

        # Deeper content (list items, nested values)
        if current_key:
            v = stripped.strip()
            if v and v not in current_section.get(current_key, []):
                current_section.setdefault(current_key, []).append(v)

    # Reconstruct
    new_lines: list[str] = []
    for k in top_order:
        vals = top_level[k]
        if not vals:
            new_lines.append(f"{k}:")
        elif len(vals) == 1 and not vals[0].startswith("-"):
            new_lines.append(f"{k}: {vals[0]}")
        else:
            new_lines.append(f"{k}:")
            for v in vals:
                new_lines.append(f"  {v}" if v.startswith("-") else f"  - {v}")

    if metadata:
        new_lines.append("metadata:")
        for k in meta_order:
            vals = metadata[k]
            if not vals:
                new_lines.append(f"  {k}:")
            elif len(vals) == 1 and not vals[0].startswith("-"):
                new_lines.append(f"  {k}: {vals[0]}")
            else:
                new_lines.append(f"  {k}:")
                for v in vals:
                    new_lines.append(f"    {v}" if v.startswith("-") else f"    - {v}")

    return "\n".join(new_lines) + "\n"


def process(path: str, *, dry_run: bool = False, backup: bool = False):
    """Deduplicate frontmatter in a single file."""
    content = read_file(path)
    fm, body = extract_frontmatter(content)

    if fm is None:
        emit(f"SKIP: No frontmatter in {path}")
        return

    new_fm = deduplicate_frontmatter(fm)
    new_content = reassemble(new_fm, body)

    before = len(fm)
    after = len(new_fm)
    emit(f"{path}: {before} -> {after} chars (saved {before - after})")

    if not dry_run:
        write_file(path, new_content, backup=backup)


def main():
    parser = argparse.ArgumentParser(description="Remove duplicate metadata blocks in SKILL.md frontmatter.")
    parser.add_argument("--file", required=True, help="Path to SKILL.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--backup", action="store_true", help="Create a .bak backup before writing")
    args = parser.parse_args()
    process(args.file, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
