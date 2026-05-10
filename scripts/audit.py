"""
audit.py — Scan a skills directory and report all SKILL.md files whose
YAML frontmatter exceeds the character limit.

Usage:
    python scripts/audit.py --dir <skills_directory>
    python scripts/audit.py --dir <skills_directory> --limit 1000
    python scripts/audit.py --dir <skills_directory> --files skill-a/SKILL.md skill-b/SKILL.md
    python scripts/audit.py --dir <skills_directory> --json
"""

import argparse
import os
import sys

# Allow running as a standalone script or as part of the package.
sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    FRONTMATTER_LIMIT,
    extract_frontmatter,
    find_skill_files,
    read_file,
    emit,
)


# ---------------------------------------------------------------------------
# Severity thresholds (character count of the frontmatter block)
# ---------------------------------------------------------------------------
CRITICAL_THRESHOLD = 1300
WARNING_THRESHOLD = 1100


def measure(path: str, limit: int) -> dict:
    """Measure frontmatter length for a single file."""
    content = read_file(path)
    fm, _ = extract_frontmatter(content)
    if fm is None:
        return {"path": path, "length": 0, "excess": 0, "severity": "no_frontmatter"}
    length = len(fm)
    excess = max(0, length - limit)
    if excess == 0:
        severity = "clean"
    elif length > CRITICAL_THRESHOLD:
        severity = "critical"
    elif length > WARNING_THRESHOLD:
        severity = "warning"
    else:
        severity = "tolerable"
    return {"path": path, "length": length, "excess": excess, "severity": severity}


def scan(directory: str, limit: int, specific_files=None) -> list[dict]:
    """Scan all SKILL.md files and return measurement results."""
    paths = find_skill_files(directory, specific_files)
    results = []
    for p in paths:
        try:
            r = measure(p, limit)
            r["rel_path"] = os.path.relpath(p, directory)
            results.append(r)
        except Exception as e:
            results.append({
                "path": p,
                "rel_path": os.path.relpath(p, directory),
                "length": 0,
                "excess": 0,
                "severity": "error",
                "error": str(e),
            })
    results.sort(key=lambda x: x["length"], reverse=True)
    return results


def print_report(results: list[dict], limit: int, *, as_json: bool = False):
    """Print a human-readable or JSON audit report."""
    over = [r for r in results if r["excess"] > 0]
    clean = [r for r in results if r["severity"] == "clean"]
    errors = [r for r in results if r["severity"] == "error"]

    if as_json:
        import json
        report = {
            "limit": limit,
            "total": len(results),
            "over_limit": len(over),
            "clean": len(clean),
            "errors": len(errors),
            "results": results,
        }
        print(json.dumps(report, indent=2))
        return

    print(f"Scanned: {len(results)} skills | Over limit: {len(over)} | Clean: {len(clean)}", end="")
    if errors:
        print(f" | Errors: {len(errors)}", end="")
    print("\n")

    if over:
        groups = {
            f"CRITICAL (>{CRITICAL_THRESHOLD})": [r for r in over if r["severity"] == "critical"],
            f"WARNING ({WARNING_THRESHOLD + 1}-{CRITICAL_THRESHOLD})": [r for r in over if r["severity"] == "warning"],
            f"TOLERABLE ({limit + 1}-{WARNING_THRESHOLD})": [r for r in over if r["severity"] == "tolerable"],
        }
        for label, group in groups.items():
            if not group:
                continue
            print(f"--- {label} ---")
            print(f"  {'Skill':<50} {'Length':>7}  {'Over by':>7}")
            for r in group:
                name = r["rel_path"].replace("\\SKILL.md", "").replace("/SKILL.md", "")
                print(f"  {name:<50} {r['length']:>7}  +{r['excess']:>6}")
            print()
    else:
        print("All skills are within the frontmatter limit.")

    if errors:
        print("--- ERRORS ---")
        for r in errors:
            print(f"  {r['rel_path']}: {r.get('error', 'unknown error')}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Audit SKILL.md frontmatter sizes against the character limit."
    )
    parser.add_argument("--dir", required=True, help="Root skills directory to scan")
    parser.add_argument("--limit", type=int, default=FRONTMATTER_LIMIT, help="Character limit (default: 1000)")
    parser.add_argument("--files", nargs="*", help="Specific files to audit (relative to --dir)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output results as JSON")
    args = parser.parse_args()

    results = scan(args.dir, args.limit, args.files)
    print_report(results, args.limit, as_json=args.as_json)

    # Exit with non-zero if any skills are over the limit.
    over = [r for r in results if r["excess"] > 0]
    sys.exit(1 if over else 0)


if __name__ == "__main__":
    main()
