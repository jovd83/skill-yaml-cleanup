"""
analyze.py — Analyze a single SKILL.md and recommend which optimizations to
apply to bring its frontmatter under the character limit.

Usage:
    python scripts/analyze.py --file <path/to/SKILL.md>
    python scripts/analyze.py --file <path/to/SKILL.md> --json
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    FRONTMATTER_LIMIT,
    MIGRATABLE_TOP_LEVEL,
    MIGRATABLE_META,
    NOISE_META_FIELDS,
    NOISE_TOP_LEVEL,
    extract_frontmatter,
    read_file,
)


# ---------------------------------------------------------------------------
# Analysis checks
# ---------------------------------------------------------------------------

def check_duplicates(fm: str) -> list[str]:
    """Find duplicate top-level keys (e.g. two 'metadata:' blocks)."""
    keys = re.findall(r"^([\w-]+):", fm, re.MULTILINE)
    seen: set[str] = set()
    dupes: list[str] = []
    for k in keys:
        if k in seen and k not in dupes:
            dupes.append(k)
        seen.add(k)
    return dupes


def check_vertical_lists(fm: str) -> int:
    """Count vertical YAML list items in the metadata section."""
    return len(re.findall(r"^\s{4}- ", fm, re.MULTILINE))


def check_noise_fields(fm: str) -> list[str]:
    """Find noise/decorative fields in frontmatter."""
    found: set[str] = set()
    for field in NOISE_META_FIELDS:
        if re.search(rf"^\s{{2}}{re.escape(field)}:", fm, re.MULTILINE):
            found.add(field)
    for field in NOISE_TOP_LEVEL:
        if re.search(rf"^{re.escape(field)}:", fm, re.MULTILINE):
            found.add(field)
    return sorted(found)


def check_migratable_fields(fm: str) -> list[str]:
    """Find non-dispatcher fields that can move to the body."""
    found: list[str] = []
    for field in MIGRATABLE_TOP_LEVEL:
        if re.search(rf"^{re.escape(field)}:", fm, re.MULTILINE):
            found.append(field)
    for field in MIGRATABLE_META:
        if re.search(rf"^\s{{2}}{re.escape(field)}:", fm, re.MULTILINE):
            found.append(field)
    return found


def get_description_length(fm: str) -> int:
    """Get the length of the description field value."""
    match = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", fm, re.MULTILINE)
    return len(match.group(1)) if match else 0


def estimate_field_savings(fm: str, fields: list[str]) -> int:
    """Estimate character savings from removing specific fields."""
    total = 0
    for f in fields:
        # Try metadata-level first, then top-level
        match = re.search(rf"^\s*{re.escape(f)}:.*", fm, re.MULTILINE)
        if match:
            total += len(match.group()) + 1  # +1 for newline
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze(path: str, *, as_json: bool = False) -> dict:
    """Run all analyses on a single file and return a recommendations dict."""
    content = read_file(path)
    fm, _ = extract_frontmatter(content)

    if fm is None:
        msg = f"No frontmatter found in {path}"
        if as_json:
            print(json.dumps({"error": msg}))
        else:
            print(msg)
        return {"error": msg}

    length = len(fm)
    excess = length - FRONTMATTER_LIMIT

    recommendations: list[dict] = []
    total_savings = 0

    # 1. Duplicates
    dupes = check_duplicates(fm)
    if dupes:
        saving = 300  # conservative estimate
        recommendations.append({
            "id": 1,
            "action": "deduplicate",
            "detail": f"Duplicate keys: {dupes}",
            "estimated_saving": saving,
        })
        total_savings += saving

    # 2. Vertical lists
    list_items = check_vertical_lists(fm)
    if list_items > 0:
        saving = list_items * 3
        recommendations.append({
            "id": 2,
            "action": "flatten",
            "detail": f"{list_items} vertical list items",
            "estimated_saving": saving,
        })
        total_savings += saving

    # 3. Noise fields
    noise = check_noise_fields(fm)
    if noise:
        saving = estimate_field_savings(fm, noise)
        recommendations.append({
            "id": 3,
            "action": "remove_noise",
            "detail": f"Noise fields: {noise}",
            "estimated_saving": saving,
        })
        total_savings += saving

    # 4. Migratable fields
    migratable = check_migratable_fields(fm)
    if migratable:
        saving = estimate_field_savings(fm, migratable)
        recommendations.append({
            "id": 4,
            "action": "migrate_to_body",
            "detail": f"Non-dispatcher fields: {migratable}",
            "estimated_saving": saving,
        })
        total_savings += saving

    # 5. Description trim (last resort)
    desc_len = get_description_length(fm)
    if desc_len > 300:
        saving = desc_len - 200
        recommendations.append({
            "id": 5,
            "action": "description_trim",
            "detail": f"Description is {desc_len} chars; target ~200",
            "estimated_saving": saving,
        })
        total_savings += saving

    result = {
        "file": path,
        "frontmatter_length": length,
        "limit": FRONTMATTER_LIMIT,
        "excess": excess,
        "status": "over" if excess > 0 else "clean",
        "recommendations": recommendations,
        "estimated_total_savings": total_savings,
        "estimated_result": length - total_savings,
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"File: {path}")
        print(f"Frontmatter: {length} chars | Limit: {FRONTMATTER_LIMIT} | {'Over by ' + str(excess) if excess > 0 else 'CLEAN'}\n")

        if excess <= 0:
            print("No optimization needed.")
            return result

        print("Recommended optimizations:")
        for rec in recommendations:
            label = rec["action"].upper().replace("_", " ")
            print(f"  [{rec['id']}] {label:<20} — {rec['detail']}  (~{rec['estimated_saving']} chars)")

        est = result["estimated_result"]
        label = "CLEAN" if est <= FRONTMATTER_LIMIT else f"still {est - FRONTMATTER_LIMIT} over"
        print(f"\nEstimated total savings: ~{total_savings} chars")
        print(f"Estimated result: ~{est} chars ({label})")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a SKILL.md and recommend frontmatter optimizations."
    )
    parser.add_argument("--file", required=True, help="Path to SKILL.md")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()
    analyze(args.file, as_json=args.as_json)


if __name__ == "__main__":
    main()
