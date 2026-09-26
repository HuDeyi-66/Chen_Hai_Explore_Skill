"""Deterministic JSON serialisation and atomic writes.

A manifest that changes bytes when nothing changed is useless as evidence, so
serialisation is pinned: sorted keys, fixed indent, ASCII-escaped, single
trailing newline, LF line endings.

Writes are atomic. A reader either sees the previous complete document or the
next complete document, never a half-written manifest. The temporary file is a
sibling of the target so that ``os.replace`` stays within one filesystem and is
therefore genuinely atomic.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

#: Fixed so that re-serialising identical data yields identical bytes.
INDENT = 2
LINE_ENDING = "\n"


def dumps(payload: Any) -> str:
    """Serialise ``payload`` to deterministic JSON text.

    ``sort_keys`` makes key order a property of the data rather than of
    insertion order; ``ensure_ascii`` keeps the output byte-stable regardless of
    the terminal or locale that produced it.
    """
    text = json.dumps(
        payload,
        indent=INDENT,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ": "),
    )
    return text + LINE_ENDING


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically.

    Sequence: create a temporary sibling, write, flush, ``fsync``, then
    ``os.replace`` onto the target. If any step fails the target is left
    untouched and the temporary file is removed.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline=LINE_ENDING,
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    """Serialise ``payload`` deterministically and write it atomically."""
    atomic_write_text(path, dumps(payload))


def read_json(path: Path) -> Any:
    """Read a JSON document, reporting the path when it is malformed.

    Decoding uses ``utf-8-sig``, which accepts a leading byte-order mark and
    ignores it. Windows tooling (PowerShell's ``Set-Content -Encoding UTF8``
    among others) writes one by default, and a TaskSpec is authored by hand far
    more often than by this harness. Refusing a spec over an invisible BOM would
    be a usability defect, not a safety property.

    Raising ``ValueError`` (not the raw ``JSONDecodeError``) lets callers treat
    a corrupt manifest as a refusal rather than an internal crash.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: malformed JSON: {error}") from error
