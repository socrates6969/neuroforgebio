"""Print the API contract and the authz matrix as one JSON object on stdout.

Used by ``apps/console/scripts/gen-api.mjs`` (and its drift test). Since M4 (4.1) the source is the
committed contract ``openapi/v1.yaml`` (itself drift-tested against the FastAPI app by
``services/platform/tests/api/test_api_openapi.py``), so the console client, the SDK and the docs
all derive from the same file. The authz matrix still comes from ``nf_platform.auth.authorize``.
No server, no database and no IdP are involved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from nf_platform.auth import authorize

SPEC = Path(__file__).resolve().parents[3] / "openapi" / "v1.yaml"


def main() -> int:
    doc = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    authz = {
        "roles": list(authorize.ROLES),
        "adminClass": sorted(authorize.ADMIN_CLASS),
        "quarantineReaders": sorted(authorize.QUARANTINE_READERS),
        "permissions": {k: sorted(v) for k, v in sorted(authorize.PERMISSIONS.items())},
    }
    json.dump({"openapi": doc, "authz": authz}, sys.stdout, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
