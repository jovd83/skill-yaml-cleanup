#!/usr/bin/env python3
"""
skill_lint.py — lint AgentSkill folders before they are installed, synced or published.

It checks what a harness needs to load a skill and pick it from its description, plus the
house rules of this skill library. Point it at a skill folder, a SKILL.md, or a whole tree.

Usage:
    python scripts/skill_lint.py <path> [<path> ...]
    python scripts/skill_lint.py <path> --readme       also run skill-readme-standard's check_readme.py
    python scripts/skill_lint.py <path> --json         machine-readable result on stdout
    python scripts/skill_lint.py <path> --strict       warnings fail the run too
    python scripts/skill_lint.py <path> --skip keys,author-version

Checks                 severity  what
    frontmatter        error     present, valid YAML, a mapping
    name               error     present, lowercase-hyphen, at most 64 characters
    name-folder        error     equal to the skill's folder name (sub-skills inside another skill
                                 are exempt unless a name is given)
    description        error     present, a string, at most 1,024 characters
    fields             error     `metadata` (when not empty) is a mapping, `context` is `fork`,
                                 flags are booleans
    dev-paths          error     no absolute paths into the development checkout (DEV_PATH_PATTERNS)
                                 in SKILL.md, references/, scripts/, agents/ or assets/;
                                 a warning in README.md
    telemetry          error     no model-run telemetry instructions in SKILL.md or references/
    keys               warning   top-level keys outside the Agent Skills and Claude Code set
    author-version     warning   `metadata` carries `author` and `version`
    size               warning   SKILL.md is under 500 lines
    links              warning   relative links in SKILL.md resolve
    readme             error     (--readme) the repository README passes check_readme.py

Per-skill settings: a `.skill-lint.json` next to SKILL.md or at the repository root, e.g.
    {"skip": ["telemetry"], "expect_name": "my-skill"}

Exit codes: 0 no failing findings, 1 findings fail the run, 2 bad invocation.
Requires PyYAML.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

try:
    import yaml
except ImportError:  # reported by main(); lint_skill() needs it
    yaml = None

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_LIMIT = 64
DESCRIPTION_LIMIT = 1024
LINE_LIMIT = 500

KNOWN_KEYS = {
    # Agent Skills specification
    "name", "description", "license", "compatibility", "metadata", "allowed-tools",
    # Claude Code
    "argument-hint", "disable-model-invocation", "user-invocable", "model", "effort", "context", "agent",
    "hooks", "paths", "shell", "when_to_use",
    # older skills in this library; `metadata.author` / `metadata.version` is the rule now
    "author", "version",
}
BOOLEAN_KEYS = ("disable-model-invocation", "user-invocable")

# Absolute paths into the author's development checkout. The second pattern is split so that
# this file, which lives in scripts/, never matches itself.
DEV_PATH_PATTERNS = [
    re.compile(r"\b[a-z]:[\\/]+projects[\\/]+skills\b", re.I),
    re.compile(r"(?<![\w.])/c/" + r"projects/skills\b", re.I),
]
DEV_PATH_DIRS = ("references", "scripts", "agents", "assets")

# Instructions that make the model log its own skill usage. Usage is logged by harness hooks.
TELEMETRY_PATTERNS = [
    re.compile(r"CRITICAL TELEMETRY", re.I),
    re.compile(r"\blog-dispatch\b"),
    re.compile(r"\bdispatch_logger\b"),
]
TELEMETRY_DIRS = ("references",)
# "Do not run log-dispatch ..." repeats the rule instead of breaking it.
NEGATION_RE = re.compile(r"\b(?:do not|don't|never|no longer|must not|should not)\b", re.I)

TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".psm1", ".sh", ".bat", ".cmd",
                 ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".html", ".css", ".xml", ".csv"}
MAX_SCAN_BYTES = 1_000_000
SKIP_SCAN_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv"}

# Folders that never hold an installable skill when a tree is walked.
PRUNE_DIRS = {"node_modules", "__pycache__", "fixtures", "tests", "test", "examples", "templates", "assets",
              "sandbox", "dist", "build", "generated", "dry-run", "archived", "backups", "evals",
              "test-results", "playwright-report", "venv"}

FRONTMATTER_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^(```|~~~)")

CONFIG_NAME = ".skill-lint.json"


@dataclass
class Finding:
    path: str
    check: str
    severity: str  # "error" | "warning"
    message: str
    line: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def repo_root(start: Path) -> Path | None:
    """Nearest ancestor (or start itself) that holds a .git entry."""
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return None


def load_config(skill_dir: Path) -> dict:
    """Merge .skill-lint.json from the repository root and the skill folder (the skill folder wins)."""
    merged: dict = {}
    root = repo_root(skill_dir)
    for folder in ([root] if root and root != skill_dir else []) + [skill_dir]:
        cfg = folder / CONFIG_NAME
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            merged["skip"] = sorted(set(merged.get("skip", [])) | set(data.get("skip", [])))
            if "expect_name" in data and folder == skill_dir:
                merged["expect_name"] = data["expect_name"]
    return merged


def is_nested(skill_dir: Path, max_levels: int = 6) -> bool:
    """True for a sub-skill: a folder above it (within the repository) holds a SKILL.md too.

    Harnesses load top-level skill folders only, so a sub-skill's name is an identifier inside
    its parent skill and need not match its folder."""
    root = repo_root(skill_dir)
    for level, parent in enumerate(skill_dir.parents):
        if level >= max_levels:
            break
        if (parent / "SKILL.md").is_file():
            return True
        if root and parent == root:
            break
    return False


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def blank_code_fences(text: str) -> str:
    """Replace fenced code blocks with empty lines so line numbers stay correct."""
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out.append("")
        else:
            out.append("" if in_fence else line)
    return "\n".join(out)


def text_files(folder: Path):
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_SCAN_DIRS]
        for name in files:
            p = Path(root) / name
            if p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size <= MAX_SCAN_BYTES:
                yield p


def scan(path: Path, patterns, skip_negated: bool = False) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    for pattern in patterns:
        for m in pattern.finditer(text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            if skip_negated and NEGATION_RE.search(text[line_start:m.start()]):
                continue
            hits.append((line_of(text, m.start()), m.group(0)))
    return sorted(set(hits))


def discover(path: Path) -> list[Path]:
    """SKILL.md files under path: the file itself, or every skill in a folder tree."""
    if path.is_file():
        return [path] if path.name == "SKILL.md" else []
    found = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs
                         if not (d.startswith(".") or d in PRUNE_DIRS or d.endswith("-workspace")))
        if "SKILL.md" in files:
            found.append(Path(root) / "SKILL.md")
    return found


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def lint_skill(skill_md: Path, expect_name: str | None = None, skip=(), display_base: Path | None = None
               ) -> list[Finding]:
    """Lint one SKILL.md and the folder around it. Returns every finding; nothing is written."""
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    skill_md = Path(os.path.abspath(skill_md))  # "." has no folder name; abspath keeps junction paths as given
    skill_dir = skill_md.parent
    cfg = load_config(skill_dir)
    skip = set(skip) | set(cfg.get("skip", []))
    explicit_name = bool(expect_name or cfg.get("expect_name"))
    expect_name = expect_name or cfg.get("expect_name") or skill_dir.name
    base = display_base or skill_dir.parent
    findings: list[Finding] = []

    def rel(p: Path) -> str:
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            return p.as_posix()

    def add(check, severity, message, line=None, path=skill_md):
        if check not in skip:
            findings.append(Finding(rel(path), check, severity, message, line))

    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        add("frontmatter", "error", "SKILL.md is not valid UTF-8")
        return findings

    data = None
    body_start = 0
    m = FRONTMATTER_RE.match(text)
    if not m:
        add("frontmatter", "error", "no YAML frontmatter block (--- ... ---) at the top of the file", 1)
    else:
        body_start = m.end()
        try:
            data = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            reason = getattr(exc, "problem", None) or str(exc).splitlines()[0]
            add("frontmatter", "error", f"frontmatter is not valid YAML: {reason}"
                + (" (quote values that contain ': ')" if "mapping values" in reason else ""),
                mark.line + 2 if mark else None)
        if data is not None and not isinstance(data, dict):
            add("frontmatter", "error", "frontmatter is not a key/value mapping", 2)
            data = None
        elif m and data is None and not any(f.check == "frontmatter" for f in findings):
            add("frontmatter", "error", "frontmatter is empty", 2)

    body = text[body_start:]
    body_line0 = line_of(text, body_start) - 1

    if isinstance(data, dict):
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            add("name", "error", "missing `name`")
        else:
            if not NAME_RE.match(name) or len(name) > NAME_LIMIT:
                add("name", "error", f"`{name}` must be lowercase letters, digits and single hyphens, "
                                     f"at most {NAME_LIMIT} characters")
            if name != expect_name and (explicit_name or not is_nested(skill_dir)):
                add("name-folder", "error", f"`{name}` does not match the folder name `{expect_name}`")

        desc = data.get("description")
        if not isinstance(desc, str) or not desc.strip():
            add("description", "error", "missing `description`; it is what the harness matches requests against")
        else:
            if len(desc) > DESCRIPTION_LIMIT:
                add("description", "error", f"description is {len(desc):,} characters; the limit is "
                                            f"{DESCRIPTION_LIMIT:,}")
            if re.search(r"<[A-Za-z/!]", desc):
                add("description", "warning", "description contains `<`; some platforms reject XML-like tags")

        if data.get("metadata") is not None and not isinstance(data["metadata"], dict):
            add("fields", "error", "`metadata` must be a key/value mapping")
        ctx = data.get("context")
        if ctx is not None and ctx != "fork":
            add("fields", "error", f"`context: {ctx}` is not supported; the only value is `fork`")
        if "agent" in data and ctx != "fork":
            add("fields", "warning", "`agent` only takes effect together with `context: fork`")
        for key in BOOLEAN_KEYS:
            if key in data and not isinstance(data[key], bool):
                add("fields", "error", f"`{key}` must be true or false, not {data[key]!r}")

        unknown = sorted(set(data) - KNOWN_KEYS)
        if unknown:
            add("keys", "warning", "unknown top-level keys: " + ", ".join(unknown)
                + "; custom fields belong under `metadata`")

        meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        missing = [k for k in ("author", "version") if not meta.get(k)]
        if missing:
            elsewhere = [k for k in missing if data.get(k) or re.search(rf"\*\*{k}:\*\*", body, re.I)]
            note = f" (found only outside metadata: {', '.join(elsewhere)})" if elsewhere else ""
            add("author-version", "warning", f"`metadata` has no {' or '.join(missing)}{note}")

    n_lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    if n_lines > LINE_LIMIT:
        add("size", "warning", f"SKILL.md is {n_lines} lines; keep it under {LINE_LIMIT} and move detail "
                               "into references/")

    for m_link in LINK_RE.finditer(blank_code_fences(body)):
        target = m_link.group(1).strip("<>")
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|/|\$|\{)", target, re.I):
            continue
        target_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if target_path and not (skill_dir / target_path).exists():
            add("links", "warning", f"link target `{target}` does not exist",
                body_line0 + line_of(body, m_link.start()))

    dev_files = [skill_md] + [p for d in DEV_PATH_DIRS if (skill_dir / d).is_dir()
                              for p in text_files(skill_dir / d)]
    for p in dev_files:
        for line, hit in scan(p, DEV_PATH_PATTERNS):
            add("dev-paths", "error", f"development-tree path `{hit}`; installed copies cannot reach it", line, p)
    readme = skill_dir / "README.md"
    if readme.is_file():
        for line, hit in scan(readme, DEV_PATH_PATTERNS):
            add("dev-paths", "warning", f"development-tree path `{hit}` in the README", line, readme)

    tele_files = [skill_md] + [p for d in TELEMETRY_DIRS if (skill_dir / d).is_dir()
                               for p in text_files(skill_dir / d)]
    for p in tele_files:
        for line, hit in scan(p, TELEMETRY_PATTERNS, skip_negated=True):
            add("telemetry", "error", f"model-run telemetry instruction `{hit}`; usage is logged by harness hooks",
                line, p)

    return findings


def find_readme_checker(explicit: str | None) -> Path | None:
    here = Path(__file__).resolve().parents[1]          # this skill's folder
    candidates = [explicit, os.environ.get("SKILL_README_CHECKER"),
                  here.parent / "skill-readme-standard" / "scripts" / "check_readme.py",
                  here.parent / "skill-readme-standard" / "skill-readme-standard" / "scripts" / "check_readme.py",
                  Path.home() / ".agents" / "skills" / "skill-readme-standard" / "scripts" / "check_readme.py"]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


def lint_readme(root: Path, checker: Path, display_base: Path) -> list[Finding]:
    """Run check_readme.py on a repository root and turn its [FAIL] lines into findings."""
    try:
        path = (root / "README.md").relative_to(display_base).as_posix()
    except ValueError:
        path = (root / "README.md").as_posix()
    proc = subprocess.run([sys.executable, str(checker), str(root)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode == 0:
        return []
    if proc.returncode != 1:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return [Finding(path, "readme", "error", "check_readme.py could not run: "
                        + (detail[-1] if detail else f"exit {proc.returncode}"))]
    findings, lines = [], proc.stdout.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("[FAIL]"):
            label = line.strip()[len("[FAIL]"):].strip()
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            detail = nxt if nxt and not nxt.startswith("[") else ""
            findings.append(Finding(path, "readme", "error", label + (f": {detail}" if detail else "")))
    return findings or [Finding(path, "readme", "error", "check_readme.py reported a failure")]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Lint AgentSkill folders (see the module docstring for the checks).")
    ap.add_argument("paths", nargs="+", help="skill folder, SKILL.md, or a tree of skills")
    ap.add_argument("--expect-name", help="expected `name` (only with a single skill); default: the folder name")
    ap.add_argument("--skip", action="append", default=[], help="check ids to skip, comma-separated; repeatable")
    ap.add_argument("--readme", action="store_true", help="also run check_readme.py on each repository root")
    ap.add_argument("--readme-checker", help="path to skill-readme-standard's check_readme.py")
    ap.add_argument("--strict", action="store_true", help="warnings fail the run too")
    ap.add_argument("--quiet", action="store_true", help="print errors only")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)

    if yaml is None:
        print("skill-lint: PyYAML is required (pip install pyyaml)", file=sys.stderr)
        return 2
    skip = {s.strip() for chunk in args.skip for s in chunk.split(",") if s.strip()}

    skills: list[tuple[Path, Path]] = []
    for raw in args.paths:
        p = Path(os.path.abspath(Path(raw).expanduser()))
        if not p.exists():
            print(f"skill-lint: {raw} does not exist", file=sys.stderr)
            return 2
        base = p.parent if p.is_file() else p
        found = discover(p)
        if not found:
            print(f"skill-lint: no SKILL.md under {raw}", file=sys.stderr)
            return 2
        skills += [(s, base.parent if s.parent == base else base) for s in found]
    if args.expect_name and len(skills) != 1:
        print("skill-lint: --expect-name needs exactly one skill", file=sys.stderr)
        return 2

    checker = None
    if args.readme:
        checker = find_readme_checker(args.readme_checker)
        if not checker:
            print("skill-lint: check_readme.py not found; pass --readme-checker or set SKILL_README_CHECKER",
                  file=sys.stderr)
            return 2

    findings: list[Finding] = []
    readme_roots: set[Path] = set()
    for skill_md, base in skills:
        try:
            findings += lint_skill(skill_md, args.expect_name, skip, base)
        except json.JSONDecodeError as exc:
            print(f"skill-lint: bad {CONFIG_NAME} near {skill_md}: {exc}", file=sys.stderr)
            return 2
        if checker and "readme" not in skip:
            root = repo_root(skill_md.parent) or skill_md.parent
            if root not in readme_roots and (root / "README.md").is_file():
                readme_roots.add(root)
                findings += lint_readme(root, checker, base)

    errors = sum(f.severity == "error" for f in findings)
    warnings = len(findings) - errors
    failed = errors > 0 or (args.strict and warnings > 0)

    if args.json:
        print(json.dumps({"skills": len(skills), "errors": errors, "warnings": warnings, "failed": failed,
                          "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        order = {"error": 0, "warning": 1}
        for f in sorted(findings, key=lambda f: (f.path, order[f.severity], f.line or 0)):
            if args.quiet and f.severity != "error":
                continue
            where = f"{f.path}:{f.line}" if f.line else f.path
            print(f"{'ERROR' if f.severity == 'error' else 'WARN '}  {where}  [{f.check}] {f.message}")
        print(f"\nskill-lint: {len(skills)} skill(s), {errors} error(s), {warnings} warning(s)"
              + (" — failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
