"""Shared test helpers for the ChenHai harness suite.

Kept as a plain module rather than a ``conftest.py`` because this repository runs
its suite with ``unittest`` discovery as well as with ``pytest``, and a shared
helper must work under both. Nothing here is named ``test_*`` and no class is
named ``Test*``, so importing this module never produces phantom tests.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

#: This package's own directory, put on the path so ``import _bootstrap`` works
#: when pytest imports this module by its package-qualified name.
_TESTS_DIR = str(Path(__file__).resolve().parent.parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import _bootstrap  # noqa: E402  (path bootstrap must run before skills imports)

BOOTSTRAP = _bootstrap


def minimal_spec(workspace_root: Path, **overrides: Any) -> dict[str, Any]:
    """A complete, valid TaskSpec document for ``workspace_root``.

    Callers override individual fields to build the invalid variants, so every
    negative test differs from a known-good document in exactly one place.
    """
    root = Path(workspace_root).resolve()
    spec: dict[str, Any] = {
        "schema_version": "0.1",
        "task_id": "M03_R2",
        "topic": "missing_authority",
        "workspace_root": str(root),
        "inputs": [
            {
                "source_path": str((root.parent / "dossier").resolve()),
                "destination": "input/dossier",
                "mode": "copy",
            }
        ],
        "expected_artifacts": [
            {
                "artifact_role": "final_answer",
                "topic": "legal_analysis",
                "extension": ".md",
                "required": True,
            }
        ],
    }
    spec.update(overrides)
    return spec


def write_spec(path: Path, spec: dict[str, Any]) -> Path:
    """Write a TaskSpec document and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def make_dossier(root: Path, files: dict[str, str]) -> Path:
    """Create a synthetic input tree and return its root.

    Files are written as bytes with no newline translation, so a fixture is
    byte-identical on every platform and a digest assertion in a test cannot
    fail merely because the host rewrites ``\\n`` as ``\\r\\n``.
    """
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    return root


def sha256_of(payload: bytes) -> str:
    """Independent digest helper, so manifest checks are not self-confirming."""
    return BOOTSTRAP.sha256_of(payload)


def read_json_file(path: Path) -> Any:
    """Read a JSON document from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def deep_copy(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy a decoded JSON document."""
    return copy.deepcopy(payload)


__all__ = [
    "BOOTSTRAP",
    "deep_copy",
    "make_dossier",
    "minimal_spec",
    "read_json_file",
    "sha256_of",
    "write_spec",
]
