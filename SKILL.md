---
name: skill-yaml-cleanup
description: "Audit and reduce YAML frontmatter bloat in SKILL.md files. Trigger to: scan skill directories, identify oversized frontmatter, propose deduplication/flattening/migration optimizations, and apply approved changes. Requires user approval before writing."
metadata:
  dispatcher-category: analysis
  dispatcher-capabilities: frontmatter-audit, yaml-deduplication, metadata-flattening, noise-removal, field-migration, description-trim
  dispatcher-accepted-intents: audit_skill_frontmatter, optimize_yaml_metadata, cleanup_skill_registry, reduce_frontmatter_bloat
  dispatcher-input-artifacts: skills_directory, skill_md_files
  dispatcher-output-artifacts: audit_report, optimization_proposals, cleaned_skill_files
  dispatcher-stack-tags: yaml, skills, metadata, registry, frontmatter
  dispatcher-risk: medium
  dispatcher-writes-files: true
  dispatcher-layer: execution
  dispatcher-lifecycle: active
  dispatcher-preferred-model: claude-haiku-4-5-20251001
---

## Telemetry & Logging
> [!IMPORTANT]
> All usage of this skill must be logged via the Skill Dispatcher to ensure audit logs and wallboard analytics are accurate:
> `./log-dispatch.cmd --skill <skill_name> --intent <intent> --model <model_name> --reason <reason>` (or `./log-dispatch.sh` on Linux)

# Skill YAML Cleanup

> **Author:** jovd83 | **Version:** 2.0.0 | **License:** MIT

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](CHANGELOG.md)

Audit and optimize YAML frontmatter in `SKILL.md` files. Agent platforms enforce a **1,000-character limit** on frontmatter blocks. Exceeding this causes preloading failures and context overflow. This skill finds, analyzes, and — with your approval — fixes oversized blocks.

## When to Trigger

- User says "clean up skill metadata", "frontmatter is too long", "reduce YAML bloat", or "audit skills"
- Skills are failing to preload or causing context overflow
- New metadata fields were added and may have exceeded the limit
- Auditing or migrating a skill registry

## Workflow

Follow these phases in order. **Never modify files before the approval gate in Phase 3.**

### Phase 1 — Audit

Scan the skills directory and report all oversized frontmatter blocks:

```bash
python scripts/audit.py --dir <skills_directory>
```

Report to the user:
- Total skills scanned
- Total over the 1,000-char limit
- Grouped by severity: **Critical** (>1,300), **Warning** (1,100–1,300), **Tolerable** (1,000–1,100)

Use `--json` for structured output when chaining with other tools.

### Phase 2 — Analyze and Propose

For each oversized skill, determine which optimizations apply:

```bash
python scripts/analyze.py --file <path/to/SKILL.md>
```

| Optimization | When to Apply | Typical Saving |
|:---|:---|:---:|
| **Deduplication** | Duplicate `metadata:` blocks exist | 200–500 chars |
| **Flattening** | Vertical YAML lists (`- item`) in metadata | 20–80 chars |
| **Noise removal** | Empty fields, `tags:`, `metadata-tags:`, external tool configs | 50–200 chars |
| **Field migration** | Non-dispatcher fields: `license`, `author`, `version`, `maturity`, `compatibility`, `homepage`, `platforms` | 50–270 chars |
| **Description trim** | Description > 300 chars (last resort) | 50–180 chars |

Present a **before/after diff** for each proposed change:

```
Skill: release-manager-skill  (1,524 → ~970 chars, saves 554)
Actions: field-migration, description-trim, flattening

BEFORE description:
  "Validate and prepare GitHub releases following SemVer and CHANGELOG standards. Trigger to: ..."

AFTER description:
  "Validate and prepare GitHub releases. Trigger for: SemVer changelogs, version bumps, release commits, CI/CD monitoring, and repo bootstrap."

Fields to REMOVE from frontmatter (moved to body):
  license, compatibility, author, version, maturity
```

**Do not apply changes yet.** Present the full proposal and ask: *"Shall I apply these changes?"*

### Phase 3 — Approval Gate (mandatory)

