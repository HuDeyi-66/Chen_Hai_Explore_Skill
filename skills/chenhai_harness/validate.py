"""``validate`` — the completeness and integrity gate.

Checks, in the order the specification lists them:

A. TaskSpec integrity — the persisted spec exists, parses, and still declares
   exactly what this workspace was initialised for.
B. workspace layout — the four core directories exist.
C. expected required artifacts — every ``required: true`` entry is present.
D. canonical filename compliance — every file in ``output/`` is named by the
   rule, for a role and topic the spec actually declares.
E. expected location — each declared artifact sits directly in ``output/``.
F. manifest/file hash consistency — every recorded digest re-computes, on both
   the input and the output manifest.
G. unexpected files inside the controlled output directory.
H. path-boundary violations detectable from workspace state — the workspace root
   and the managed directories must not resolve outside the boundary they claim.

Result:

``PASS``
    All required artifacts present, named correctly, and hash-consistent.
``INCOMPLETE``
    The workspace is otherwise sound but required artifacts are absent.
``REFUSE``
    Anything else: invalid spec, unsafe path, naming violation, manifest
    corruption, hash mismatch, collision, or an unexpected file in ``output/``.

Precedence: ``REFUSE`` outranks ``INCOMPLETE``. A workspace that has both a
tampered manifest and a missing artifact is reported as ``REFUSE``, because the
integrity problem must be resolved before "how much is left to do" is even a
meaningful question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .init import load_persisted_task_spec
from .jsonio import read_json
from .outcomes import (
    INCOMPLETE,
    PASS,
    REFUSE,
    IncompleteError,
    RefusalError,
    make_report,
)
from .paths import UnsafePathError, as_posix_relative, resolve_under
from .workspace import (
    MANIFEST_SCHEMA_VERSION,
    WorkspaceLayout,
    layout_for,
)


@dataclass
class ValidationFindings:
    """Accumulated findings, grouped exactly as the report groups them."""

    missing_required_artifacts: list[str] = field(default_factory=list)
    unexpected_output_files: list[str] = field(default_factory=list)
    naming_violations: list[str] = field(default_factory=list)
    hash_mismatches: list[str] = field(default_factory=list)
    integrity_errors: list[str] = field(default_factory=list)

    @property
    def has_integrity_problem(self) -> bool:
        """True when the finding set forces ``REFUSE`` regardless of completeness."""
        return bool(
            self.integrity_errors
            or self.hash_mismatches
            or self.naming_violations
            or self.unexpected_output_files
        )


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of ``validate``, plus where the report was written."""

    status: str
    report: dict[str, Any]
    report_path: str

    def to_json(self) -> dict[str, Any]:
        return self.report


def _check_layout(workspace: WorkspaceLayout, findings: ValidationFindings) -> None:
    """Check B: the four core directories are present."""
    missing = workspace.missing_core_dirs()
    if missing:
        findings.integrity_errors.append(
            "workspace layout is incomplete; missing director(ies): "
            + ", ".join(missing)
        )


def _check_path_boundaries(
    workspace: WorkspaceLayout, findings: ValidationFindings
) -> None:
    """Check H: the workspace and its managed directories stay where they claim.

    ``workspace.root`` is already resolved, so no re-normalisation of the root
    itself is needed and none is done: that would compare a resolved path with
    a resolved path and prove nothing. What *is* checked is the one boundary
    violation observable purely from workspace state — a core directory that
    resolves inside the workspace but is physically located somewhere else,
    which is exactly the case where a later ``place`` would write outside the
    declared room.
    """
    root = workspace.root
    for name, path in workspace.core_dirs().items():
        if not path.exists():
            continue
        try:
            resolved = path.resolve(strict=False)
        except OSError as error:  # pragma: no cover - defensive
            findings.integrity_errors.append(f"{name}/ is unresolvable: {error}")
            continue
        if resolved != path or (resolved != root and root not in resolved.parents):
            findings.integrity_errors.append(
                f"path boundary: {name}/ resolves away from its declared "
                f"location inside the workspace ({path} -> {resolved})"
            )


def _check_task_spec(
    workspace: WorkspaceLayout, findings: ValidationFindings
) -> tuple[Any, dict[str, Any]] | None:
    """Check A: the persisted TaskSpec exists, parses, and is self-consistent."""
    path = workspace.task_spec_path
    if not path.is_file():
        findings.integrity_errors.append(
            f"TaskSpec integrity: {path} is missing; the workspace is not initialised"
        )
        return None
    try:
        raw = read_json(path)
    except ValueError as error:
        findings.integrity_errors.append(f"TaskSpec integrity: {error}")
        return None
    if not isinstance(raw, dict):
        findings.integrity_errors.append(
            "TaskSpec integrity: persisted document is not a JSON object"
        )
        return None
    try:
        spec, _ = load_persisted_task_spec(workspace.root)
    except RefusalError as error:
        findings.integrity_errors.append(f"TaskSpec integrity: {error}")
        return None

    if raw.get("workspace_root") != str(workspace.root):
        findings.integrity_errors.append(
            "TaskSpec integrity: persisted workspace_root "
            f"{raw.get('workspace_root')!r} does not match the workspace being "
            f"validated ({workspace.root})"
        )
    return spec, raw


