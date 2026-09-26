"""ChenHai evidence discipline harness test bootstrap.

Makes this repository's root importable as ``skills`` and ``fixtures`` when the
suite is run from anywhere, without requiring an install. There is no packaging
metadata in this repository on purpose: a clean checkout plus a Python 3.10+
interpreter is the whole requirement.

Used by every suite module, and by ``run_all.py``.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

#: Monotonic counter making scratch directory names unique within one process.
_SCRATCH_COUNTER = itertools.count()


def scratch_base_candidates() -> list[Path]:
    """Directories that might accept a scratch workspace, best candidate first.

    ``TEMP`` is deliberately **not** a candidate. A sandboxed host can expose a
    temporary directory that accepts a top-level ``mkdir`` and then refuses
    anything deeper, which produces confusing failures in the middle of a test
    rather than at the start of one. The checkout's parent directory is tried
    first and the checkout itself second; both are known writable because this
    suite lives there.

    Scratch directories are always given names beginning with ``chenhai_`` so
    that a leaked one is identifiable, and ``.gitignore`` excludes that pattern
    so a leak can never be committed.

    Note that ``tempfile`` is deliberately *not* used anywhere in this suite: it
    creates directories with a restrictive mode, and on some sandboxed hosts
    that makes the new directory unreadable to the very process that created it.
    ``Path.mkdir`` is used instead.
    """
    candidates: list[Path] = [PROJECT_ROOT.parent, PROJECT_ROOT]
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def make_scratch_dir(*, prefix: str = "chenhai_scratch_", base: Path | None = None) -> Path:
    """Create and return a fresh scratch directory.

    Tries each candidate base in turn and returns the first that accepts a
    nested directory. Raises ``RuntimeError`` when none does, rather than
    silently falling back to a location the suite cannot clean up.
    """
    bases = [base] if base is not None else scratch_base_candidates()
    errors: list[str] = []
    for candidate_base in bases:
        if candidate_base is None:
            continue
        name = f"{prefix}{os.getpid()}_{next(_SCRATCH_COUNTER)}"
        target = Path(candidate_base) / name
        try:
            (target / "probe" / "nested").mkdir(parents=True, exist_ok=True)
            shutil.rmtree(target / "probe", ignore_errors=True)
        except OSError as error:
            errors.append(f"{target}: {type(error).__name__}: {error}")
            continue
        return target
    raise RuntimeError(
        "no writable scratch base directory; tried: " + "; ".join(errors)
    )


def remove_scratch_dir(path: Path) -> None:
    """Remove a scratch directory, tolerating a host that refuses deletion."""
    shutil.rmtree(Path(path), ignore_errors=True)


def scratch_directory() -> tuple[Path, Any]:
    """Return ``(path, cleanup)``; ``cleanup`` is idempotent and never raises."""
    path = make_scratch_dir()

    def cleanup() -> None:
        remove_scratch_dir(path)

    return path, cleanup

#: Synthetic demo fixture. Public-safe: no real evidence, no private paths.
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
DEMO_DIR = FIXTURES_DIR / "m03_r2_demo"
DEMO_TASK_SPEC = DEMO_DIR / "task_spec.json"
DEMO_TEMPLATE_SPEC = DEMO_DIR / "task_spec.template.json"
DEMO_SOURCE_DIR = DEMO_DIR / "source" / "dossier"

#: The placeholder the runnable demo spec carries instead of a host path.
WORKSPACE_PLACEHOLDER = "REPLACED_AT_TEST_TIME"

#: The two artifacts the runnable demo declares as required.
DEMO_REQUIRED_ARTIFACTS = (
    "m03_r2__legal_analysis__final_answer.md",
    "m03_r2__legal_analysis__citation_record.json",
)


def sha256_of(payload: bytes) -> str:
    """Independent digest helper, so manifest checks are not self-confirming."""
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: Any) -> Path:
    """Write a JSON document with a stable, readable layout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_demo_spec_template() -> dict[str, Any]:
    """Return the published TaskSpec shape example as a fresh dictionary.

    The smoke demonstration and the fixture tests both build their runnable
    specification from this one document, so the published example and every
    executed variant cannot drift apart.
    """
    return json.loads(DEMO_TEMPLATE_SPEC.read_text(encoding="utf-8"))


def build_demo_task_spec(
    scratch: Path,
    *,
    workspace_name: str = "workspace",
    expected_artifacts: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    """Materialise the demo TaskSpec for a scratch directory.

    The fixture's ``source/dossier`` is copied into ``scratch`` and the spec's
    ``source_path`` is rewritten to that copy, so a test never stages from the
    repository fixture itself and cannot mutate it.

    Returns ``(task_spec_path, workspace_root)``.
    """
    scratch = Path(scratch).resolve()
    workspace_root = scratch / workspace_name

    staged_source = scratch / "source" / "dossier"
    if staged_source.exists():
        shutil.rmtree(staged_source)
    staged_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DEMO_SOURCE_DIR, staged_source)

    spec = json.loads(DEMO_TASK_SPEC.read_text(encoding="utf-8"))
    spec["workspace_root"] = str(workspace_root)
    spec["inputs"][0]["source_path"] = str(staged_source)
    if expected_artifacts is not None:
        spec["expected_artifacts"] = expected_artifacts

    task_spec_path = write_json(scratch / "task_spec.json", spec)
    return task_spec_path, workspace_root


def demo_artifact_payloads() -> dict[str, bytes]:
    """Bytes for the two synthetic artifacts the demo expects.

    The values are hashed by the tests, so the content is deliberately trivial
    and stable.
    """
    answer = (
        b"# Synthetic final answer (demo fixture)\n\n"
        b"This file is synthetic. It carries no legal analysis and no real "
        b"authority.\n"
    )
    citation_record = (
        b'{\n  "synthetic": true,\n  "entries": [\n'
        b'    {"authority_reference": "SYNTHETIC-001", "status": "demonstration only"}\n'
        b"  ]\n}\n"
    )
    return {
        "m03_r2__legal_analysis__final_answer.md": answer,
        "m03_r2__legal_analysis__citation_record.json": citation_record,
    }


def repository_has_no_llm_or_network_dependency() -> bool:
    """True when no harness module imports an LLM, network or subprocess library.

    The source is parsed rather than imported, so the check cannot pass merely
    because an import happened to resolve against the host environment. This is
    the machine-checkable form of the MVP's "no LLM dependency, no retrieval, no
    network" constraint.
    """
    import ast

    forbidden = {
        "anthropic",
        "httpx",
        "langchain",
        "llama_index",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    for path in sorted((PROJECT_ROOT / "skills").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.split(".")[0] in forbidden for a in node.names):
                    return False
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                if (node.module or "").split(".")[0] in forbidden:
                    return False
    return True
