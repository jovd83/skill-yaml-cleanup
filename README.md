# skill-yaml-cleanup

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![GitHub Repo Size](https://img.shields.io/github/repo-size/jovd83/skill-yaml-cleanup)
![GitHub last commit](https://img.shields.io/github/last-commit/jovd83/skill-yaml-cleanup)

**Audit and optimize YAML frontmatter in AgentSkill `SKILL.md` files.**

Many agent platforms impose a hard character limit on YAML frontmatter (typically **1,000 characters**). Exceeding this limit causes preloading failures and context bloat. This skill finds oversized frontmatter, proposes targeted optimizations, and — with explicit user approval — applies them.

## Quick Start

```bash
# Audit all skills in a directory
python scripts/audit.py --dir ~/.agents/skills

# Analyze a specific oversized skill
python scripts/analyze.py --file ~/.agents/skills/my-skill/SKILL.md

# Full pipeline (audit → analyze → apply with backups)
python scripts/cleanup.py --dir ~/.agents/skills --analyze --apply --backup
```

## What It Does

| Optimization       | Description                                            | Typical Saving |
|:-------------------|:-------------------------------------------------------|:--------------:|
| **Deduplication**  | Merge duplicate `metadata:` blocks                     | 200–500 chars  |
| **Flattening**     | Convert vertical YAML lists to inline values           | 20–80 chars    |
| **Noise removal**  | Strip `tags:`, `metadata-tags:`, empty fields, external configs | 50–200 chars |
| **Field migration**| Move `license`, `author`, `version`, etc. to the body  | 50–270 chars   |
| **Description trim**| Shorten descriptions over 300 chars (last resort)     | 50–180 chars   |

## Repository Structure

```
skill-yaml-cleanup/
├── SKILL.md              # Agent skill definition (install this)
├── README.md             # This file
├── CHANGELOG.md          # Version history
├── .gitignore
├── scripts/
│   ├── _common.py        # Shared utilities (frontmatter parsing, I/O)
│   ├── cleanup.py        # Unified CLI entry point
│   ├── audit.py          # Scan and report oversized frontmatter
│   ├── analyze.py        # Recommend optimizations for a file
│   ├── deduplicate.py    # Merge duplicate metadata blocks
│   ├── flatten.py        # Convert vertical lists to inline
│   ├── remove_noise.py   # Strip decorative/external fields
│   └── migrate_to_body.py# Move non-dispatcher fields to body
├── tests/
│   ├── fixtures/         # Sample SKILL.md files for testing
│   ├── test_common.py    # Unit tests for shared module
│   └── test_scripts.py   # Integration tests for all scripts
└── evals/
    └── evals.json        # Evaluation cases for skill triggering
```

## Installation

Copy or symlink the `SKILL.md` and `scripts/` directory into your agent's skill registry:

```bash
# Example for ~/.agents/skills/
cp -r . ~/.agents/skills/skill-yaml-cleanup/
```

### Requirements

- Python 3.10+
- No external dependencies (stdlib only)

## Safety Model

**All file modifications require explicit user approval.** The skill enforces a mandatory approval gate between analysis and application. Scripts support `--dry-run` for preview and `--backup` for creating `.bak` files before writing.

## JSON Output

All major scripts support `--json` for structured output, enabling automation and CI integration:

```bash
python scripts/audit.py --dir ~/.agents/skills --json
python scripts/analyze.py --file path/to/SKILL.md --json
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for any new functionality
4. Run `pytest tests/ -v` to verify
5. Submit a pull request

## License

MIT

## Author

jovd83

---

## What changed — 2026-05-01 initiative

Three new composable helpers added to `scripts/_common.py` for use by `skill-dispatcher/scripts/build_registry.py` and any other consumer:

| Helper | Purpose |
|:-------|:--------|
| `dedupe_metadata_blocks(fm)` | Merge duplicate `metadata:` blocks in frontmatter |
| `flatten_vertical_lists(fm, list_fields)` | Convert vertical `- item` YAML lists to inline CSV |
| `strip_noise(fm)` | Remove decorative/noise fields (`tags`, `metadata-tags`, empty fields) |
| `normalize(fm)` | Pipeline combining all three; returns `(new_fm, report_dict)` |

New constant `DISPATCHER_LIST_FIELDS` — canonical set of dispatcher metadata keys that expect inline CSV values. Imported by `build_registry.py` to avoid duplication.

17 new tests in `tests/test_normalize.py` cover all helpers and edge cases including the malformed `personal-context-portfolio` frontmatter pattern.
