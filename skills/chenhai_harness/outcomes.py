"""Refusal and completeness signalling for the ChenHai evidence discipline
harness.

The harness has exactly three terminal outcomes, and they are distinct on
purpose:

``PASS``
    Everything declared was produced, and every recorded digest still matches.

``INCOMPLETE``
    The workspace is itself sound, but required artifacts are simply not there
    yet. This is a scheduling fact, not an integrity failure.

``REFUSE``
    Something is wrong that the harness will not paper over: an invalid spec, an
    unsafe path, a naming violation, a corrupt or missing manifest, a digest
    mismatch, or a collision. Refusing is always preferred to guessing.

Collapsing ``INCOMPLETE`` into ``REFUSE`` would make "not finished yet"
indistinguishable from "tampered with"; collapsing ``REFUSE`` into a warning
would let an unusable workspace be reported as usable. Both are why the two are
separate exception types with separate exit codes.
"""

from __future__ import annotations

from typing import Any

#: Terminal statuses, also written into ``checks/validation_report.json``.
PASS = "PASS"
INCOMPLETE = "INCOMPLETE"
REFUSE = "REFUSE"

#: Process exit codes, documented in ``README.md``.
EXIT_OK = 0
EXIT_INTERNAL_ERROR = 1
EXIT_INCOMPLETE = 2
EXIT_REFUSE = 3

STATUS_EXIT_CODES = {
    PASS: EXIT_OK,
    INCOMPLETE: EXIT_INCOMPLETE,
    REFUSE: EXIT_REFUSE,
}


class RefusalError(Exception):
    """An integrity or safety violation. Corresponds to ``REFUSE``."""

    def __init__(self, message: str, *, errors: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.errors = errors or (message,)


class IncompleteError(Exception):
    """Required artifacts are absent. Corresponds to ``INCOMPLETE``."""

    def __init__(self, message: str, *, missing: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.missing = missing


def make_report(
    *,
    task_id: str,
    status: str,
    missing_required_artifacts: list[str] | None = None,
    unexpected_output_files: list[str] | None = None,
    naming_violations: list[str] | None = None,
    hash_mismatches: list[str] | None = None,
    integrity_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build a machine-readable validation report.

    Every collection is always present, even when empty, so that a consumer can
    read a field without checking for its existence. All collections are sorted
    so that two runs over the same workspace produce identical reports.
    """

    def _sorted(values: list[str] | None) -> list[str]:
        return sorted(values) if values else []

    return {
        "schema_version": "0.1",
        "task_id": task_id,
        "status": status,
        "missing_required_artifacts": _sorted(missing_required_artifacts),
        "unexpected_output_files": _sorted(unexpected_output_files),
        "naming_violations": _sorted(naming_violations),
        "hash_mismatches": _sorted(hash_mismatches),
        "integrity_errors": _sorted(integrity_errors),
    }