Wait for explicit user confirmation. This is a **hard stop**.

- **Yes to all:** proceed to Phase 4
- **Yes to some:** apply only the approved skills/optimizations
- **No:** stop — no files are modified

### Phase 4 — Apply

Apply approved changes using the bundled scripts. Run in this order per skill:

1. `scripts/deduplicate.py --file <path> --backup` — merge duplicate metadata blocks
2. `scripts/flatten.py --file <path>` — convert vertical lists to inline values
3. `scripts/remove_noise.py --file <path>` — strip noise/decorative fields
4. `scripts/migrate_to_body.py --file <path>` — move non-dispatcher fields to body
5. Manual description trim (if approved) — edit the `description:` value directly

Always use `--backup` on the **first** script to create a `.bak` safety copy. Subsequent scripts operate on the already-backed-up file.

Use `--dry-run` on any script to preview without writing.

### Phase 5 — Verify

Re-run the audit on modified files only:

```bash
python scripts/audit.py --dir <skills_directory> --files <changed_file1> <changed_file2>
```

Report the final result:
- ✅ Skills now clean (≤ 1,000 chars)
- ⚠️ Skills still over (and by how much)

If any skill remains over after all safe optimizations, report it as requiring manual description editing and show the user the exact line to trim.

### Alternative: Unified Pipeline

For convenience, all phases can be run through a single command:

```bash
python scripts/cleanup.py --dir <skills_directory> --analyze --apply --backup --dry-run
```

Remove `--dry-run` to apply changes. The unified CLI still requires the agent to present results and obtain approval before the `--apply` phase.

## Frontmatter vs. Body Contract

### Stays in frontmatter (dispatcher reads these)
`name`, `description`, all `metadata.dispatcher-*` keys

### Moves to body (agent reads the full file)
`license`, `compatibility`, `author`, `version`, `maturity`, `homepage`, `platforms`

The agent reads the **entire SKILL.md** — moving fields to the body loses nothing. The dispatcher preloader only reads the frontmatter block.

**Migrated metadata format in body:**
```markdown
> **Author:** jovd83 | **Version:** 2.0.0 | **License:** MIT
> **Compatibility:** Requires Python 3.10+
```

## Guardrails

- **Never apply without approval.** The Phase 3 approval gate is mandatory and non-negotiable.
- **Never trim `dispatcher-*` keys.** These are the routing contract. Only shorten *values* where safe.
- **Preserve semantic meaning.** When shortening descriptions or capability values, keep all trigger keywords. Do not remove domain terms that help the dispatcher match the skill.
- **Do not over-abbreviate intents.** `prepare_release` is acceptable; `prep_rel` is not.
- **Always use `--backup` on the first write** to a file. If something goes wrong, the `.bak` file provides recovery.
- **Use `--dry-run` first** when uncertain about the impact of an optimization.

## Scripts Reference

| Script | Purpose | Key Flags |
|:---|:---|:---|
| `scripts/cleanup.py` | Unified pipeline (audit → analyze → apply) | `--analyze`, `--apply`, `--dry-run`, `--backup`, `--json` |
| `scripts/audit.py` | Scan directory, report oversized files | `--dir`, `--files`, `--limit`, `--json` |
| `scripts/analyze.py` | Per-skill optimization recommendations | `--file`, `--json` |
| `scripts/deduplicate.py` | Merge duplicate metadata blocks | `--file`, `--dry-run`, `--backup` |
| `scripts/flatten.py` | Convert vertical lists to inline values | `--file`, `--dry-run`, `--backup` |
| `scripts/remove_noise.py` | Strip noise/decorative fields | `--file`, `--dry-run`, `--backup` |
| `scripts/migrate_to_body.py` | Move non-dispatcher fields to body | `--file`, `--dry-run`, `--backup` |

## Optional Integration: Telemetry

If your environment uses a skill dispatcher with telemetry logging, log usage after each invocation:
```
./log-dispatch.cmd --skill skill-yaml-cleanup --intent <intent> --model <model> --reason <reason>
```
This is optional and depends on your infrastructure setup.
