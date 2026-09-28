"""Print the ``content_sha256`` of the RuleSet in ``rules/`` (for the manifest after an edit)."""

from __future__ import annotations

import sys

from nf_platform.governance import rules

if __name__ == "__main__":
    rs = rules.load(sys.argv[1] if len(sys.argv) > 1 else None, check_hash=False)
    print(rs.content_sha256)
