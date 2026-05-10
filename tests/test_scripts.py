"""
test_scripts.py — Integration tests for the optimization scripts.
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from _common import extract_frontmatter, read_file, FRONTMATTER_LIMIT

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def temp_skill(tmp_path):
    """Copy the oversized fixture to a temp dir for mutation tests."""
    src = os.path.join(FIXTURES, "oversized", "SKILL.md")
    dst = tmp_path / "SKILL.md"
    shutil.copy2(src, dst)
    return str(dst)


class TestAudit:
    def test_scan_finds_fixtures(self):
        from audit import scan
        results = scan(FIXTURES, FRONTMATTER_LIMIT)
        assert len(results) >= 3  # clean, oversized, body-with-hr (no-frontmatter has None)

    def test_clean_file_has_no_excess(self):
        from audit import measure
        path = os.path.join(FIXTURES, "clean", "SKILL.md")
        result = measure(path, FRONTMATTER_LIMIT)
        assert result["excess"] == 0
        assert result["severity"] == "clean"


class TestDeduplicate:
    def test_removes_duplicate_metadata(self, temp_skill):
        from deduplicate import process
        content_before = read_file(temp_skill)
        assert content_before.count("metadata:") >= 2

        process(temp_skill, dry_run=False)
        content_after = read_file(temp_skill)
        fm, _ = extract_frontmatter(content_after)
        # After dedup the metadata key should appear once
        assert fm.count("metadata:") <= 1


class TestFlatten:
    def test_converts_vertical_to_inline(self, temp_skill):
        from flatten import process
        content_before = read_file(temp_skill)
        assert "    - code-scanning" in content_before

        process(temp_skill, dry_run=False)
        content_after = read_file(temp_skill)
        assert "    - code-scanning" not in content_after


class TestRemoveNoise:
    def test_removes_tags(self, temp_skill):
        from remove_noise import process
        process(temp_skill, dry_run=False)
        content_after = read_file(temp_skill)
        fm, _ = extract_frontmatter(content_after)
        # Check that the noise fields are removed (but dispatcher-stack-tags stays)
        fm_lines = fm.split("\n")
        meta_tags_lines = [l for l in fm_lines if "metadata-tags:" in l]
        noise_tags_lines = [l for l in fm_lines if l.strip().startswith("tags:")]
        assert len(meta_tags_lines) == 0, "metadata-tags should be removed"
        assert len(noise_tags_lines) == 0, "standalone tags: should be removed"


class TestMigrateToBody:
    def test_moves_license_to_body(self, temp_skill):
        from migrate_to_body import process
        process(temp_skill, dry_run=False)
        content_after = read_file(temp_skill)
        fm, body = extract_frontmatter(content_after)
        assert "license:" not in fm
        assert "**License:**" in body


class TestBackup:
    def test_backup_creates_bak_file(self, temp_skill):
        from deduplicate import process
        process(temp_skill, dry_run=False, backup=True)
        assert os.path.exists(temp_skill + ".bak")