def _check_output_names(
    workspace: WorkspaceLayout, spec: Any, findings: ValidationFindings
) -> None:
    """Checks D, E and G: naming compliance and unexpected files in ``output/``."""
    expected_by_filename = {
        expected.canonical_filename(spec.task_id): expected
        for expected in spec.expected_artifacts
    }

    if not workspace.output_dir.is_dir():
        return

    for child in sorted(workspace.output_dir.iterdir(), key=lambda item: item.name):
        relative = as_posix_relative(child.relative_to(workspace.root))
        if child.is_dir():
            findings.unexpected_output_files.append(
                f"{relative} (directory: the controlled output area is flat)"
            )
            continue
        if child.name not in expected_by_filename:
            if _looks_canonical(child.name):
                findings.naming_violations.append(
                    f"{relative} (canonical shape, but not a declared "
                    "artifact_role/topic/extension for this task)"
                )
            else:
                findings.unexpected_output_files.append(
                    f"{relative} (not a declared artifact and not a canonical "
                    "harness filename)"
                )


def _looks_canonical(filename: str) -> bool:
    """Heuristic used only to classify a finding, never to accept a file."""
    stem = filename.rsplit(".", 1)[0]
    return stem.count("__") == 2


def _check_required_artifacts(
    workspace: WorkspaceLayout, spec: Any, findings: ValidationFindings
) -> None:
    """Check C: each required artifact is present under its canonical name."""
    for expected in spec.expected_artifacts:
        filename = expected.canonical_filename(spec.task_id)
        target = workspace.output_dir / filename
        if target.is_file():
            if target.parent.resolve(strict=False) != workspace.output_dir.resolve(
                strict=False
            ):
                findings.naming_violations.append(
                    f"{filename} (declared artifact is not directly in output/)"
                )
            continue
        if expected.required:
            findings.missing_required_artifacts.append(filename)


def _staged_input_files(workspace: WorkspaceLayout) -> list[str]:
    """Workspace-relative paths of every file currently under ``input/``."""
    if not workspace.input_dir.is_dir():
        return []
    return sorted(
        as_posix_relative(path.relative_to(workspace.root))
        for path in workspace.input_dir.rglob("*")
        if path.is_file()
    )


def _produced_output_files(workspace: WorkspaceLayout) -> list[str]:
    """Workspace-relative paths of every file currently under ``output/``.

    ``checks/validation_report.json`` is deliberately not consulted, and neither
    is ``manifests/``: only the controlled output area decides whether a
    manifest is expected to exist yet.
    """
    if not workspace.output_dir.is_dir():
        return []
    return sorted(
        as_posix_relative(path.relative_to(workspace.root))
        for path in workspace.output_dir.rglob("*")
        if path.is_file()
    )


def _check_manifest(
    *,
    manifest_path: Path,
    collection_key: str,
    label: str,
    findings: ValidationFindings,
    base_dir: Path,
    absent_is_error: bool = True,
) -> None:
    """Check F: every entry in a manifest still matches the file it describes.

    ``absent_is_error=False`` is used for the input manifest, which is genuinely
    optional while nothing has been staged: a freshly initialised workspace has
    no staged input and therefore nothing to record. Once content exists under
    ``input/``, that content must be accounted for, so the absent manifest
    becomes an integrity error. ``validate`` decides which case applies and
    passes the answer in, rather than this function guessing.
    """
    if not manifest_path.is_file():
        if absent_is_error:
            findings.integrity_errors.append(
                f"{label} manifest is missing: {manifest_path.name}"
            )
        return
    try:
        document = read_json(manifest_path)
    except ValueError as error:
        findings.integrity_errors.append(f"{label} manifest is unreadable: {error}")
        return
    if not isinstance(document, dict):
        findings.integrity_errors.append(
            f"{label} manifest is not a JSON object: {manifest_path}"
        )
        return
    if document.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        findings.integrity_errors.append(
            f"{label} manifest has an unexpected schema_version: "
            f"{document.get('schema_version')!r}"
        )
    entries = document.get(collection_key)
    if not isinstance(entries, list):
        findings.integrity_errors.append(
            f"{label} manifest has no '{collection_key}' array: {manifest_path}"
        )
        return

    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            findings.integrity_errors.append(
                f"{label} manifest entry #{position} is not a JSON object"
            )
            continue
        relative = entry.get("relative_path")
        recorded = entry.get("sha256_lower")
        if not isinstance(relative, str) or not relative:
            findings.integrity_errors.append(
                f"{label} manifest entry #{position} has no relative_path"
            )
            continue
        if not isinstance(recorded, str) or len(recorded) != 64:
            findings.integrity_errors.append(
                f"{label} manifest entry {relative!r} has no usable sha256_lower"
            )
            continue

        try:
            target = resolve_under(
                base_dir, base_dir / relative, field=f"{label} manifest entry {relative!r}"
            )
        except UnsafePathError as error:
            findings.integrity_errors.append(
                f"{label} manifest entry escapes the workspace: {error}"
            )
            continue

        if not target.is_file():
            findings.hash_mismatches.append(
                f"{relative} (recorded in {manifest_path.name} but missing on disk)"
            )
            continue
        actual = sha256_file(target)
        if actual != recorded:
            findings.hash_mismatches.append(
                f"{relative} (sha256 {actual} != recorded {recorded})"
            )
        recorded_size = entry.get("size_bytes")
        if isinstance(recorded_size, int) and recorded_size != target.stat().st_size:
            findings.hash_mismatches.append(
                f"{relative} (size {target.stat().st_size} != recorded {recorded_size})"
            )


