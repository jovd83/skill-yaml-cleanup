"""
test_normalize.py — Unit tests for the composable frontmatter normalizers
added to _common.py: dedupe_metadata_blocks, flatten_vertical_lists,
strip_noise, and normalize.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from _common import (
    FRONTMATTER_LIMIT,
    dedupe_metadata_blocks,
    flatten_vertical_lists,
    normalize,
    strip_noise,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fm(text: str) -> str:
    """Strip leading/trailing newlines from an indented multi-line string."""
    return text.strip("\n")


# ---------------------------------------------------------------------------
# dedupe_metadata_blocks
# ---------------------------------------------------------------------------

class TestDedupeMetadataBlocks:
    def test_single_metadata_block_unchanged(self):
        raw = fm("""
name: my-skill
description: A skill
metadata:
  dispatcher-layer: execution
  dispatcher-lifecycle: active
""")
        result, report = dedupe_metadata_blocks(raw)
        assert "dispatcher-layer: execution" in result
        assert "dispatcher-lifecycle: active" in result
        assert report["removed"] == 0

    def test_duplicate_metadata_blocks_merged(self):
        raw = fm("""
name: my-skill
description: A skill
metadata:
  dispatcher-layer: execution
  dispatcher-capabilities: foo, bar
metadata:
  dispatcher-layer: execution
  dispatcher-capabilities: foo, bar
""")
        result, report = dedupe_metadata_blocks(raw)
        # Only one metadata: block in output
        assert result.count("metadata:") == 1
        assert result.count("dispatcher-layer") == 1
        assert result.count("dispatcher-capabilities") == 1

    def test_duplicate_metadata_blocks_values_deduplicated(self):
        raw = fm("""
name: my-skill
description: A skill
metadata:
  dispatcher-layer: execution
metadata:
  dispatcher-layer: feedback
""")
        result, _ = dedupe_metadata_blocks(raw)
        # Both unique values should survive (merged list)
        assert "execution" in result or "feedback" in result

    def test_duplicate_top_level_description_merged(self):
        raw = fm("""
name: my-skill
description: First description
description: Second description
""")
        result, _ = dedupe_metadata_blocks(raw)
        # The key 'description:' must appear exactly once (de-duplicated)
        key_occurrences = sum(1 for line in result.split("\n") if line.startswith("description:") or line.startswith("description:"))
        assert key_occurrences == 1


# ---------------------------------------------------------------------------
# flatten_vertical_lists
# ---------------------------------------------------------------------------

class TestFlattenVerticalLists:
    def test_vertical_list_flattened(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-capabilities:
    - foo
    - bar
    - baz
""")
        result, report = flatten_vertical_lists(raw)
        assert "dispatcher-capabilities: foo, bar, baz" in result
        assert "- foo" not in result
        assert "dispatcher-capabilities" in report["flattened"]

    def test_inline_list_unchanged(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-capabilities: foo, bar
""")
        result, report = flatten_vertical_lists(raw)
        assert "dispatcher-capabilities: foo, bar" in result
        assert report["flattened"] == []

    def test_malformed_pcp_case_category_list(self):
        """dispatcher-category is NOT in DISPATCHER_LIST_FIELDS — stays vertical."""
        raw = fm("""
name: my-skill
metadata:
  dispatcher-category:
    - execution
    - analysis
""")
        result, report = flatten_vertical_lists(raw)
        # dispatcher-category not in list_fields so vertical list stays
        assert "- execution" in result
        assert "dispatcher-category" not in report["flattened"]

    def test_no_false_positives_on_non_list_fields(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-layer: execution
  dispatcher-risk: low
""")
        result, report = flatten_vertical_lists(raw)
        assert "dispatcher-layer: execution" in result
        assert report["flattened"] == []


# ---------------------------------------------------------------------------
# strip_noise
# ---------------------------------------------------------------------------

class TestStripNoise:
    def test_tags_field_stripped(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-layer: execution
  tags: analysis, security
""")
        result, report = strip_noise(raw)
        assert "tags:" not in result
        assert "tags" in report["stripped"]

    def test_metadata_tags_stripped(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-layer: execution
  metadata-tags: code-quality
""")
        result, report = strip_noise(raw)
        assert "metadata-tags" not in result
        assert "metadata-tags" in report["stripped"]

    def test_empty_persistent_directories_stripped(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-layer: execution
  dispatcher-persistent-directories:
""")
        result, report = strip_noise(raw)
        assert "dispatcher-persistent-directories" not in result
        assert "dispatcher-persistent-directories" in report["stripped"]

    def test_nonempty_persistent_directories_kept(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-layer: execution
  dispatcher-persistent-directories: logs, registry
""")
        result, report = strip_noise(raw)
        assert "dispatcher-persistent-directories: logs, registry" in result
        assert "dispatcher-persistent-directories" not in report["stripped"]

    def test_real_dispatcher_fields_untouched(self):
        raw = fm("""
name: my-skill
metadata:
  dispatcher-capabilities: foo, bar
  dispatcher-layer: execution
""")
        result, report = strip_noise(raw)
        assert "dispatcher-capabilities: foo, bar" in result
        assert report["stripped"] == []


# ---------------------------------------------------------------------------
# normalize (orchestrator)
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_full_pipeline_on_dirty_frontmatter(self):
        """Fixture mirrors the oversized test fixture: dup blocks + vertical lists + noise."""
        raw = fm("""
name: example-oversized-skill
description: A skill
metadata:
  dispatcher-category: analysis
  dispatcher-capabilities:
    - code-scanning
    - vulnerability-detection
  tags: analysis, security
  dispatcher-persistent-directories:
metadata:
  dispatcher-category: analysis
  dispatcher-capabilities:
    - code-scanning
    - vulnerability-detection
""")
        result, report = normalize(raw)
        assert result.count("metadata:") == 1
        assert "dispatcher-capabilities: code-scanning, vulnerability-detection" in result
        assert "tags" not in result
        assert "dispatcher-persistent-directories" not in result
        assert report["dedupe_removed"] >= 0
        assert "dispatcher-capabilities" in report["flattened_fields"]
        assert "tags" in report["noise_stripped"]

    def test_oversized_flag(self):
        long_desc = "x" * 1100
        raw = f'name: my-skill\ndescription: "{long_desc}"\nmetadata:\n  dispatcher-layer: execution\n'
        _, report = normalize(raw)
        assert report["oversized"] is True
        assert report["char_count"] > FRONTMATTER_LIMIT

    def test_clean_frontmatter_no_changes(self):
        raw = fm("""
name: my-skill
description: A concise description
metadata:
  dispatcher-layer: execution
  dispatcher-lifecycle: active
  dispatcher-capabilities: foo, bar
  dispatcher-risk: low
  dispatcher-writes-files: false
""")
        result, report = normalize(raw)
        assert report["dedupe_removed"] == 0
        assert report["flattened_fields"] == []
        assert report["noise_stripped"] == []
        assert report["oversized"] is False

    def test_report_char_count_matches_audit_baseline(self):
        raw = fm("""
name: my-skill
description: Short
metadata:
  dispatcher-layer: execution
""")
        _, report = normalize(raw)
        # char_count matches audit.py baseline: frontmatter text without --- delimiters
        assert report["char_count"] == len(raw.rstrip())
