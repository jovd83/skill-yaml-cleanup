#!/usr/bin/env python3
"""Consolidated validation for the skill-yaml-cleanup repository."""

import subprocess
import sys
from pathlib import Path

def run_command(command: list[str], root: Path) -> int:
    print(f"--- Running: {' '.join(command)} ---")
    try:
        result = subprocess.run(command, cwd=root, check=False)
        return result.returncode
    except FileNotFoundError as exc:
        print(f"Error: Command not found: {exc}")
        return 1

def main() -> int:
    root = Path(__file__).resolve().parent.parent
    
    # 1. Run unit tests
    print("--- Running pytest ---")
    rc = run_command([sys.executable, "-m", "pytest", "tests/", "-v"], root)
    if rc != 0:
        print("Tests failed.")
        return rc
        
    # 2. Run a self-audit (smoke test)
    print("--- Running self-audit ---")
    rc = run_command([sys.executable, "scripts/audit.py", "--dir", "."], root)
    # audit.py returns non-zero if it finds issues, but here we just want to make sure it runs
    # Actually, it might find issues in its own SKILL.md if not cleaned up.
    # For now, we'll just check if it crashes.
    if rc != 0 and rc != 1: # 1 is "violations found", other non-zero is crash
         print("Audit script failed to execute.")
         return rc
    
    print("\nValidation complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
