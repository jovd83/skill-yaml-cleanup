"""
_common.py — Shared utilities for skill-yaml-cleanup scripts.

Provides robust frontmatter extraction that does NOT break on '---' horizontal
rules or code fences in the markdown body.  Also provides consistent file I/O,
backup handling, and structured output helpers.
"""

import json
import os
import re
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRONTMATTER_LIMIT = 1000

# Fields the dispatcher preloader reads — must stay in frontmatter.
DISPATCHER_FIELDS = {"name", "description", "metadata"}

# Non-dispatcher top-level fields safe to migrate to the body.
MIGRATABLE_TOP_LEVEL = {"license", "compatibility", "homepage", "platforms"}

# Non-dispatcher metadata-level fields safe to migrate to the body.
MIGRATABLE_META = {"author", "version", "maturity"}

# Fields that are noise (decorative, unused, or external-tool config).
NOISE_META_FIELDS = {"tags", "metadata-tags", "dispatcher-persistent-directories"}
NOISE_TOP_LEVEL = {"openclaw", "hermes"}

# Dispatcher metadata keys that are expected to be inline lists (CSV).
# Mirrors LIST_FIELDS in skill-dispatcher/scripts/build_registry.py — keep aligned.
DISPATCHER_LIST_FIELDS = {
    "dispatcher-capabilities",
    "dispatcher-accepted-intents",
    "dispatcher-input-artifacts",
    "dispatcher-output-artifacts",
    "dispatcher-stack-tags",
    "dispatcher-downstream-skills",
    "tags",
}


# ---------------------------------------------------------------------------
# Composable frontmatter transforms
# (Return (new_fm_text, report_dict) — never touch the file directly.)
# ---------------------------------------------------------------------------

def dedupe_metadata_blocks(fm_text: str) -> tuple[str, dict]:
    """Merge duplicate top-level keys and duplicate metadata: blocks.

    If a key appears more than once, values are merged and deduplicated.
    The metadata: block is consolidated into a single occurrence.
    Returns (new_fm_text, {"removed": int}) where removed counts merged lines.
    """
    lines = fm_text.splitlines()
    top_level: dict[str, list[str]] = {}
    metadata: dict[str, list[str]] = {}
    top_order: list[str] = []
    meta_order: list[str] = []
    in_metadata = False
    current_key: str | None = None
    current_section = top_level

    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            continue
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
        if current_key:
            v = stripped.strip()
            if v and v not in current_section.get(current_key, []):
                current_section.setdefault(current_key, []).append(v)

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

    new_fm = "\n".join(new_lines) + "\n"
    removed = len(lines) - len(new_fm.splitlines())
    return new_fm, {"removed": max(0, removed)}


def flatten_vertical_lists(
    fm_text: str,
    list_fields: set[str] | None = None,
) -> tuple[str, dict]:
    """Convert vertical YAML list items under known dispatcher keys to inline CSV.

    Before:
        dispatcher-capabilities:
          - foo
          - bar
    After:
        dispatcher-capabilities: foo, bar

    Returns (new_fm_text, {"flattened": [field_name, ...]}).
    """
    if list_fields is None:
        list_fields = DISPATCHER_LIST_FIELDS

    lines = fm_text.split("\n")
    result: list[str] = []
    flattened: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # Match a metadata key (2-space indented) with no inline value
        match = re.match(r"^(  [\w-]+:)\s*$", line.rstrip())
        if match:
            key_part = match.group(1)
            field_name = key_part.strip().rstrip(":")
            if field_name in list_fields:
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
                    flattened.append(field_name)
                    i = j
                    continue
        result.append(line)
        i += 1

    return "\n".join(result), {"flattened": flattened}


