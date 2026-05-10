"""
migrate_to_body.py — Move non-dispatcher fields from frontmatter to the
markdown body.

Fields moved: license, compatibility, author, version, maturity, homepage, platforms.
These are not read by the dispatcher preloader. The agent reads the full
SKILL.md, so nothing is lost.

Usage:
    python scripts/migrate_to_body.py --file <path/to/SKILL.md>
    python scripts/migrate_to_body.py --file <path/to/SKILL.md> --dry-run
    python scripts/migrate_to_body.py --file <path/to/SKILL.md> --backup
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    MIGRATABLE_TOP_LEVEL, MIGRATABLE_META,
    extract_frontmatter, reassemble, read_file, write_file, emit,
)


def extract_and_migrate(raw_fm: str) -> tuple[str, dict[str, str]]:
    lines = raw_fm.split("\n")
    result = []
    extracted: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        top = re.match(r"^([\w-]+):\s*(.*)", stripped)
        if top:
            key, value = top.groups()
            if key in MIGRATABLE_TOP_LEVEL:
                extracted[key] = value.strip()
                i += 1
                while i < len(lines) and re.match(r"^\s+", lines[i]):
                    i += 1
                continue
        meta = re.match(r"^\s{2}([\w-]+):\s*(.*)", stripped)
        if meta:
            key, value = meta.groups()
            if key in MIGRATABLE_META:
                extracted[key] = value.strip().strip("\"'")
                i += 1
                continue
        result.append(line)
        i += 1
    return "\n".join(result), extracted


def build_info_line(extracted: dict[str, str]) -> str:
    parts = []
    for key in ["author", "version", "maturity", "license", "homepage", "platforms"]:
        if key in extracted:
            parts.append(f"**{key.capitalize()}:** {extracted[key]}")
    info = ""
    if parts:
        info += "> " + " | ".join(parts) + "  \n"
    if "compatibility" in extracted:
        info += f"> **Compatibility:** {extracted['compatibility']}\n"
    return info


def inject_info(body: str, info_line: str) -> str:
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^# ", line):
            lines.insert(i + 1, "")
            lines.insert(i + 2, info_line)
            return "\n".join(lines)
    return info_line + "\n" + body


def process(path, *, dry_run=False, backup=False):
    content = read_file(path)
    fm, body = extract_frontmatter(content)
    if fm is None:
        emit(f"SKIP: No frontmatter in {path}"); return
    new_fm, extracted = extract_and_migrate(fm)
    if not extracted:
        emit(f"SKIP: No migratable fields in {path}"); return
    info_line = build_info_line(extracted)
    new_body = inject_info(body, info_line)
    new_content = reassemble(new_fm, new_body)
    emit(f"{path}: {len(fm)} -> {len(new_fm)} chars (saved {len(fm) - len(new_fm)})")
    emit(f"  Migrated: {list(extracted.keys())}")
    if not dry_run:
        write_file(path, new_content, backup=backup)


def main():
    p = argparse.ArgumentParser(description="Move non-dispatcher fields to body.")
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true")
    args = p.parse_args()
    process(args.file, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
