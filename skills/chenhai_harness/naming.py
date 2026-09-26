"""Semantic artifact naming.

Canonical filename::

    <normalized_task_id>__<normalized_topic>__<normalized_artifact_role><extension>

Example::

    m03_r2__legal_analysis__final_answer.md

Normalisation rules (deterministic, applied in this order)
----------------------------------------------------------

1. Unicode input is accepted. The value is normalised to NFKC first, so that
   full-width and compatibility forms of the same character cannot produce two
   different filenames.
2. Surrounding whitespace is trimmed.
3. ASCII uppercase is lowercased. Non-ASCII letters are **not** case-folded and
   are not transliterated: ``.lower()`` is deliberately not used, because it
   would map e.g. ``İ`` to a two-character sequence and make the result
   length-unstable.
4. Any run of characters that are neither ASCII ``[a-z0-9]`` nor Unicode
   alphanumerics is replaced by a single underscore. Spaces, hyphens, dots and
   punctuation therefore all collapse into the separator. Non-ASCII letters and
   digits (for example CJK characters) are kept, so a topic expressed in Chinese
   stays identifiable rather than being erased.
5. Leading and trailing underscores are stripped, which also collapses any
   separator run left by step 4.
6. A separator run inside the value can no longer occur, because step 4 emits at
   most one underscore per run.

Then the whole component is rejected if it is empty, is ``.`` or ``..``,
contains a path separator, or survives as a Windows reserved device name.

The rules never look at file content. A name comes from the TaskSpec or from an
explicit command argument, never from inference over bytes.
"""

from __future__ import annotations

import re
import unicodedata

from .paths import UnsafePathError, reject_unsafe_component

#: The literal separator between the three normalised components.
SEPARATOR = "__"

#: Everything that is neither an ASCII lowercase letter/digit nor a Unicode
#: alphanumeric becomes a separator. The complement is expressed as an explicit
#: class rather than ``[^a-z0-9\w]`` so that CJK and other non-ASCII letters
#: survive: erasing them would destroy the topic information the name is
#: supposed to carry. ``_`` is excluded from the class so that a literal
#: underscore is *also* folded into the separator run, which is what makes
#: ``a - _ b`` collapse to ``a_b`` rather than ``a___b``.
_UNSAFE_RUN = re.compile(r"[^a-z0-9_\u00c0-\U0010ffff]+", re.UNICODE)

#: A literal ``..`` standing alone as a path component. This is the traversal
#: case, and it must be refused. A ``..`` that is merely embedded in ordinary
#: text (``a...b``) is not a traversal and is simply collapsed to a separator.
_PARENT_COMPONENT = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)|^\.\.$")

#: Characters permitted in an extension, after the leading dot.
_EXTENSION_BODY = re.compile(r"^[a-z0-9]+$")


def _has_parent_component(raw: str) -> bool:
    """True when ``raw`` contains a standalone ``..`` component."""
    return bool(_PARENT_COMPONENT.search(raw))


def normalize_component(raw: str, *, field: str) -> str:
    """Normalise one naming component (task id, topic or artifact role).

    Raises ``UnsafePathError`` when the value is unusable, when it contains a
    path separator or ``..``, or when normalisation leaves nothing behind.
    """
    if not isinstance(raw, str):
        raise UnsafePathError(f"{field}: expected a string, got {type(raw).__name__}")

    # Reject traversal attempts on the *raw* value: normalisation would
    # otherwise turn "../etc" into "etc" and hide the attempt.
    if "/" in raw or "\\" in raw:
        raise UnsafePathError(f"{field}: must not contain a path separator: {raw!r}")
    if _has_parent_component(raw):
        raise UnsafePathError(f"{field}: must not contain '..': {raw!r}")
    if raw.strip() in (".", ".."):
        raise UnsafePathError(f"{field}: must not be a parent or current reference: {raw!r}")

    normalized = unicodedata.normalize("NFKC", raw).strip()
    normalized = "".join(
        character.lower() if character.isascii() else character
        for character in normalized
    )
    normalized = _UNSAFE_RUN.sub("_", normalized)
    # Underscores that were already present survive the substitution above (they
    # are outside the replaced class), so they are collapsed separately. This is
    # what makes "a - _ b" become "a_b" rather than "a___b".
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if normalized == "":
        raise UnsafePathError(
            f"{field}: normalises to an empty component; "
            f"{raw!r} contains no filename-safe characters"
        )
    if normalized in (".", ".."):
        raise UnsafePathError(f"{field}: normalises to a parent reference: {raw!r}")
    reject_unsafe_component(normalized, field=field)
    return normalized


