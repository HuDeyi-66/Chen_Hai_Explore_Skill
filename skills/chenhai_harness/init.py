"""``init`` — create the controlled workspace from a TaskSpec.

Non-destructive by construction. The operation never deletes, never resets and
never repairs: if the target already exists with content it did not produce, the
answer is ``REFUSE``.

Idempotence is deliberate. Running ``init`` twice with the same TaskSpec
succeeds and changes nothing, because re-declaring the same room is not an
error. Running it with a *different* TaskSpec against an initialised workspace
refuses, because silently redefining a workspace that may already hold evidence
would destroy the audit trail the harness exists to protect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jsonio import atomic_write_json, dumps, read_json
from .outcomes import RefusalError
from .paths import UnsafePathError
from .taskspec import TaskSpec, parse_task_spec
from .workspace import WorkspaceLayout, layout_for


@dataclass(frozen=True)
class InitResult:
    """What ``init`` did."""

    workspace_root: str
    task_id: str
    created: bool
    created_directories: tuple[str, ...]
    task_spec_path: str
    already_initialised: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "operation": "init",
            "workspace_root": self.workspace_root,
            "task_id": self.task_id,
            "created": self.created,
            "already_initialised": self.already_initialised,
            "created_directories": list(self.created_directories),
            "task_spec_path": self.task_spec_path,
        }


def load_task_spec_file(path: Path) -> TaskSpec:
    """Read and validate a TaskSpec JSON file."""
    spec_path = Path(path)
    if not spec_path.is_file():
        raise RefusalError(f"task spec not found: {spec_path}")
    try:
        payload = read_json(spec_path)
    except ValueError as error:
        raise RefusalError(str(error)) from error
    try:
        return parse_task_spec(payload)
    except UnsafePathError as error:
        raise RefusalError(f"invalid task spec: {error}") from error


def _existing_entries(path: Path) -> list[str]:
    """Names of everything currently inside ``path``, for compatibility checks."""
    if not path.is_dir():
        return []
    return sorted(child.name for child in path.iterdir())


def _assert_compatible(workspace: WorkspaceLayout, spec: TaskSpec) -> bool:
    """Return True when the workspace is already initialised with ``spec``.

    Raises ``RefusalError`` when the target holds anything the harness must not
    overwrite.
    """
    root = workspace.root
    if not root.exists():
        return False
    if not root.is_dir():
        raise RefusalError(
            f"workspace root exists and is not a directory: {root}"
        )

    task_spec_path = workspace.task_spec_path
    if task_spec_path.is_file():
        try:
            existing_payload = read_json(task_spec_path)
        except ValueError as error:
            raise RefusalError(
                f"existing workspace has an unreadable TaskSpec; refusing to "
                f"overwrite it: {error}"
            ) from error
        try:
            existing_spec = parse_task_spec(existing_payload)
        except UnsafePathError as error:
            raise RefusalError(
                f"existing workspace has an invalid TaskSpec; refusing to "
                f"overwrite it: {error}"
            ) from error
        if existing_spec.to_json() != spec.to_json():
            raise RefusalError(
                f"workspace {root} is already initialised for a different task "
                f"spec (existing task_id={existing_spec.task_id!r}, "
                f"requested task_id={spec.task_id!r}); refusing to overwrite. "
                "Choose a different workspace_root or remove the workspace "
                "deliberately."
            )
        return True

    # No persisted TaskSpec. Only the layout this operation itself would create
    # is acceptable; anything else means the directory belongs to something
    # else.
    root_entries = _existing_entries(root)
    allowed_root = set(workspace.core_dirs())
    unexpected_root = sorted(set(root_entries) - allowed_root)
    if unexpected_root:
        raise RefusalError(
            f"workspace root {root} already contains content not created by the "
            f"harness: {', '.join(unexpected_root)}; refusing to use it"
        )

    for name, path in workspace.core_dirs().items():
        if not path.exists():
            continue
        if not path.is_dir():
            raise RefusalError(f"{name} exists and is not a directory: {path}")
        contents = _existing_entries(path)
        # An empty directory is what init itself creates, so it is safe to
        # adopt. A populated one is not: the contents are unreferenced by any
        # manifest and their provenance is unknown.
        if contents:
            raise RefusalError(
                f"{name}/ already contains unreferenced content: "
                f"{', '.join(contents)}; refusing to adopt it"
            )
    return False


def init_workspace(
    task_spec_path: Path | str,
    *,
    workspace_root: Path | str | None = None,
) -> InitResult:
    """Create (or confirm) the controlled workspace declared by a TaskSpec.

    ``workspace_root`` overrides the spec's own ``workspace_root``; it is used
    only by tests and by callers that relocate a portable spec. When it is
    given, the persisted TaskSpec records the override, so the workspace and its
    spec never disagree.
    """
    spec = load_task_spec_file(Path(task_spec_path))

    if workspace_root is not None:
        override = Path(workspace_root).resolve()
        spec = TaskSpec(
            schema_version=spec.schema_version,
            task_id=spec.task_id,
            topic=spec.topic,
            workspace_root=str(override),
            inputs=spec.inputs,
            expected_artifacts=spec.expected_artifacts,
        )

    workspace = layout_for(spec.workspace_root)
    already_initialised = _assert_compatible(workspace, spec)

    created_directories: list[str] = []
    for name, path in workspace.core_dirs().items():
        if not path.exists():
            path.mkdir(parents=True, exist_ok=False)
            created_directories.append(name)

    persisted = dumps(spec.to_json())
    existing_text = (
        workspace.task_spec_path.read_text(encoding="utf-8")
        if workspace.task_spec_path.is_file()
        else None
    )
    if existing_text != persisted:
        atomic_write_json(workspace.task_spec_path, spec.to_json())

    return InitResult(
        workspace_root=str(workspace.root),
        task_id=spec.task_id,
        created=not already_initialised,
        created_directories=tuple(sorted(created_directories)),
        task_spec_path=str(workspace.task_spec_path),
        already_initialised=already_initialised,
    )


def load_persisted_task_spec(workspace_root: Path | str) -> tuple[TaskSpec, dict[str, Any]]:
    """Load the persisted TaskSpec for a workspace.

    Returns the validated object plus the raw decoded document, so ``validate``
    can compare the stored bytes meaningfully rather than only re-parsing them.
    """
    workspace = layout_for(workspace_root)
    path = workspace.task_spec_path
    if not path.is_file():
        raise RefusalError(
            f"workspace is not initialised: {path} does not exist"
        )
    try:
        raw = read_json(path)
    except ValueError as error:
        raise RefusalError(str(error)) from error
    try:
        spec = parse_task_spec(raw)
    except UnsafePathError as error:
        raise RefusalError(f"persisted task spec is invalid: {error}") from error
    return spec, raw


__all__ = [
    "InitResult",
    "init_workspace",
    "load_persisted_task_spec",
    "load_task_spec_file",
]
