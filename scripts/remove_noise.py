"""
remove_noise.py — Strip empty, decorative, and external-tool fields from
SKILL.md frontmatter.

Usage:
    python scripts/remove_noise.py --file <path/to/SKILL.md>
    python scripts/remove_noise.py --file <path/to/SKILL.md> --dry-run
    python scripts/remove_noise.py --file <path/to/SKILL.md> --backup
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    NOISE_META_FIELDS, NOISE_TOP_LEVEL,
    extract_frontmatter, reassemble, read_file, write_file, emit,
)

REMOVE_IF_EMPTY = {"dispatcher-persistent-directories"}


def clean_noise(raw_fm: str) -> str:
    lines = raw_fm.split("\n")
    result = []
    skip_top = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        top = re.match(r"^([\w-]+):\s*(.*)", stripped)
        if top:
            key = top.group(1)
            if key in NOISE_TOP_LEVEL:
                skip_top = True; i += 1; continue
            else:
                skip_top = False
        if skip_top:
            i += 1; continue
        meta = re.match(r"^\s{2}([\w-]+):\s*(.*)", stripped)
        if meta:
            key, value = meta.group(1), meta.group(2).strip()
            if key in NOISE_META_FIELDS:
                i += 1
                while i < len(lines) and re.match(r"^    ", lines[i].rstrip()):
                    i += 1
                continue
            if key in REMOVE_IF_EMPTY and value == "":
                i += 1
                while i < len(lines) and re.match(r"^    ", lines[i].rstrip()):
                    i += 1
                continue
        result.append(line)
        i += 1
    return "\n".join(result)


def process(path, *, dry_run=False, backup=False):
    content = read_file(path)
    fm, body = extract_frontmatter(content)
    if fm is None:
        emit(f"SKIP: No frontmatter in {path}"); return
    new_fm = clean_noise(fm)
    new_content = reassemble(new_fm, body)
    emit(f"{path}: {len(fm)} -> {len(new_fm)} chars (saved {len(fm) - len(new_fm)})")
    if not dry_run:
        write_file(path, new_content, backup=backup)


def main():
    p = argparse.ArgumentParser(description="Strip noise fields from frontmatter.")
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true")
    args = p.parse_args()
    process(args.file, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
