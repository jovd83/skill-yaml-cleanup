# Changelog

All notable changes to skill-lint (formerly skill-yaml-cleanup) are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.0.0] — 2026-09-27

### Changed
- **BREAKING:** renamed from `skill-yaml-cleanup` to `skill-lint`. The skill is now a `/skill-lint` command (`disable-model-invocation: true`) that lints first and trims second.
- `migrate_to_body.py` and `analyze.py` no longer move `author` and `version` out of `metadata`: the library rule is that `metadata` carries them. `maturity` still moves.
- README rewritten to the skill-readme-standard layout. CI workflow renamed to `ci.yml`.

### Added
- `scripts/skill_lint.py`: checks frontmatter YAML, name format, name against folder, description length, field values, development-tree paths, model-run telemetry instructions, unknown keys, author/version in metadata, SKILL.md size, relative links, and optionally the README via skill-readme-standard's `check_readme.py`. Text or JSON output; exit codes 0/1/2; per-skill `.skill-lint.json`.
- `lint_skill()` as a library function, used by the manifest-driven skill sync as its lint gate.
- `action.yml`: a composite GitHub Action (`uses: jovd83/skill-lint@v3`) that runs the linter, installing PyYAML into a private venv only when the runner lacks it.
- `tests/test_skill_lint.py`: 18 tests, every sample skill built in a temporary folder.
- `validate_repo.py` and `validate_repo.ps1` now lint the repository itself.

## [2.0.0] — 2026-04-29

### Changed
- **BREAKING:** Rewrote all scripts to use robust frontmatter extraction (fixes `---` delimiter bug).
- Extracted shared utilities into `scripts/_common.py` — consistent parsing, backup, and output across all scripts.
- All scripts now accept `--backup` flag to create `.bak` files before writing.
- `audit.py` now accepts `--json` flag for structured output and exits non-zero when violations are found.
- `analyze.py` now returns structured recommendation dicts and accepts `--json`.

### Added
- `scripts/_common.py` — shared frontmatter parser, file I/O, discovery, and output helpers.
- `scripts/cleanup.py` — unified CLI entry point for the full audit→analyze→apply pipeline.
- `scripts/__init__.py` — package marker for importability.
- `tests/` — pytest test suite with fixtures covering all edge cases.
- `evals/evals.json` — expanded to 6 evaluation cases.
- `examples/` — before/after examples for documentation.
- `.gitignore` — standard Python exclusions.
- `CHANGELOG.md` — this file.
- `README.md` — GitHub-facing documentation.

### Fixed
- **Critical:** `content.split("---")` no longer breaks on `---` horizontal rules in the markdown body.
- Scripts no longer silently corrupt files that contain `---` separators in their body content.

### Removed
- Telemetry/logging section removed from mandatory skill header (moved to optional integration note).
- One-off `backlog-story-generator/dist/` rule removed from guardrails.

## [1.0.0] — 2026-04-29

### Added
- Initial release by jovd83.
- `audit.py`, `analyze.py`, `deduplicate.py`, `flatten.py`, `remove_noise.py`, `migrate_to_body.py`.
- SKILL.md with 5-phase workflow and approval gate.
