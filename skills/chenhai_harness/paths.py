"""Path-resolution safety for the ChenHai evidence discipline harness.

Everything that turns a caller-supplied or TaskSpec-supplied string into a real
filesystem location goes through this module. Keeping it in one place is the
reason ``init``, ``stage``, ``place`` and ``validate`` cannot drift apart in how
they decide that a path is acceptable.

This is **not** an operating-system sandbox
-------------------------------------------
The checks here constrain the paths that *this harness* is willing to construct
and write. They cannot stop another process, a model, or a human from opening
any path they like. See the limitation section in ``README.md``.
"""

from __future__ import annotations

import ntpath
import posixpath
from pathlib import Path

#: Windows device names that are not usable as ordinary path components.
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class UnsafePathError(ValueError):
    """Raised when a path is rejected before any filesystem effect occurs."""


def as_posix_relative(path: Path | str) -> str:
    """Return a workspace-relative path rendered with forward slashes.

    Manifests record paths in this form so that a manifest produced on Windows
    is byte-comparable with one produced on POSIX. Only the separator is
    normalised; no other rewriting is applied.
    """
    return Path(path).as_posix()


def has_parent_reference(raw: str) -> bool:
    """True when ``raw`` contains a ``..`` component.

    Both separators are inspected because the string may have been authored on
    either platform, and ``..`` is the one component that can escape a
    boundary.
    """
    separators = ("/", "\\")
    for separator in separators:
        if separator in raw:
            for part in raw.split(separator):
                if part == "..":
                    return True
    return raw == ".."


def is_absolute_any_platform(raw: str) -> bool:
    """True when ``raw`` is absolute under Windows or POSIX rules.

    A Windows-authored TaskSpec may legitimately be read on a POSIX host and
    vice versa, so both conventions are rejected explicitly rather than relying
    on the host's own ``is_absolute``.
    """
    return bool(ntpath.isabs(raw) or posixpath.isabs(raw))


def reject_unsafe_component(component: str, *, field: str) -> str:
    """Validate one filename or path component and return it unchanged.

    Rejects separators, ``..``, empty/whitespace-only values, NUL bytes, and
    Windows reserved device names. Used for artifact roles, topics and
    extensions before a filename is assembled from them.
    """
    if not isinstance(component, str):
        raise UnsafePathError(f"{field}: expected a string, got {type(component).__name__}")
    if component.strip() == "":
        raise UnsafePathError(f"{field}: must not be empty or whitespace only")
    if "\x00" in component:
        raise UnsafePathError(f"{field}: contains a NUL byte")
    if "/" in component or "\\" in component:
        raise UnsafePathError(f"{field}: must not contain a path separator: {component!r}")
    if component in (".", ".."):
        raise UnsafePathError(f"{field}: must not be a parent or current reference: {component!r}")
    if has_parent_reference(component):
        raise UnsafePathError(f"{field}: must not contain '..': {component!r}")
    stem = component.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED:
        raise UnsafePathError(f"{field}: {component!r} is a reserved device name")
    return component


def resolve_under(root: Path, candidate: Path, *, field: str) -> Path:
    """Resolve ``candidate`` and prove it stays inside ``root``.

    ``root`` is resolved first so that the comparison is between two real
    locations rather than between a real one and a lexical one. The candidate is
    required to be inside ``root`` strictly below it: ``root`` itself is
    accepted, a sibling or a parent is not.

    Raises ``UnsafePathError`` when the candidate escapes, which is what stops
    a TaskSpec or CLI argument from reaching outside the controlled workspace.
    """
    real_root = Path(root).resolve()
    real_candidate = Path(candidate).resolve()
    if real_candidate == real_root:
        return real_candidate
    if real_root not in real_candidate.parents:
        raise UnsafePathError(
            f"{field}: resolves outside the permitted root "
            f"({real_candidate} is not under {real_root})"
        )
    return real_candidate


def resolve_input_source(raw: str, *, workspace_root: Path, field: str) -> Path:
    """Resolve a declared input ``source_path``.

    Absolute paths are used as given. Relative paths are resolved against the
    workspace root, which makes a committed TaskSpec template self-contained
    without embedding a private absolute path.

    A ``..`` component is refused outright rather than normalised away, so an
    escaping declaration is reported instead of silently corrected.
    """
    if not isinstance(raw, str) or raw.strip() == "":
        raise UnsafePathError(f"{field}: must be a non-empty string")
    if "\x00" in raw:
        raise UnsafePathError(f"{field}: contains a NUL byte")
    if has_parent_reference(raw):
        raise UnsafePathError(f"{field}: must not contain '..': {raw!r}")
    candidate = Path(raw)
    if not is_absolute_any_platform(raw):
        candidate = Path(workspace_root) / candidate
    return candidate.resolve()


def require_absolute(raw: str, *, field: str) -> Path:
    """Validate that ``raw`` is an absolute path with no ``..`` component."""
    if not isinstance(raw, str) or raw.strip() == "":
        raise UnsafePathError(f"{field}: must be a non-empty string")
    if "\x00" in raw:
        raise UnsafePathError(f"{field}: contains a NUL byte")
    if not is_absolute_any_platform(raw):
        raise UnsafePathError(
            f"{field}: must be an absolute path, got {raw!r}; "
            "the harness never resolves the workspace root against the "
            "current working directory"
        )
    if has_parent_reference(raw):
        raise UnsafePathError(f"{field}: must not contain '..': {raw!r}")
    return Path(raw).resolve()


def relative_destination(raw: str, *, field: str) -> Path:
    """Validate a declared workspace-relative destination such as ``input/x``."""
    if not isinstance(raw, str) or raw.strip() == "":
        raise UnsafePathError(f"{field}: must be a non-empty string")
    if "\x00" in raw:
        raise UnsafePathError(f"{field}: contains a NUL byte")
    if is_absolute_any_platform(raw):
        raise UnsafePathError(f"{field}: must be relative to the workspace, got {raw!r}")
    if has_parent_reference(raw):
        raise UnsafePathError(f"{field}: must not contain '..': {raw!r}")
    cleaned = raw.replace("\\", "/").strip("/")
    if cleaned == "":
        raise UnsafePathError(f"{field}: must not be empty")
    return Path(cleaned)