def strip_noise(fm_text: str) -> tuple[str, dict]:
    """Remove noise fields (tags, metadata-tags, empty dispatcher-persistent-directories, etc.).

    Returns (new_fm_text, {"stripped": [field_name, ...]}).
    """
    remove_if_empty = {"dispatcher-persistent-directories"}
    lines = fm_text.split("\n")
    result: list[str] = []
    stripped_fields: list[str] = []
    skip_top = False
    i = 0

    # Fields removed unconditionally vs only when empty
    unconditional_noise = NOISE_META_FIELDS - remove_if_empty

    while i < len(lines):
        line = lines[i]
        stripped_line = line.rstrip()
        top = re.match(r"^([\w-]+):\s*(.*)", stripped_line)
        if top:
            key = top.group(1)
            if key in NOISE_TOP_LEVEL:
                skip_top = True
                stripped_fields.append(key)
                i += 1
                continue
            else:
                skip_top = False
        if skip_top:
            i += 1
            continue
        meta = re.match(r"^\s{2}([\w-]+):\s*(.*)", stripped_line)
        if meta:
            key, value = meta.group(1), meta.group(2).strip()
            if key in remove_if_empty and value == "":
                stripped_fields.append(key)
                i += 1
                while i < len(lines) and re.match(r"^    ", lines[i].rstrip()):
                    i += 1
                continue
            if key in unconditional_noise:
                stripped_fields.append(key)
                i += 1
                while i < len(lines) and re.match(r"^    ", lines[i].rstrip()):
                    i += 1
                continue
        result.append(line)
        i += 1

    return "\n".join(result), {"stripped": stripped_fields}


def normalize(fm_text: str) -> tuple[str, dict]:
    """Run all safe in-memory normalizations on raw frontmatter text.

    Pipeline: dedupe → flatten vertical lists → strip noise.

    Returns (new_fm_text, report) where report contains:
        {
            "dedupe_removed": int,
            "flattened_fields": [str, ...],
            "noise_stripped": [str, ...],
            "oversized": bool,
            "char_count": int,
        }
    """
    fm, dedupe_report = dedupe_metadata_blocks(fm_text)
    fm, flatten_report = flatten_vertical_lists(fm)
    fm, noise_report = strip_noise(fm)

    char_count = len(fm.rstrip())
    report = {
        "dedupe_removed": dedupe_report["removed"],
        "flattened_fields": flatten_report["flattened"],
        "noise_stripped": noise_report["stripped"],
        "oversized": char_count > FRONTMATTER_LIMIT,
        "char_count": char_count,
    }
    return fm, report


# ---------------------------------------------------------------------------
# Frontmatter extraction (robust)
# ---------------------------------------------------------------------------

def extract_frontmatter(content: str) -> tuple[str | None, str]:
    """Extract YAML frontmatter from a SKILL.md file.

    Returns (frontmatter_text, body) where frontmatter_text is the raw text
    between the opening and closing '---' delimiters (excluding the delimiters
    themselves), or None if no valid frontmatter is found.

    Unlike a naive `content.split('---')`, this correctly handles '---'
    horizontal rules and code fences in the markdown body.
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing '---' — it must be the first occurrence of a line that
    # is exactly '---' (with optional trailing whitespace) after the opening.
    lines = content.split("\n")
    # Skip the opening '---' on line 0.
    closing_index = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            closing_index = i
            break

    if closing_index is None:
        return None, content

    fm_text = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1:])
    return fm_text, body


def reassemble(frontmatter: str, body: str) -> str:
    """Reassemble a SKILL.md from frontmatter text and body."""
    return f"---\n{frontmatter}\n---\n{body}"


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a file with UTF-8 encoding."""
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str, *, backup: bool = False) -> str | None:
    """Write content to a file.  Optionally create a .bak backup first.

    Returns the backup path if a backup was created, else None.
    """
    backup_path = None
    if backup and os.path.exists(path):
        backup_path = path + ".bak"
        shutil.copy2(path, backup_path)
    Path(path).write_text(content, encoding="utf-8")
    return backup_path


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(message: str, *, data: dict | None = None, as_json: bool = False):
    """Print a human-readable message or JSON object."""
    if as_json:
        payload = data or {}
        if "message" not in payload:
            payload["message"] = message
        print(json.dumps(payload, indent=2))
    else:
        print(message)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_skill_files(directory: str, specific_files: list[str] | None = None) -> list[str]:
    """Find all SKILL.md files in a directory tree.

    If specific_files is provided, resolve them relative to directory instead.
    Excludes hidden directories (starting with '.').
    """
    if specific_files:
        return [
            os.path.join(directory, f)
            for f in specific_files
            if os.path.exists(os.path.join(directory, f))
        ]

    paths = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "SKILL.md" in files:
            paths.append(os.path.join(root, "SKILL.md"))
    return sorted(paths)
