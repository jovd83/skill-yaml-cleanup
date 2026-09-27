---
name: skill-lint
description: "Lint AgentSkill folders before they are installed, synced or published: frontmatter that parses as YAML, a name that matches the folder, a description within 1,024 characters, no development-tree paths, no model-run telemetry instructions, and optionally the README standard. Also trims oversized frontmatter, with approval."
disable-model-invocation: true
argument-hint: "[path ...] [--readme] [--strict]"
metadata:
  author: jovd83
  version: 3.0.0
  dispatcher-category: analysis
  dispatcher-capabilities: skill-lint, frontmatter-validation, readme-audit, frontmatter-trim
  dispatcher-accepted-intents: lint_skills, validate_skill_frontmatter, audit_skill_frontmatter, reduce_frontmatter_bloat
  dispatcher-output-artifacts: lint_report, optimization_proposals, cleaned_skill_files
  dispatcher-risk: low
  dispatcher-writes-files: true
  dispatcher-layer: execution
  dispatcher-lifecycle: active
---

# Skill Lint

> **Author:** jovd83 | **Version:** 3.0.0 | **License:** MIT

Lint AgentSkill folders and report what would stop a harness from loading a skill, or from picking it by its description, plus the house rules of this library. Linting is read-only. Fixes happen only after the user approves them.

Run it as `/skill-lint <path>`. With no path, lint the current repository.

## Run The Linter

```bash
python "<skill folder>/scripts/skill_lint.py" <path> [<path> ...]
```

`<skill folder>` is the folder that holds this SKILL.md (`${CLAUDE_SKILL_DIR}` in Claude Code). A path can be a skill folder, a SKILL.md, or a tree such as a whole skills directory. The script needs PyYAML: `pip install pyyaml`, or `uv run --with pyyaml python ...`.

| Flag | Effect |
|---|---|
| `--readme` | Also run skill-readme-standard's `check_readme.py` on each repository root. |
| `--strict` | Warnings fail the run too. |
| `--skip a,b` | Switch checks off by id. |
| `--expect-name x` | Expected `name` for a single skill, instead of its folder name. |
| `--json` | Machine-readable result. |
| `--quiet` | Print errors only. |

Exit codes: `0` nothing fails, `1` findings fail the run, `2` bad invocation.

## Checks

| Id | Severity | Rule |
|---|---|---|
| `frontmatter` | error | A frontmatter block exists, parses as YAML, and is a mapping. |
| `name` | error | Lowercase letters, digits and single hyphens, at most 64 characters. |
| `name-folder` | error | Equals the skill's folder name. Sub-skills inside another skill are exempt. |
| `description` | error | Present and at most 1,024 characters. A `<` is a warning. |
| `fields` | error | `metadata` is a mapping, `context` is `fork`, `disable-model-invocation` and `user-invocable` are booleans. |
| `dev-paths` | error | No absolute paths into the development checkout in SKILL.md, `references/`, `scripts/`, `agents/` or `assets/`. A warning in README.md. |
| `telemetry` | error | No instructions telling the model to log its own skill usage, in SKILL.md or `references/`. Harness hooks do the logging. |
| `keys` | warning | Top-level keys outside the Agent Skills and Claude Code set. |
| `author-version` | warning | `metadata` carries `author` and `version`. |
| `size` | warning | SKILL.md stays under 500 lines. |
| `links` | warning | Relative links in SKILL.md resolve. Code blocks are ignored. |
| `readme` | error | With `--readme`: the README passes `check_readme.py`. |

A `.skill-lint.json` next to SKILL.md or at the repository root switches checks off for that skill: `{"skip": ["telemetry"], "expect_name": "my-skill"}`. Every skip needs a reason in the repository, such as a line in the README or CHANGELOG.

## Report

