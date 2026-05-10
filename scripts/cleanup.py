"""
cleanup.py — Unified CLI entry point for skill-yaml-cleanup.

Runs the full pipeline: audit → analyze → (optional) apply optimizations.

Usage:
    python scripts/cleanup.py --dir <skills_directory>
    python scripts/cleanup.py --dir <skills_directory> --dry-run
    python scripts/cleanup.py --dir <skills_directory> --json
    python scripts/cleanup.py --dir <skills_directory> --apply --backup
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import FRONTMATTER_LIMIT, find_skill_files, read_file, extract_frontmatter
from audit import scan, print_report
from analyze import analyze


def main():
    parser = argparse.ArgumentParser(
        description="Unified skill YAML frontmatter cleanup pipeline."
    )
    parser.add_argument("--dir", required=True, help="Root skills directory")
    parser.add_argument("--limit", type=int, default=FRONTMATTER_LIMIT)
    parser.add_argument("--files", nargs="*", help="Specific files (relative to --dir)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--analyze", action="store_true", help="Run analysis on oversized files")
    parser.add_argument("--apply", action="store_true", help="Apply all safe optimizations")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    # Phase 1: Audit
    print("=" * 60)
    print("PHASE 1 — AUDIT")
    print("=" * 60)
    results = scan(args.dir, args.limit, args.files)
    print_report(results, args.limit, as_json=args.as_json)

    over = [r for r in results if r["excess"] > 0]
    if not over:
        print("All skills are clean. Nothing to do.")
        return

    # Phase 2: Analyze (if requested or applying)
    if args.analyze or args.apply:
        print("\n" + "=" * 60)
        print("PHASE 2 — ANALYZE")
        print("=" * 60)
        for r in over:
            path = os.path.join(args.dir, r["rel_path"])
            print(f"\n--- {r['rel_path']} ---")
            analyze(path, as_json=args.as_json)

    # Phase 3: Apply (if requested)
    if args.apply:
        print("\n" + "=" * 60)
        print("PHASE 3 — APPLY")
        print("=" * 60)
        from deduplicate import process as dedup
        from flatten import process as flat
        from remove_noise import process as noise
        from migrate_to_body import process as migrate

        for r in over:
            path = os.path.join(args.dir, r["rel_path"])
            print(f"\n--- Processing: {r['rel_path']} ---")
            dedup(path, dry_run=args.dry_run, backup=args.backup)
            flat(path, dry_run=args.dry_run, backup=False)
            noise(path, dry_run=args.dry_run, backup=False)
            migrate(path, dry_run=args.dry_run, backup=False)

        # Re-audit
        print("\n" + "=" * 60)
        print("PHASE 4 — VERIFY")
        print("=" * 60)
        results2 = scan(args.dir, args.limit, args.files)
        print_report(results2, args.limit, as_json=args.as_json)


if __name__ == "__main__":
    main()
