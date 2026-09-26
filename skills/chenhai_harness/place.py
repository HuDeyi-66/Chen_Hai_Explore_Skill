"""``place`` — put an already-produced artifact into the controlled output area.

The caller says what the artifact *is* (role, topic) and where its bytes
currently are. The harness decides the name and the location, copies the bytes,
hashes them and records them. It never inspects the content to guess a name, and
it never judges whether the content is any good: ``place`` moves evidence into
the controlled area, it does not evaluate it.

Ordering matters and is deliberate:

1. validate the source and the name;
2. copy to a temporary sibling of the destination;
3. hash the temporary file;
4. rename the temporary file onto the canonical name (atomic);
5. merge and write the output manifest (atomic, and always last).

The manifest is written last so it describes files that are already in place.
A failure before step 5 leaves an unrecorded file rather than a manifest
pointing at something that does not exist; ``validate`` treats such an orphan as
an integrity violation, which is the honest outcome.

Concurrency note: the temp-then-rename pattern is atomic against crashes and
partial writes, not against two concurrent ``place`` calls racing on the same
manifest. Serialising concurrent writers is out of scope for this MVP and is
stated as a limitation rather than pretended away.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hashing import files_are_identical, sha256_file
from .init import load_persisted_task_spec
from .jsonio import atomic_write_json, read_json
from .naming import (
    canonical_filename,
    extract_extension,
    normalize_component,
    normalize_extension,
)
from .outcomes import RefusalError
from .paths import UnsafePathError, as_posix_relative, resolve_under
from .workspace import WorkspaceLayout, layout_for, make_output_manifest


@dataclass(frozen=True)
class PlaceResult:
    """What ``place`` did."""

    workspace_root: str
    task_id: str
    artifact_role: str
    topic: str
    filename: str
    relative_path: str
    size_bytes: int
    sha256_lower: str
    idempotent: bool
    output_manifest_path: str

    def to_json(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "operation": "place",
            "workspace_root": self.workspace_root,
            "task_id": self.task_id,
            "artifact_role": self.artifact_role,
            "topic": self.topic,
            "filename": self.filename,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256_lower": self.sha256_lower,
            "idempotent": self.idempotent,
            "output_manifest_path": self.output_manifest_path,
        }


def _resolve_extension(
    *, explicit: str | None, source: Path, artifact_role: str
) -> str:
    """Use the explicit extension when given, otherwise infer it from the source.

    Inference is limited to the source *filename*. Content sniffing is never
    performed, so a mislabelled file keeps its declared label instead of being
    silently reclassified by the harness.
    """
    if explicit is not None:
        try:
            return normalize_extension(explicit, field="extension")
        except UnsafePathError as error:
            raise RefusalError(str(error)) from error
    try:
        return extract_extension(source.name, field="extension")
    except UnsafePathError as error:
        raise RefusalError(
            f"{error} (artifact_role={artifact_role!r})"
        ) from error


def _normalized_role_and_topic(
    *, artifact_role: str, topic: str
) -> tuple[str, str]:
    try:
        normalized_role = normalize_component(artifact_role, field="artifact_role")
        normalized_topic = normalize_component(topic, field="topic")
    except UnsafePathError as error:
        raise RefusalError(str(error)) from error
    return normalized_role, normalized_topic


def _read_output_manifest(workspace: WorkspaceLayout) -> list[dict[str, Any]]:
    """Read the existing output manifest, refusing if it is unusable."""
    path = workspace.output_manifest_path
    if not path.is_file():
        return []
    try:
        document = read_json(path)
    except ValueError as error:
        raise RefusalError(
            f"existing output manifest is unreadable; refusing to replace it: {error}"
        ) from error
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise RefusalError(
            f"existing output manifest at {path} does not have the expected shape; "
            "refusing to replace it"
        )
    artifacts: list[dict[str, Any]] = []
    for item in document["artifacts"]:
        if not isinstance(item, dict) or "relative_path" not in item:
            raise RefusalError(
                f"existing output manifest at {path} has a malformed artifact "
                "entry; refusing to replace it"
            )
        artifacts.append(dict(item))
    return artifacts


def _matching_declaration(
    spec: Any, *, artifact_role: str, topic: str, extension: str
) -> Any | None:
    """Return the TaskSpec declaration this artifact matches, or ``None``.

    Identity is the MVP-declared triple — ``artifact_role``, ``topic`` and
    ``extension`` — compared through the *same* normalisation that builds the
    canonical filename, so a declaration cannot appear to match through one code
    path and fail to match through the other.

    Only the declaration supplies these three values, and each expected artifact
    is already validated and unique by canonical filename at TaskSpec parse time,
    so at most one declaration can match and no disambiguation is needed.
    """
    for expected in spec.expected_artifacts:
        if (
            normalize_component(expected.artifact_role, field="artifact_role")
            == artifact_role
            and normalize_component(expected.topic, field="topic") == topic
            and normalize_extension(expected.extension) == extension
        ):
            return expected
    return None


def _declared_identities(spec: Any) -> str:
    """Render the declared artifact identities for a refusal message."""
    if not spec.expected_artifacts:
        return "  (TaskSpec declares no expected_artifacts)"
    lines = []
    for expected in spec.expected_artifacts:
        lines.append(
            f"  - artifact_role={expected.artifact_role!r} "
            f"topic={expected.topic!r} extension={expected.extension!r} "
            f"required={expected.required}"
        )
    return "\n".join(lines)


def place_artifact(
    workspace_root: Path | str,
    source_path: Path | str,
    *,
    artifact_role: str,
    topic: str,
    extension: str | None = None,
) -> PlaceResult:
    """Copy one artifact into ``output/`` under its canonical filename.

    The declaration gate runs before the destination is computed and before any
    byte is copied. An artifact the TaskSpec does not declare is refused, so
    ``place`` can never create a file that ``validate`` would then reject as
    undeclared: the two operations agree on what the workspace may contain.
    """
    spec, _ = load_persisted_task_spec(workspace_root)
    workspace = layout_for(spec.workspace_root)

    source = Path(source_path)
    if not source.is_file():
        raise RefusalError(f"artifact source is not a regular file: {source}")

    normalized_role, normalized_topic = _normalized_role_and_topic(
        artifact_role=artifact_role, topic=topic
    )
    resolved_extension = _resolve_extension(
        explicit=extension, source=source, artifact_role=artifact_role
    )

    declaration = _matching_declaration(
        spec,
        artifact_role=normalized_role,
        topic=normalized_topic,
        extension=resolved_extension,
    )
    if declaration is None:
        raise RefusalError(
            "refusing to place an artifact that TaskSpec does not declare: "
            f"artifact_role={normalized_role!r} topic={normalized_topic!r} "
            f"extension={resolved_extension!r}. The controlled output area "
            "accepts declared artifacts only; nothing was written and the "
            "output manifest is unchanged. Declared artifacts for this task:\n"
            + _declared_identities(spec)
        )

    filename = canonical_filename(
        task_id=spec.task_id,
        topic=normalized_topic,
        artifact_role=normalized_role,
        extension=resolved_extension,
    )
    try:
        destination = resolve_under(
            workspace.output_dir,
            workspace.output_dir / filename,
            field="artifact destination",
        )
    except UnsafePathError as error:
        raise RefusalError(str(error)) from error

    idempotent = False
    if destination.exists():
        if destination.is_dir():
            raise RefusalError(
                f"artifact destination is an existing directory: {destination}"
            )
        if not files_are_identical(destination, source):
            raise RefusalError(
                f"collision: {destination} already exists with different content. "
                "The canonical name is determined by task, topic and role, so a "
                "different artifact cannot occupy it. Remove or rename the "
                "existing artifact deliberately."
            )
        idempotent = True
    else:
        workspace.output_dir.mkdir(parents=True, exist_ok=True)
        _copy_atomically(source, destination)

    digest = sha256_file(destination)
    size_bytes = destination.stat().st_size
    relative_path = as_posix_relative(destination.relative_to(workspace.root))

    artifacts = [
        item
        for item in _read_output_manifest(workspace)
        if item.get("relative_path") != relative_path
    ]
    artifacts.append(
        {
            "artifact_role": normalized_role,
            "topic": normalized_topic,
            "filename": filename,
            "relative_path": relative_path,
            "size_bytes": size_bytes,
            "sha256_lower": digest,
            "extension": resolved_extension,
            # Taken from the matched declaration rather than re-derived, so the
            # recorded flag cannot disagree with the gate that admitted it.
            "required": declaration.required,
        }
    )
    document = make_output_manifest(task_id=spec.task_id, artifacts=artifacts)
    atomic_write_json(workspace.output_manifest_path, document)

    return PlaceResult(
        workspace_root=str(workspace.root),
        task_id=spec.task_id,
        artifact_role=normalized_role,
        topic=normalized_topic,
        filename=filename,
        relative_path=relative_path,
        size_bytes=size_bytes,
        sha256_lower=digest,
        idempotent=idempotent,
        output_manifest_path=str(workspace.output_manifest_path),
    )


def _copy_atomically(source: Path, destination: Path) -> None:
    """Copy ``source`` onto ``destination`` via a temporary sibling."""
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        suffix=".partial",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            with open(source, "rb") as origin:
                shutil.copyfileobj(origin, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


__all__ = ["PlaceResult", "place_artifact"]
