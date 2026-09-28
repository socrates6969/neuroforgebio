"""The published v1 pipelines of the step library (PipelineVersion documents, hashing.md §5.1).

``image`` is a placeholder digest on the ``registry.invalid`` domain until the step image is built
and signed in CI (SEC-044); the container runner refuses it, the local runners ignore it.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

PLACEHOLDER_IMAGE = "registry.invalid/nf-steps@sha256:" + "0" * 64
# The step image's command: ``nf-step run --step <ref> --params ... --seed ... --in ... --out ...``.
ENTRYPOINT = ("nf-step", "run")


def names() -> list[str]:
    return sorted(
        p.name[: -len(".json")]
        for p in resources.files(__name__).iterdir()
        if p.name.endswith(".json")
    )


def load(name: str) -> dict[str, Any]:
    return json.loads(resources.files(__name__).joinpath(f"{name}.json").read_text("utf-8"))


def all_specs() -> list[dict[str, Any]]:
    return [load(n) for n in names()]
