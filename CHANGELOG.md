# Changelog

All notable changes to skill-yaml-cleanup are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
