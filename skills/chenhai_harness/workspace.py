"""The controlled workspace layout.

Exactly four directories, and no deeper hierarchy::

    <workspace_root>/
        input/
        output/
        manifests/
        checks/

The layout is intentionally flat. A larger tree would invite ad-hoc placement
decisions, and the point of the harness is that placement is declared rather
than chosen at the time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The four core directories, in the order they are created.
CORE_DIRECTORIES = ("input", "output", "manifests", "checks")

#: Canonical persisted TaskSpec location.
TASK_SPEC_RELATIVE = "manifests/task_spec.json"

#: Staged-input manifest.
INPUT_MANIFEST_RELATIVE = "manifests/input_manifest.json"

#: Produced-artifact manifest.
OUTPUT_MANIFEST_RELATIVE = "manifests/output_manifest.json"

#: Validation report.
VALIDATION_REPORT_RELATIVE = "checks/validation_report.json"

#: Manifest document version, independent of the TaskSpec schema version.
MANIFEST_SCHEMA_VERSION = "chest-harness-manifest/0.1"

#: Identity recorded in generated documents. Deliberately a constant and not a
#: timestamp: identical state must produce identical bytes.
GENERATED_BY = "skills/chenhai_harness"


@dataclass(frozen=True)
class WorkspaceLayout:
    """Resolved paths of one controlled workspace."""

    root: Path

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def manifests_dir(self) -> Path:
        return self.root / "manifests"

    @property
    def checks_dir(self) -> Path:
        return self.root / "checks"

    @property
    def task_spec_path(self) -> Path:
        return self.root / TASK_SPEC_RELATIVE

    @property
    def input_manifest_path(self) -> Path:
        return self.root / INPUT_MANIFEST_RELATIVE

    @property
    def output_manifest_path(self) -> Path:
        return self.root / OUTPUT_MANIFEST_RELATIVE

    @property
    def validation_report_path(self) -> Path:
        return self.root / VALIDATION_REPORT_RELATIVE

    def core_dirs(self) -> dict[str, Path]:
        return {
            "input": self.input_dir,
            "output": self.output_dir,
            "manifests": self.manifests_dir,
            "checks": self.checks_dir,
        }

    def missing_core_dirs(self) -> list[str]:
        return sorted(
            name for name, path in self.core_dirs().items() if not path.is_dir()
        )


def layout_for(workspace_root: Path | str) -> WorkspaceLayout:
    """Return the layout for a workspace root without touching the filesystem."""
    return WorkspaceLayout(root=Path(workspace_root).resolve())


def make_input_manifest(*, task_id: str, entries: list[dict[str, object]]) -> dict[str, object]:
    """Build an ``input_manifest.json`` document.

    Entries are sorted by ``relative_path`` so that two staging runs over the
    same inputs produce identical bytes.
    """
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "task_id": task_id,
        "entry_count": len(entries),
        "entries": sorted(entries, key=lambda entry: str(entry["relative_path"])),
    }


def make_output_manifest(*, task_id: str, artifacts: list[dict[str, object]]) -> dict[str, object]:
    """Build an ``output_manifest.json`` document, sorted by ``relative_path``."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "task_id": task_id,
        "artifact_count": len(artifacts),
        "artifacts": sorted(artifacts, key=lambda item: str(item["relative_path"])),
    }