def _declared_identity(
    manifest_path: Path, *, label: str
) -> tuple[str | None, str | None]:
    """Return ``(task_id, problem)`` from a manifest's recorded identity.

    The manifests record which task produced them. Comparing that against the
    persisted TaskSpec is the only check that catches a TaskSpec rewritten after
    the fact: the spec is the input to validation, so a tampered ``task_id``
    would otherwise simply redefine what "correct" means. The manifest was
    written by a different, earlier run and still carries the original identity.
    """
    if not manifest_path.is_file():
        return None, None
    try:
        document = read_json(manifest_path)
    except ValueError:
        # Already reported by the hash check; do not double-report here.
        return None, None
    if not isinstance(document, dict):
        return None, None
    recorded = document.get("task_id")
    if not isinstance(recorded, str):
        return None, f"{manifest_path.name} records no task_id"
    return recorded, None


def _check_spec_identity_consistency(
    workspace: WorkspaceLayout, spec: Any, findings: ValidationFindings
) -> None:
    """Check A (continued): the spec still matches what the manifests recorded."""
    for manifest_path, label in (
        (workspace.input_manifest_path, "input"),
        (workspace.output_manifest_path, "output"),
    ):
        recorded, problem = _declared_identity(manifest_path, label=label)
        if problem:
            findings.integrity_errors.append(f"TaskSpec identity: {problem}")
            continue
        if recorded is None:
            continue
        if recorded != spec.task_id:
            findings.integrity_errors.append(
                f"TaskSpec identity: the persisted TaskSpec declares "
                f"task_id={spec.task_id!r} but {manifest_path.name} was produced "
                f"for task_id={recorded!r}; the TaskSpec was modified after this "
                "workspace was built"
            )


def validate_workspace(
    workspace_root: Path | str,
    *,
    write_report: bool = True,
) -> ValidationResult:
    """Validate a controlled workspace and optionally write the check report.

    The report is written for every outcome, including ``REFUSE``, so a refused
    run still leaves machine-readable evidence of why it was refused.
    """
    workspace = layout_for(workspace_root)
    findings = ValidationFindings()
    task_id = ""

    _check_layout(workspace, findings)
    _check_path_boundaries(workspace, findings)

    loaded = _check_task_spec(workspace, findings)
    if loaded is not None:
        spec, _ = loaded
        task_id = spec.task_id
        _check_output_names(workspace, spec, findings)
        _check_required_artifacts(workspace, spec, findings)
        _check_spec_identity_consistency(workspace, spec, findings)
        _check_manifest(
            manifest_path=workspace.input_manifest_path,
            collection_key="entries",
            label="input",
            findings=findings,
            base_dir=workspace.root,
            # Optional until something is actually staged, then mandatory.
            absent_is_error=bool(_staged_input_files(workspace)),
        )
        _check_manifest(
            manifest_path=workspace.output_manifest_path,
            collection_key="artifacts",
            label="output",
            findings=findings,
            # Manifest paths are workspace-relative for both manifests, so the
            # base is the workspace root in both cases. Using output/ here would
            # look for output/output/<name> and report a spurious mismatch.
            base_dir=workspace.root,
            # Optional until something has actually been placed, then mandatory:
            # a file in output/ that no manifest accounts for is unreferenced.
            absent_is_error=bool(_produced_output_files(workspace)),
        )
    else:
        # With no trustworthy TaskSpec there is nothing to compare against, but
        # the output area can still be reported on.
        findings.integrity_errors.append(
            "output area was not checked for completeness because the TaskSpec "
            "could not be trusted"
        )

    if findings.has_integrity_problem:
        status = REFUSE
    elif findings.missing_required_artifacts:
        status = INCOMPLETE
    else:
        status = PASS

    report = make_report(
        task_id=task_id,
        status=status,
        missing_required_artifacts=findings.missing_required_artifacts,
        unexpected_output_files=findings.unexpected_output_files,
        naming_violations=findings.naming_violations,
        hash_mismatches=findings.hash_mismatches,
        integrity_errors=findings.integrity_errors,
    )

    report_path = workspace.validation_report_path
    if write_report and workspace.checks_dir.is_dir():
        from .jsonio import atomic_write_json

        atomic_write_json(report_path, report)

    return ValidationResult(
        status=status, report=report, report_path=str(report_path)
    )


__all__ = [
    "IncompleteError",
    "RefusalError",
    "ValidationFindings",
    "ValidationResult",
    "validate_workspace",
]