1. Lead with the totals: skills checked, errors, warnings.
2. List the errors grouped by skill, each with `file:line`, the check id and one line on the fix.
3. Summarise warnings by check, unless the user asks for all of them.
4. Mark third-party skills (no source in the user's own repositories) as report-only.
5. Propose fixes and stop. Change nothing until the user approves.

## Fixing Findings

| Check | Fix |
|---|---|
| `frontmatter` | Quote any value that contains `: ` or starts with a special character; the usual culprit is an unquoted description. |
| `name`, `name-folder` | Rename the `name` field or the folder. A public skill's name is also its trigger and often its repository name, so ask which one should change. |
| `description` | Shorten it while keeping the trigger phrases; drop restated examples first. |
| `fields` | Use `context: fork` or remove `context`; write booleans as `true` or `false`. |
| `dev-paths` | Use a path relative to the skill folder, `${CLAUDE_SKILL_DIR}`, or an environment variable. |
| `telemetry` | Delete the block. Usage logging belongs in harness hooks. |
| `keys` | Move custom fields under `metadata`. |
| `author-version` | Add `author` and `version` under `metadata`, matching the body's version line and the CHANGELOG. |

After fixing, run the linter again on the changed skills only and report the new totals.

## Oversized Frontmatter

When frontmatter is too long for a platform's budget, use the trim tools. Every tool supports `--dry-run`, so preview first.

1. `python scripts/audit.py --dir <skills directory> [--limit 1000]` reports blocks over the limit by severity.
2. `python scripts/analyze.py --file <SKILL.md>` proposes deduplication, list flattening, noise removal, field migration and description trimming, with estimated savings.
3. Show the before/after proposal and ask for approval. This is a hard stop: nothing is written without a yes.
4. Apply in order: `deduplicate.py --backup`, `flatten.py`, `remove_noise.py`, `migrate_to_body.py`, then any approved description edit.
5. Re-run `audit.py` and `skill_lint.py` on the changed files.

`migrate_to_body.py` moves `license`, `compatibility`, `homepage`, `platforms` and `metadata.maturity` into the body line. `author` and `version` stay in `metadata`. `scripts/cleanup.py` runs the same pipeline in one command and still needs the approval gate before `--apply`.

## Continuous Integration

The repository is also a GitHub Action:

```yaml
- uses: actions/checkout@v4
- uses: jovd83/skill-lint@v3
  with:
    path: .
    readme: "true"
```

Inputs: `path` (default `.`), `readme`, `strict`, and `args` for extra flags. In Actions the checkout folder is named after the repository, so `name-folder` compares the skill name with the repository name.

## Guardrails

- Linting never writes files. Fixes wait for explicit approval, and the first write to a file uses `--backup`.
- Never run the scripts of the skill under review; read its files only.
- Do not bypass a failing check with `--skip` or `.skill-lint.json` unless the user agrees, and record the reason.
- In the two-tree layout, fix the development source and let the sync update the installed copy. Never edit the installed copy.

## Scripts Reference

| Script | Purpose | Key flags |
|---|---|---|
| `scripts/skill_lint.py` | Lint skills and optionally their READMEs | `--readme`, `--strict`, `--skip`, `--expect-name`, `--json`, `--quiet` |
| `scripts/audit.py` | Report oversized frontmatter blocks | `--dir`, `--files`, `--limit`, `--json` |
| `scripts/analyze.py` | Per-skill trim recommendations | `--file`, `--json` |
| `scripts/deduplicate.py` | Merge duplicate `metadata:` blocks | `--file`, `--dry-run`, `--backup` |
| `scripts/flatten.py` | Turn vertical YAML lists into inline values | `--file`, `--dry-run`, `--backup` |
| `scripts/remove_noise.py` | Strip decorative and empty fields | `--file`, `--dry-run`, `--backup` |
| `scripts/migrate_to_body.py` | Move non-routing fields into the body line | `--file`, `--dry-run`, `--backup` |
| `scripts/cleanup.py` | Trim pipeline in one command | `--analyze`, `--apply`, `--dry-run`, `--backup`, `--json` |
