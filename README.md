# Skill Lint

[![version](https://img.shields.io/badge/version-3.0.0-blue)](CHANGELOG.md)
[![status](https://img.shields.io/badge/status-stable-3fb950)](SKILL.md)
[![category](https://img.shields.io/badge/category-analysis-0a7ea4)](SKILL.md)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Validate Skills](https://github.com/jovd83/skill-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/jovd83/skill-lint/actions/workflows/ci.yml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/jovd83)

`skill-lint` checks AgentSkill folders before they are installed, synced or published, and fails the ones a harness would load wrongly or not at all. It runs as a `/skill-lint` command, as a script, and as a GitHub Action. It grew out of `skill-yaml-cleanup`, whose frontmatter trim tools it still ships.

## What This Skill Does

A skill that looks fine in an editor can be invisible to the agent. An unquoted `: ` in the description breaks the YAML, and the harness falls back to the file's heading. A name that differs from the folder makes the skill show up under the wrong name. A description over 1,024 characters gets cut. None of this produces an error message. The skill just stops being chosen.

`skill-lint` makes those failures loud. For every SKILL.md it finds, it checks:

- **Loadability.** The frontmatter parses as YAML. The `name` is well-formed and matches the folder. The description is present and at most 1,024 characters. `context`, `metadata` and the boolean flags have valid values.
- **Portability.** No absolute paths into the author's development checkout, which installed copies cannot reach.
- **Hygiene.** No blocks telling the model to log its own usage, since harness hooks do that now. No unknown top-level keys. `author` and `version` sit in `metadata`. SKILL.md stays under 500 lines, and its relative links resolve.
- **README standard.** Optional: runs `check_readme.py` from [skill-readme-standard](https://github.com/jovd83/skill-readme-standard) on each repository.

For frontmatter that is simply too long, the trim tools from `skill-yaml-cleanup` are still here. They deduplicate, flatten, strip noise and move fields into the body, always behind an approval gate.

## What This Skill Does Not Do

- **It does not judge whether a skill is good.** It checks structure and house rules, not the quality of the instructions. Use `skill-creator` evals or a review for that.
- **It is not a security review.** It never runs the skill's scripts and does not look for malicious content. Use `skill-vetting-reporter` or the `skill-vetter` agent before installing someone else's skill.
- **It does not fix anything on its own.** Linting is read-only. Fixes, including the trim tools, need explicit approval.
- **It does not check the README's prose.** `--readme` delegates to `check_readme.py`, which checks sections, badges and install instructions, not the writing.

## When To Use It

Use it when:

- You are about to commit, release or sync a skill: `/skill-lint .`
- A skill no longer triggers, or shows up with a heading instead of its description.
- You want a CI gate on a skill repository, so broken frontmatter never reaches the default branch.
- You are auditing a whole skills directory, whether your own or an installed runtime tree.
- A platform rejects a skill because its frontmatter is too long.

It only runs when you invoke it (`disable-model-invocation: true`), so it never competes with other skills for automatic selection.

## Repository Layout

```
skill-lint/
├── SKILL.md                  # the /skill-lint command: run, report, fix with approval
├── action.yml                # composite GitHub Action
├── scripts/
│   ├── skill_lint.py         # the linter (needs PyYAML)
│   ├── audit.py              # frontmatter size report
│   ├── analyze.py            # per-skill trim recommendations
│   ├── deduplicate.py        # merge duplicate metadata blocks
│   ├── flatten.py            # vertical lists to inline values
│   ├── remove_noise.py       # strip decorative and empty fields
│   ├── migrate_to_body.py    # move non-routing fields into the body line
│   ├── cleanup.py            # trim pipeline in one command
│   ├── _common.py            # shared frontmatter helpers (also used by skill-dispatcher)
│   ├── validate_repo.py      # repository validation
│   └── validate_repo.ps1
├── tests/                    # pytest suite; fixtures/ holds sample SKILL.md files
└── evals/evals.json          # 6 eval cases
```

## Installation

```bash
npx skills add jovd83/skill-lint
```

Manual alternative:

```bash
git clone https://github.com/jovd83/skill-lint.git
```

Then place the repository folder where your agent looks for local skills, such as `~/.agents/skills/skill-lint/` or `~/.claude/skills/skill-lint/`. The folder name must be `skill-lint`, or the linter will flag its own name.

Requirements: Python 3.10+ and PyYAML (`pip install pyyaml`). The trim tools need only the standard library. `--readme` needs [skill-readme-standard](https://github.com/jovd83/skill-readme-standard) installed next to this skill, or its `check_readme.py` path passed with `--readme-checker`.

## Usage

In an agent that supports slash commands:

```text
/skill-lint ~/.agents/skills --quiet
```

From a shell:

```bash
python scripts/skill_lint.py path/to/skill                 # one skill
python scripts/skill_lint.py ~/.agents/skills --quiet      # a whole tree, errors only
python scripts/skill_lint.py . --readme --strict           # release gate: README too, warnings fail
python scripts/skill_lint.py . --json > lint.json          # for other tools
```

In GitHub Actions:

```yaml
jobs:
  skill-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jovd83/skill-lint@v3
        with:
          path: .
          readme: "true"      # optional
          strict: "false"     # optional
          args: ""            # optional, e.g. "--skip keys"
```

The action uses the runner's Python when it already has PyYAML. Otherwise it installs PyYAML into a private virtual environment, so the job's own Python is never changed.

A `.skill-lint.json` at the repository root, or next to a SKILL.md, switches checks off: `{"skip": ["telemetry"], "expect_name": "my-skill"}`.

## Output Contract

Text output, one finding per line, sorted by file:

```text
ERROR  my-skill/SKILL.md:3  [frontmatter] frontmatter is not valid YAML: mapping values are not allowed here (quote values that contain ': ')
WARN   my-skill/SKILL.md  [author-version] `metadata` has no author or version (found only outside metadata: author, version)

skill-lint: 1 skill(s), 1 error(s), 1 warning(s) — failed
```

With `--json`, the result is `{"skills", "errors", "warnings", "failed", "findings": [{"path", "check", "severity", "message", "line"}]}`. Exit code `0` means nothing failed, `1` means findings failed the run, and `2` means a bad invocation.

## Validation

```bash
python scripts/validate_repo.py
```

This runs the pytest suite (the trim tools plus `tests/test_skill_lint.py`, which builds every sample skill in a temporary folder), a frontmatter size self-audit, and `skill_lint.py` on this repository. CI runs the same script and then lints the repository through `action.yml`.

## Optional Integrations

- **skill-readme-standard:** `--readme` runs its `check_readme.py`.
- **Skill sync:** a manifest-driven sync can import `lint_skill()` from `scripts/skill_lint.py` and refuse to install skills with blocking errors.
- **skill-dispatcher:** `build_registry.py` imports `normalize()` from `scripts/_common.py` when this skill is installed next to it.

## Contributing

Edit in this repository and run `python scripts/validate_repo.py`. Then copy the repository folder to your skills directory as `skill-lint/`. The installed copy is downstream and should never be edited directly.

## License

MIT — see [LICENSE](LICENSE).
