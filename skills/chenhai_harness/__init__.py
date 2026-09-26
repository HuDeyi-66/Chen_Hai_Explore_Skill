"""ChenHai evidence discipline harness (MVP).

A small, deterministic filesystem harness that reduces manual experiment and
evidence workspace handling. It provides four operations:

``init``
    Create a controlled workspace from a TaskSpec.
``stage``
    Copy declared inputs into the workspace and record their SHA-256 digests.
``place``
    Put a produced artifact into the controlled output area under its canonical
    filename.
``validate``
    Check the workspace and return ``PASS``, ``INCOMPLETE`` or ``REFUSE``.

Deliberately absent: any LLM dependency, semantic inference, retrieval, and
evaluation intelligence. The harness decides where bytes live and whether they
are the bytes that were recorded — never what they mean.

Explicit limitation
-------------------
This MVP is **not** an operating-system sandbox. It does not prevent an external
model or process from reading or writing arbitrary paths. It constructs a
controlled workspace, stages known inputs, constrains managed outputs, records
manifests, and validates the resulting workspace. It does not isolate anything.
"""

from __future__ import annotations

from .hashing import files_are_identical, sha256_bytes, sha256_file
from .init import InitResult, init_workspace, load_persisted_task_spec
from .naming import (
    SEPARATOR,
    canonical_filename,
    describe_rules,
    extract_extension,
    normalize_component,
    normalize_extension,
)
from .outcomes import (
    EXIT_INCOMPLETE,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_REFUSE,
    INCOMPLETE,
    PASS,
    REFUSE,
    IncompleteError,
    RefusalError,
)
from .paths import UnsafePathError
from .place import PlaceResult, place_artifact
from .stage import StageResult, stage_workspace
from .taskspec import SCHEMA_VERSION, TaskSpec, parse_task_spec
from .validate import ValidationResult, validate_workspace
from .workspace import (
    CORE_DIRECTORIES,
    INPUT_MANIFEST_RELATIVE,
    OUTPUT_MANIFEST_RELATIVE,
    TASK_SPEC_RELATIVE,
    VALIDATION_REPORT_RELATIVE,
    WorkspaceLayout,
    layout_for,
)

__version__ = "0.1.0"

__all__ = [
    "CORE_DIRECTORIES",
    "EXIT_INCOMPLETE",
    "EXIT_INTERNAL_ERROR",
    "EXIT_OK",
    "EXIT_REFUSE",
    "INCOMPLETE",
    "INPUT_MANIFEST_RELATIVE",
    "IncompleteError",
    "InitResult",
    "OUTPUT_MANIFEST_RELATIVE",
    "PASS",
    "PlaceResult",
    "REFUSE",
    "RefusalError",
    "SCHEMA_VERSION",
    "SEPARATOR",
    "StageResult",
    "TASK_SPEC_RELATIVE",
    "TaskSpec",
    "UnsafePathError",
    "VALIDATION_REPORT_RELATIVE",
    "ValidationResult",
    "WorkspaceLayout",
    "canonical_filename",
    "describe_rules",
    "extract_extension",
    "files_are_identical",
    "init_workspace",
    "layout_for",
    "load_persisted_task_spec",
    "normalize_component",
    "normalize_extension",
    "parse_task_spec",
    "place_artifact",
    "sha256_bytes",
    "sha256_file",
    "stage_workspace",
    "validate_workspace",
    "__version__",
]
