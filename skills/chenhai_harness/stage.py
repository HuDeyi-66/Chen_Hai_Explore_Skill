"""``stage`` — copy declared inputs into the workspace and hash them.

Only ``mode = "copy"`` is implemented. Sources are never moved, never
rewritten and never opened for writing: staging is a read of the source and a
write to a new destination inside ``input/``.

Guarantees:

* both single files and directories (recursively) are supported;
* every staged file is recorded with its size and SHA-256;
* entries are sorted, so the manifest is reproducible;
* a missing source is a refusal, never a silently smaller manifest;
* a destination that already exists with different bytes is a refusal, never an
  overwrite;
* symlinks are skipped rather than followed, so a link cannot pull content from
  outside the declared source tree.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .init import load_persisted_task_spec
from .jsonio import atomic_write_json, read_json
from .outcomes import RefusalError
from .paths import UnsafePathError, as_posix_relative, resolve_under
from .workspace import WorkspaceLayout, layout_for, make_input_manifest


@dataclass(frozen=True)
class StageResult:
    """What ``stage`` did."""

    workspace_root: str
    task_id: str
    copied: tuple[str, ...]
    already_present: tuple[str, ...]
    entry_count: int
    skipped_symlinks: tuple[str, ...]
    input_manifest_path: str

    def to_json(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "operation": "stage",
            "workspace_root": self.workspace_root,
            "task_id": self.task_id,
            "entry_count": self.entry_count,
            "copied": list(self.copied),
            "already_present": list(self.already_present),
            "skipped_symlinks": list(self.skipped_symlinks),
            "input_manifest_path": self.input_manifest_path,
        }


def _collect_source_files(
    source: Path,
) -> tuple[list[tuple[Path, str]], list[str]]:
    """Expand a declared source into (file, relative-within-source) pairs.

    Returns the files to stage and the symlinks that were skipped, both sorted
    deterministically. Directories are walked recursively.
    """
    files: list[tuple[Path, str]] = []
    skipped: list[str] = []

    if source.is_symlink():
        return [], [str(source)]

    if source.is_file():
        return [(source, "")], []

    if not source.is_dir():
        raise RefusalError(f"declared input source is neither a file nor a directory: {source}")

    for candidate in sorted(source.rglob("*")):
        if candidate.is_symlink():
            skipped.append(str(candidate))
            continue
        if candidate.is_file():
            relative = candidate.relative_to(source)
            files.append((candidate, as_posix_relative(relative)))

    files.sort(key=lambda item: item[1])
    skipped.sort()
    return files, skipped


def stage_workspace(workspace_root: Path | str) -> StageResult:
    """Stage every declared input and write ``manifests/input_manifest.json``."""
    spec, _ = load_persisted_task_spec(workspace_root)
    workspace = layout_for(spec.workspace_root)
    if not workspace.input_dir.is_dir():
        raise RefusalError(
            f"workspace layout is incomplete: {workspace.input_dir} does not exist"
        )

    # Checked before any new work: a corrupted manifest must stop the operation
    # before it writes anything, not after.
    _existing_manifest_entries(workspace)

    entries: list[dict[str, object]] = []
    copied: list[str] = []
    already_present: list[str] = []
    skipped_symlinks: list[str] = []

    for declaration in spec.inputs:
        source = declaration.resolve_source(workspace.root)
        if not source.exists() and not source.is_symlink():
            raise RefusalError(
                f"inputs[{declaration.index}].source_path does not exist: {source}"
            )

        destination_root = _safe_destination(
            workspace, declaration.destination_relative, index=declaration.index
        )

        files, skipped = _collect_source_files(source)
        skipped_symlinks.extend(skipped)
        if not files:
            raise RefusalError(
                f"inputs[{declaration.index}].source_path contains no files to "
                f"stage: {source}"
            )

        for file_path, relative in files:
            target = (
                destination_root / relative if relative else destination_root
            )
            target = _safe_target(workspace, target, source=file_path)
            relative_path = as_posix_relative(target.relative_to(workspace.root))

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.is_dir():
                    raise RefusalError(
                        f"staging destination is an existing directory: {target}"
                    )
                if sha256_file(target) != sha256_file(file_path):
                    raise RefusalError(
                        f"staging destination already exists with different "
                        f"content: {target}; refusing to overwrite it"
                    )
                already_present.append(relative_path)
            else:
                shutil.copyfile(file_path, target)
                copied.append(relative_path)

            entries.append(
                {
                    "relative_path": relative_path,
                    "size_bytes": target.stat().st_size,
                    "sha256_lower": sha256_file(target),
                    "source_path": str(file_path),
                    "mode": declaration.mode,
                }
            )

    entries.sort(key=lambda entry: str(entry["relative_path"]))
    document = make_input_manifest(task_id=spec.task_id, entries=entries)
    atomic_write_json(workspace.input_manifest_path, document)

    return StageResult(
        workspace_root=str(workspace.root),
        task_id=spec.task_id,
        copied=tuple(sorted(copied)),
        already_present=tuple(sorted(already_present)),
        entry_count=len(entries),
        skipped_symlinks=tuple(sorted(skipped_symlinks)),
        input_manifest_path=str(workspace.input_manifest_path),
    )


def _existing_manifest_entries(workspace: WorkspaceLayout) -> list[Any]:
    """Read an existing input manifest, refusing if it is unusable."""
    path = workspace.input_manifest_path
    if not path.is_file():
        return []
    try:
        document = read_json(path)
    except ValueError as error:
        raise RefusalError(
            f"existing input manifest is unreadable; refusing to replace it: {error}"
        ) from error
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise RefusalError(
            f"existing input manifest at {path} does not have the expected shape; "
            "refusing to replace it"
        )
    return list(document["entries"])


def _safe_destination(workspace: WorkspaceLayout, relative: str, *, index: int) -> Path:
    """Resolve a declared destination inside ``input/``, refusing escapes."""
    candidate = workspace.root / relative
    try:
        resolved = resolve_under(
            workspace.input_dir, candidate, field=f"inputs[{index}].destination"
        )
    except UnsafePathError as error:
        raise RefusalError(str(error)) from error
    return resolved


def _safe_target(workspace: WorkspaceLayout, target: Path, *, source: Path) -> Path:
    """Prove a concrete staging target is still inside ``input/``."""
    try:
        return resolve_under(workspace.input_dir, target, field=f"staging target for {source}")
    except UnsafePathError as error:
        raise RefusalError(str(error)) from error


__all__ = ["StageResult", "stage_workspace"]