def normalize_extension(raw: str, *, field: str = "extension") -> str:
    """Normalise a file extension and return it with a leading dot.

    The extension is the one component that is *not* separator-collapsed: a dot
    is meaningful there. ``.MD`` becomes ``.md``.
    """
    if not isinstance(raw, str):
        raise UnsafePathError(f"{field}: expected a string, got {type(raw).__name__}")
    value = unicodedata.normalize("NFKC", raw).strip()
    if value == "":
        raise UnsafePathError(f"{field}: must not be empty")
    if "/" in value or "\\" in value:
        raise UnsafePathError(f"{field}: must not contain a path separator: {raw!r}")
    if _has_parent_component(value):
        raise UnsafePathError(f"{field}: must not contain '..': {raw!r}")
    if not value.startswith("."):
        value = "." + value
    body = "".join(
        character.lower() if character.isascii() else character
        for character in value[1:]
    )
    if not _EXTENSION_BODY.match(body):
        raise UnsafePathError(
            f"{field}: must contain only ASCII letters and digits after the dot, "
            f"got {raw!r}"
        )
    return "." + body


def extract_extension(raw: str, *, field: str = "extension") -> str:
    """Derive an extension from a source filename.

    Only the suffix is taken, and only when it is a plain one. A source with no
    suffix, or with a suffix that is not letters/digits, is rejected rather than
    guessed at: the caller must state the extension instead.
    """
    if not isinstance(raw, str) or raw.strip() == "":
        raise UnsafePathError(f"{field}: cannot infer an extension from {raw!r}")
    name = raw.strip().replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name:
        raise UnsafePathError(
            f"{field}: cannot infer an extension from {name!r}; pass --extension"
        )
    suffix = name.rsplit(".", 1)[-1]
    suffix = "".join(
        character.lower() if character.isascii() else character
        for character in suffix
    )
    if suffix == "" or not _EXTENSION_BODY.match(suffix):
        raise UnsafePathError(
            f"{field}: cannot infer a usable extension from {name!r}; pass --extension"
        )
    return "." + suffix


def canonical_filename(
    *,
    task_id: str,
    topic: str,
    artifact_role: str,
    extension: str,
) -> str:
    """Build the canonical artifact filename for the three components."""
    return (
        normalize_component(task_id, field="task_id")
        + SEPARATOR
        + normalize_component(topic, field="topic")
        + SEPARATOR
        + normalize_component(artifact_role, field="artifact_role")
        + normalize_extension(extension)
    )


def is_canonical_filename(
    filename: str,
    *,
    task_id: str,
    topic: str,
    artifact_role: str,
    extension: str,
) -> bool:
    """True when ``filename`` is exactly the canonical name for these inputs."""
    return filename == canonical_filename(
        task_id=task_id,
        topic=topic,
        artifact_role=artifact_role,
        extension=extension,
    )


def describe_rules() -> dict[str, object]:
    """Machine-readable statement of the naming policy.

    Kept next to the implementation so the documented rule and the executed rule
    cannot drift apart.
    """
    return {
        "pattern": (
            "<normalized_task_id>" + SEPARATOR + "<normalized_topic>"
            + SEPARATOR + "<normalized_artifact_role><extension>"
        ),
        "separator": SEPARATOR,
        "unicode": "NFKC; non-ASCII alphanumerics preserved, not transliterated",
        "case": "ASCII uppercase lowercased; non-ASCII untouched",
        "separator_collapse": (
            "runs of characters that are not ASCII [a-z0-9] or Unicode "
            "alphanumerics become one underscore"
        ),
        "rejects": [
            "path separators",
            "'..' components",
            "empty normalized components",
            "Windows reserved device names",
        ],
        "content_inference": False,
    }
