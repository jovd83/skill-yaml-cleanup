"""
test_common.py — Tests for the shared _common module.
"""

import os
import sys
import tempfile

import pytest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from _common import extract_frontmatter, reassemble, FRONTMATTER_LIMIT

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtractFrontmatter:
    def test_clean_file(self):
        path = os.path.join(FIXTURES, "clean", "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm, body = extract_frontmatter(content)
        assert fm is not None
        assert "name: example-clean-skill" in fm
        assert "# Example Clean Skill" in body

    def test_no_frontmatter(self):
        path = os.path.join(FIXTURES, "no-frontmatter", "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm, body = extract_frontmatter(content)
        assert fm is None
        assert "No frontmatter here" in body

    def test_body_with_horizontal_rules(self):
        """Ensure --- in the body doesn't break extraction."""
        path = os.path.join(FIXTURES, "body-with-hr", "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm, body = extract_frontmatter(content)
        assert fm is not None
        assert "name: body-with-hr" in fm
        # Body should contain the HR lines
        assert "---" in body
        assert "Another Section" in body

    def test_oversized_file(self):
        path = os.path.join(FIXTURES, "oversized", "SKILL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        fm, body = extract_frontmatter(content)
        assert fm is not None
        assert len(fm) > FRONTMATTER_LIMIT

    def test_reassemble_roundtrip(self):
        content = "---\nname: test\n---\n# Body\nHello"
        fm, body = extract_frontmatter(content)
        result = reassemble(fm, body)
        assert result == content


class TestReassemble:
    def test_basic(self):
        result = reassemble("name: foo\n", "# Title\nBody")
        assert result == "---\nname: foo\n\n---\n# Title\nBody"
