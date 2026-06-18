# WFERP Report Designs

This directory contains reusable product report design contracts for WFERP report generation.

`index.json` is the canonical catalog order and allowlist. `skill_scripts/report_catalog.py` rejects missing profile files, unindexed profile IDs, and profiles missing required product metadata.

Each concrete design declares machine-readable front matter for the harness, renderer, report scaffold, and validators, followed by human guidance for section writing and review.
