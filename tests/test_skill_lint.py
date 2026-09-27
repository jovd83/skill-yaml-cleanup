"""
test_skill_lint.py — Tests for scripts/skill_lint.py. Every skill is built in tmp_path.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import skill_lint  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "skill_lint.py")

CLEAN_FM = """\
name: {name}
description: "Use when a test needs a clean skill: it has every field the linter expects."
metadata:
  author: jovd83
  version: 1.0.0
"""


def make_skill(root, name="demo-skill", frontmatter=None, body="# Demo\n\nBody text.\n", files=None):
    skill = root / name
    skill.mkdir(parents=True, exist_ok=True)
    fm = frontmatter if frontmatter is not None else CLEAN_FM.format(name=name)
    (skill / "SKILL.md").write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")
    for rel, content in (files or {}).items():
        p = skill / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return skill


def checks(findings, severity=None):
    return sorted({f.check for f in findings if severity is None or f.severity == severity})


def run_cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8")


# ---------------------------------------------------------------------------
# Frontmatter, name, description, fields
# ---------------------------------------------------------------------------

def test_clean_skill_has_no_findings(tmp_path):
    skill = make_skill(tmp_path)
    assert skill_lint.lint_skill(skill / "SKILL.md") == []


def test_unquoted_colon_in_description_is_invalid_yaml(tmp_path):
    fm = "name: demo-skill\ndescription: Use when: the value has a colon\nmetadata:\n  author: a\n  version: 1\n"
    findings = skill_lint.lint_skill(make_skill(tmp_path, frontmatter=fm) / "SKILL.md")
    assert checks(findings, "error") == ["frontmatter"]
    assert "quote values" in findings[0].message
    assert findings[0].line == 3


def test_missing_frontmatter(tmp_path):
    skill = tmp_path / "bare"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Bare\n", encoding="utf-8")
    assert checks(skill_lint.lint_skill(skill / "SKILL.md"), "error") == ["frontmatter"]


def test_crlf_frontmatter_parses(tmp_path):
    skill = make_skill(tmp_path)
    md = skill / "SKILL.md"
    md.write_bytes(md.read_bytes().replace(b"\n", b"\r\n"))
    assert skill_lint.lint_skill(md) == []


def test_name_must_match_folder_unless_configured(tmp_path):
    skill = make_skill(tmp_path, name="folder-name", frontmatter=CLEAN_FM.format(name="other-name"))
    assert checks(skill_lint.lint_skill(skill / "SKILL.md"), "error") == ["name-folder"]
    (skill / ".skill-lint.json").write_text(json.dumps({"expect_name": "other-name"}), encoding="utf-8")
    assert skill_lint.lint_skill(skill / "SKILL.md") == []


def test_sub_skill_name_is_exempt_from_folder_match(tmp_path):
    parent = make_skill(tmp_path, "parent-skill")
    sub = make_skill(parent / "modules", "core", frontmatter=CLEAN_FM.format(name="parent-core"))
    assert skill_lint.lint_skill(sub / "SKILL.md") == []
    assert checks(skill_lint.lint_skill(sub / "SKILL.md", expect_name="core"), "error") == ["name-folder"]


def test_name_format(tmp_path):
    skill = make_skill(tmp_path, name="Bad_Name", frontmatter=CLEAN_FM.format(name="Bad_Name"))
    assert checks(skill_lint.lint_skill(skill / "SKILL.md"), "error") == ["name"]


def test_description_limit(tmp_path):
    fm = f"name: demo-skill\ndescription: \"{'x' * 1025}\"\nmetadata:\n  author: a\n  version: 1\n"
    findings = skill_lint.lint_skill(make_skill(tmp_path, frontmatter=fm) / "SKILL.md")
    assert checks(findings, "error") == ["description"]
    assert "1,025" in findings[0].message


def test_context_must_be_fork_and_flags_boolean(tmp_path):
    fm = CLEAN_FM.format(name="demo-skill") + "context: inline\ndisable-model-invocation: \"yes\"\n"
    findings = skill_lint.lint_skill(make_skill(tmp_path, frontmatter=fm) / "SKILL.md")
    assert [f.check for f in findings if f.severity == "error"] == ["fields", "fields"]

    ok = CLEAN_FM.format(name="demo-skill") + "context: fork\nagent: Explore\ndisable-model-invocation: true\n"
    assert skill_lint.lint_skill(make_skill(tmp_path / "b", frontmatter=ok) / "SKILL.md") == []


def test_unknown_keys_and_missing_author_version_are_warnings(tmp_path):
    fm = "name: demo-skill\ndescription: Use when testing.\nflavour: vanilla\n"
    body = "# Demo\n\n> **Author:** jovd83 | **Version:** 1.0.0\n"
    findings = skill_lint.lint_skill(make_skill(tmp_path, frontmatter=fm, body=body) / "SKILL.md")
    assert checks(findings, "error") == []
    assert checks(findings, "warning") == ["author-version", "keys"]
    av = next(f for f in findings if f.check == "author-version")
    assert "found only outside metadata: author, version" in av.message


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

def test_dev_paths_in_skill_files_readme_and_changelog(tmp_path):
    dev = "C:" + "\\projects\\skills\\other-skill"
    skill = make_skill(tmp_path, files={
        "references/guide.md": f"intro\nsee {dev} for details\n",
        "scripts/run.ps1": "$root = '/c/" + "projects/skills/x'\n",
        "README.md": f"Clone into {dev}\n",
        "CHANGELOG.md": f"- removed {dev}\n",
    })
    findings = skill_lint.lint_skill(skill / "SKILL.md")
    errors = [(f.path, f.line) for f in findings if f.check == "dev-paths" and f.severity == "error"]
    assert errors == [("demo-skill/references/guide.md", 2), ("demo-skill/scripts/run.ps1", 1)]
    warnings = [f.path for f in findings if f.check == "dev-paths" and f.severity == "warning"]
    assert warnings == ["demo-skill/README.md"]


def test_telemetry_in_skill_md_and_references_only(tmp_path):
    body = "# Demo\n\n## Telemetry\n\nRun `log-dispatch` before anything else.\n"
    skill = make_skill(tmp_path, body=body, files={"scripts/hook.py": "import dispatch_logger\n"})
    findings = skill_lint.lint_skill(skill / "SKILL.md")
    assert [(f.check, f.line) for f in findings] == [("telemetry", 13)]


def test_negated_telemetry_mention_is_not_an_instruction(tmp_path):
    body = "# Demo\n\nDo not run `log-dispatch` for normal skill use; hooks log usage.\n"
    assert skill_lint.lint_skill(make_skill(tmp_path, body=body) / "SKILL.md") == []


def test_links_resolve_and_code_fences_are_ignored(tmp_path):
    body = ("# Demo\n\nSee [guide](references/guide.md), [gone](references/gone.md#part) and "
            "[site](https://example.com).\n\n```markdown\n[example](not/checked.md)\n```\n")
    skill = make_skill(tmp_path, body=body, files={"references/guide.md": "ok\n"})
    findings = skill_lint.lint_skill(skill / "SKILL.md")
    assert [(f.check, f.severity, f.line) for f in findings] == [("links", "warning", 11)]
    assert "references/gone.md#part" in findings[0].message


def test_size_warning(tmp_path):
    body = "# Demo\n" + "line\n" * 520
    findings = skill_lint.lint_skill(make_skill(tmp_path, body=body) / "SKILL.md")
    assert checks(findings) == ["size"]


def test_skip_from_argument_and_repo_config(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".skill-lint.json").write_text(json.dumps({"skip": ["keys"]}), encoding="utf-8")
    fm = "name: demo-skill\ndescription: Use when testing.\nflavour: vanilla\n"
    md = make_skill(tmp_path, frontmatter=fm) / "SKILL.md"
    assert checks(skill_lint.lint_skill(md)) == ["author-version"]
    assert skill_lint.lint_skill(md, skip={"author-version"}) == []


# ---------------------------------------------------------------------------
# Discovery and CLI
# ---------------------------------------------------------------------------

def test_discover_prunes_non_skill_folders(tmp_path):
    make_skill(tmp_path, "real-skill")
    make_skill(tmp_path / "real-skill" / "skills", "nested-skill")
    for noise in ("node_modules/pkg", "tests/fixtures/bad", "old-workspace/copy", ".git/x", "examples/demo"):
        make_skill(tmp_path / noise, "noise")
    found = sorted(p.parent.name for p in skill_lint.discover(tmp_path))
    assert found == ["nested-skill", "real-skill"]


def test_cli_exit_codes(tmp_path):
    clean = make_skill(tmp_path / "a")
    assert run_cli(clean).returncode == 0

    warn_fm = "name: demo-skill\ndescription: Use when testing.\n"
    warn = make_skill(tmp_path / "b", frontmatter=warn_fm)
    assert run_cli(warn).returncode == 0
    assert run_cli(warn, "--strict").returncode == 1
    assert run_cli(warn, "--strict", "--skip", "author-version").returncode == 0

    broken = make_skill(tmp_path / "c", frontmatter="name: demo-skill\n")
    result = run_cli(broken, "--json")
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["errors"] == 1 and data["findings"][0]["check"] == "description"

    assert run_cli(tmp_path / "missing").returncode == 2
    assert run_cli(clean, clean, "--expect-name", "x").returncode == 2


def test_readme_checker_failures_become_findings(tmp_path):
    (tmp_path / ".git").mkdir()
    skill = make_skill(tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    checker = tmp_path / "fake_check_readme.py"
    checker.write_text(textwrap.dedent("""\
        import sys
        print("README audit: demo")
        print("  [FAIL] required section 'When To Use It'")
        print("         missing")
        print("  [WARN] section order")
        sys.exit(1)
        """), encoding="utf-8")
    result = run_cli(skill, "--readme", "--readme-checker", checker, "--json")
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert [(f["check"], f["message"]) for f in data["findings"]] == [
        ("readme", "required section 'When To Use It': missing")]
