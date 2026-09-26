"""SHA-256 primitives for the ChenHai evidence discipline harness.

One implementation of digesting, used by every operation, so that a hash
recorded by ``stage`` or ``place`` and a hash re-checked by ``validate`` can
never disagree because two code paths read bytes differently.

Standard library only. No network, no subprocess, no external tooling.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Read granularity for streaming digests. 1 MiB keeps memory flat for large
#: evidence files while staying a single syscall per chunk on typical systems.
CHUNK_SIZE = 1024 * 1024


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the lowercase hexadecimal SHA-256 of the file at ``path``.

    The file is streamed in ``CHUNK_SIZE`` blocks, so digesting a large staged
    input does not load it into memory.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def files_are_identical(first: Path, second: Path) -> bool:
    """True when two existing files have identical content.

    Compares sizes first, then digests. This is the collision test used by
    ``place``: a canonical destination that already holds byte-identical
    content makes the operation idempotent instead of a refusal.
    """
    if first.stat().st_size != second.stat().st_size:
        return False
    return sha256_file(first) == sha256_file(second)
