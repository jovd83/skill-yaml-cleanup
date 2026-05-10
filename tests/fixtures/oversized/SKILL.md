---
name: example-oversized-skill
description: "This is an extremely long description that goes on and on about all the things this skill can do including scanning repositories for issues and analyzing code quality and checking for vulnerabilities and generating reports and sending notifications and much more functionality that nobody needs in a description field."
license: MIT
author: test-author
version: 1.0.0
maturity: stable
compatibility: "Requires Python 3.10+"
homepage: https://example.com
metadata:
  dispatcher-category: analysis
  dispatcher-capabilities:
    - code-scanning
    - vulnerability-detection
    - report-generation
    - notification-sending
    - dashboard-rendering
  dispatcher-accepted-intents:
    - scan_code
    - check_vulnerabilities
    - generate_report
  dispatcher-input-artifacts: source_code, config_files
  dispatcher-output-artifacts: scan_report, vulnerability_list
  dispatcher-stack-tags: python, security, analysis
  dispatcher-risk: low
  dispatcher-writes-files: false
  dispatcher-layer: execution
  dispatcher-lifecycle: active
  tags: analysis, security, scanning
  metadata-tags: code-quality
  dispatcher-persistent-directories:
metadata:
  dispatcher-category: analysis
  dispatcher-capabilities:
    - code-scanning
    - vulnerability-detection
---

# Example Oversized Skill

This is a test fixture with multiple issues:
- Oversized description
- Duplicate metadata blocks
- Vertical lists
- Noise fields (tags, metadata-tags, empty dispatcher-persistent-directories)
- Migratable fields (license, author, version, maturity, compatibility, homepage)
