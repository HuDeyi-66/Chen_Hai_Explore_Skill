"""TaskSpec: the frozen declaration of a controlled evidence workspace.

JSON only, schema version ``0.1``. The schema is deliberately small: it records
the task identity, where the workspace lives, which inputs are permitted, and
which artifacts are expected. It says nothing about *how* the task is performed
and nothing about what the evidence means.

Validation happens here and only here, so that every operation sees the same
checked object and no operation re-implements a check slightly differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .naming import canonical_filename, normalize_component, normalize_extension
from .paths import (
    UnsafePathError,
    as_posix_relative,
    relative_destination,
    require_absolute,
    resolve_input_source,
)

#: The only schema version this MVP understands.
SCHEMA_VERSION = "0.1"

#: Required top-level fields, exactly as specified.
REQUIRED_FIELDS = (
    "schema_version",
    "task_id",
    "topic",
    "workspace_root",
    "inputs",
    "expected_artifacts",
)

#: Required fields of each ``inputs`` entry.
REQUIRED_INPUT_FIELDS = ("source_path", "destination", "mode")

#: Required fields of each ``expected_artifacts`` entry.
REQUIRED_ARTIFACT_FIELDS = ("artifact_role", "topic", "extension", "required")

#: The single staging mode implemented by the MVP.
SUPPORTED_MODES = ("copy",)


@dataclass(frozen=True)
class InputDeclaration:
    """One permitted input source and where it is staged inside the workspace."""

    source_path: str
    destination: str
    mode: str
    index: int

    @property
    def destination_relative(self) -> str:
        return as_posix_relative(relative_destination(self.destination, field=f"inputs[{self.index}].destination"))

    def resolve_source(self, workspace_root: Path) -> Path:
        return resolve_input_source(
            self.source_path,
            workspace_root=workspace_root,
            field=f"inputs[{self.index}].source_path",
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "destination": self.destination,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class ExpectedArtifact:
    """One artifact the task is expected to produce."""

    artifact_role: str
    topic: str
    extension: str
    required: bool
    index: int

    def canonical_filename(self, task_id: str) -> str:
        return canonical_filename(
            task_id=task_id,
            topic=self.topic,
            artifact_role=self.artifact_role,
            extension=self.extension,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "artifact_role": self.artifact_role,
            "topic": self.topic,
            "extension": self.extension,
            "required": self.required,
        }


@dataclass(frozen=True)
class TaskSpec:
    """A validated TaskSpec."""

    schema_version: str
    task_id: str
    topic: str
    workspace_root: str
    inputs: tuple[InputDeclaration, ...]
    expected_artifacts: tuple[ExpectedArtifact, ...]

    @property
    def normalized_task_id(self) -> str:
        return normalize_component(self.task_id, field="task_id")

    @property
    def normalized_topic(self) -> str:
        return normalize_component(self.topic, field="topic")

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_root)

    def to_json(self) -> dict[str, Any]:
        """Canonical JSON form, used both to persist and to compare."""
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "topic": self.topic,
            "workspace_root": self.workspace_root,
            "inputs": [entry.to_json() for entry in self.inputs],
            "expected_artifacts": [entry.to_json() for entry in self.expected_artifacts],
        }


def _require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnsafePathError(f"{field}: expected a JSON object, got {type(value).__name__}")
    return value


def _require_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise UnsafePathError(f"{field}: expected a JSON array, got {type(value).__name__}")
    return value


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise UnsafePathError(f"{field}: expected a non-empty string")
    return value


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise UnsafePathError(
            f"{field}: expected true or false, got {type(value).__name__}"
        )
    return value


def parse_task_spec(payload: Any) -> TaskSpec:
    """Validate a decoded JSON document and return a ``TaskSpec``.

    Raises ``UnsafePathError`` with a field-qualified message on the first
    problem found. Unknown extra fields are refused rather than ignored: a
    silently dropped field would be a declaration the harness appears to honour
    but does not.
    """
    document = _require_mapping(payload, field="task_spec")

    missing = [field for field in REQUIRED_FIELDS if field not in document]
    if missing:
        raise UnsafePathError(
            "task_spec: missing required field(s): " + ", ".join(sorted(missing))
        )
    unexpected = sorted(set(document) - set(REQUIRED_FIELDS))
    if unexpected:
        raise UnsafePathError(
            "task_spec: unknown field(s) not permitted by schema 0.1: "
            + ", ".join(unexpected)
        )

    schema_version = _require_non_empty_string(
        document["schema_version"], field="schema_version"
    )
    if schema_version != SCHEMA_VERSION:
        raise UnsafePathError(
            f"schema_version: expected {SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    task_id = _require_non_empty_string(document["task_id"], field="task_id")
    normalize_component(task_id, field="task_id")

    topic = _require_non_empty_string(document["topic"], field="topic")
    normalize_component(topic, field="topic")

    workspace_root = _require_non_empty_string(
        document["workspace_root"], field="workspace_root"
    )
    require_absolute(workspace_root, field="workspace_root")

    raw_inputs = _require_list(document["inputs"], field="inputs")
    inputs: list[InputDeclaration] = []
    destination_seen: dict[str, int] = {}
    for index, raw_entry in enumerate(raw_inputs):
        entry = _require_mapping(raw_entry, field=f"inputs[{index}]")
        entry_missing = [f for f in REQUIRED_INPUT_FIELDS if f not in entry]
        if entry_missing:
            raise UnsafePathError(
                f"inputs[{index}]: missing required field(s): "
                + ", ".join(sorted(entry_missing))
            )
        entry_unexpected = sorted(set(entry) - set(REQUIRED_INPUT_FIELDS))
        if entry_unexpected:
            raise UnsafePathError(
                f"inputs[{index}]: unknown field(s) not permitted by schema 0.1: "
                + ", ".join(entry_unexpected)
            )

        source_path = _require_non_empty_string(
            entry["source_path"], field=f"inputs[{index}].source_path"
        )
        # Resolve early so an unsafe declaration is refused at parse time rather
        # than after a workspace has been created from it.
        resolve_input_source(
            source_path,
            workspace_root=Path(workspace_root),
            field=f"inputs[{index}].source_path",
        )

        destination = _require_non_empty_string(
            entry["destination"], field=f"inputs[{index}].destination"
        )
        destination_relative = as_posix_relative(
            relative_destination(destination, field=f"inputs[{index}].destination")
        )
        if destination_relative != "input" and not destination_relative.startswith("input/"):
            raise UnsafePathError(
                f"inputs[{index}].destination: must be inside 'input/', "
                f"got {destination!r}; the harness never stages into output/, "
                "manifests/ or checks/"
            )
        if destination_relative in destination_seen:
            raise UnsafePathError(
                f"inputs[{index}].destination: duplicate destination "
                f"{destination_relative!r} also declared at index "
                f"{destination_seen[destination_relative]}"
            )
        destination_seen[destination_relative] = index

        mode = _require_non_empty_string(entry["mode"], field=f"inputs[{index}].mode")
        if mode not in SUPPORTED_MODES:
            raise UnsafePathError(
                f"inputs[{index}].mode: unsupported mode {mode!r}; "
                f"schema 0.1 supports {', '.join(SUPPORTED_MODES)}"
            )

        inputs.append(
            InputDeclaration(
                source_path=source_path,
                destination=destination,
                mode=mode,
                index=index,
            )
        )

    raw_artifacts = _require_list(document["expected_artifacts"], field="expected_artifacts")
    artifacts: list[ExpectedArtifact] = []
    artifact_seen: dict[str, int] = {}
    for index, raw_entry in enumerate(raw_artifacts):
        entry = _require_mapping(raw_entry, field=f"expected_artifacts[{index}]")
        entry_missing = [f for f in REQUIRED_ARTIFACT_FIELDS if f not in entry]
        if entry_missing:
            raise UnsafePathError(
                f"expected_artifacts[{index}]: missing required field(s): "
                + ", ".join(sorted(entry_missing))
            )
        entry_unexpected = sorted(set(entry) - set(REQUIRED_ARTIFACT_FIELDS))
        if entry_unexpected:
            raise UnsafePathError(
                f"expected_artifacts[{index}]: unknown field(s) not permitted by "
                "schema 0.1: " + ", ".join(entry_unexpected)
            )

        artifact_role = _require_non_empty_string(
            entry["artifact_role"], field=f"expected_artifacts[{index}].artifact_role"
        )
        artifact_topic = _require_non_empty_string(
            entry["topic"], field=f"expected_artifacts[{index}].topic"
        )
        extension = normalize_extension(
            _require_non_empty_string(
                entry["extension"], field=f"expected_artifacts[{index}].extension"
            ),
            field=f"expected_artifacts[{index}].extension",
        )
        required = _require_bool(
            entry["required"], field=f"expected_artifacts[{index}].required"
        )

        canonical = canonical_filename(
            task_id=task_id,
            topic=artifact_topic,
            artifact_role=artifact_role,
            extension=extension,
        )
        if canonical in artifact_seen:
            raise UnsafePathError(
                f"expected_artifacts[{index}]: canonical filename {canonical!r} "
                f"collides with index {artifact_seen[canonical]}"
            )
        artifact_seen[canonical] = index

        artifacts.append(
            ExpectedArtifact(
                artifact_role=artifact_role,
                topic=artifact_topic,
                extension=extension,
                required=required,
                index=index,
            )
        )

    return TaskSpec(
        schema_version=schema_version,
        task_id=task_id,
        topic=topic,
        workspace_root=workspace_root,
        inputs=tuple(inputs),
        expected_artifacts=tuple(artifacts),
    )
