"""Command-line interface for the ChenHai evidence discipline harness.

Usage::

    python -m skills.chenhai_harness init <task_spec.json> [--workspace-root DIR]
    python -m skills.chenhai_harness stage <workspace>
    python -m skills.chenhai_harness place <workspace> <source_file> \
        --role final_answer --topic legal_analysis [--extension .md]
    python -m skills.chenhai_harness validate <workspace>

Exit codes::

    0  PASS, or a successful init/stage/place operation
    2  INCOMPLETE  -- the workspace is sound but required artifacts are missing
    3  REFUSE      -- invalid spec, unsafe path, naming violation, manifest
                      corruption, hash mismatch, collision, or similar
    1  unexpected internal error

``2`` and ``3`` are deliberately distinct, and ``1`` is deliberately not used
for a refusal: a caller must be able to tell "not finished" from "not
trustworthy" from "the harness itself broke".

No third-party argument parser is used. The dependency surface of this MVP is
the Python standard library, and the argument set is small enough that a
hand-rolled parser remains readable and keeps the refusal behaviour explicit.
"""

from __future__ import annotations

import sys
from typing import Sequence

from .init import init_workspace
from .jsonio import dumps
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
    STATUS_EXIT_CODES,
)
from .paths import UnsafePathError
from .place import place_artifact
from .stage import stage_workspace
from .validate import validate_workspace

PROGRAM = "python -m skills.chenhai_harness"

USAGE = f"""\
ChenHai evidence discipline harness (MVP)

usage:
  {PROGRAM} init <task_spec.json> [--workspace-root DIR]
  {PROGRAM} stage <workspace>
  {PROGRAM} place <workspace> <source_file> --role ROLE --topic TOPIC [--extension .ext]
  {PROGRAM} validate <workspace>

operations:
  init       create the controlled workspace declared by a TaskSpec
  stage      copy declared inputs into the workspace and record SHA-256 digests
  place      put a produced artifact into output/ under its canonical name
  validate   check the workspace; report PASS, INCOMPLETE or REFUSE

exit codes:
  0  PASS / successful operation
  2  INCOMPLETE
  3  REFUSE
  1  unexpected internal error
"""


class UsageError(Exception):
    """The command line itself was wrong."""


def _parse_options(argv: Sequence[str], allowed: set[str]) -> dict[str, str]:
    """Parse ``--flag value`` pairs, rejecting anything not in ``allowed``."""
    options: dict[str, str] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if not token.startswith("--"):
            raise UsageError(f"unexpected argument: {token!r}")
        name = token[2:]
        if name not in allowed:
            raise UsageError(
                f"unknown option --{name}; allowed here: "
                + ", ".join(sorted("--" + item for item in allowed))
            )
        if index + 1 >= len(argv):
            raise UsageError(f"--{name} needs a value")
        if name in options:
            raise UsageError(f"--{name} given more than once")
        options[name] = argv[index + 1]
        index += 2
    return options


def _require_positional(argv: Sequence[str], count: int, usage_line: str) -> list[str]:
    if len(argv) < count:
        raise UsageError(f"missing argument(s)\n\nusage:\n  {usage_line}")
    return list(argv[:count])


def _emit(document: object) -> None:
    sys.stdout.write(dumps(document))


def _run_init(argv: Sequence[str]) -> int:
    positionals = _require_positional(argv, 1, f"{PROGRAM} init <task_spec.json>")
    options = _parse_options(argv[1:], {"workspace-root"})
    result = init_workspace(
        positionals[0], workspace_root=options.get("workspace-root")
    )
    _emit(result.to_json())
    return EXIT_OK


def _run_stage(argv: Sequence[str]) -> int:
    positionals = _require_positional(argv, 1, f"{PROGRAM} stage <workspace>")
    _parse_options(argv[1:], set())
    result = stage_workspace(positionals[0])
    _emit(result.to_json())
    return EXIT_OK


def _run_place(argv: Sequence[str]) -> int:
    positionals = _require_positional(
        argv,
        2,
        f"{PROGRAM} place <workspace> <source_file> --role ROLE --topic TOPIC",
    )
    options = _parse_options(argv[2:], {"role", "topic", "extension"})
    for required in ("role", "topic"):
        if required not in options:
            raise UsageError(f"--{required} is required for place")
    result = place_artifact(
        positionals[0],
        positionals[1],
        artifact_role=options["role"],
        topic=options["topic"],
        extension=options.get("extension"),
    )
    _emit(result.to_json())
    return EXIT_OK


def _run_validate(argv: Sequence[str]) -> int:
    positionals = _require_positional(argv, 1, f"{PROGRAM} validate <workspace>")
    _parse_options(argv[1:], set())
    result = validate_workspace(positionals[0])
    _emit(result.report)
    return STATUS_EXIT_CODES[result.status]


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)

    if not arguments or arguments[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return EXIT_OK

    operation = arguments[0]
    remainder = arguments[1:]

    handlers = {
        "init": _run_init,
        "stage": _run_stage,
        "place": _run_place,
        "validate": _run_validate,
    }

    if operation not in handlers:
        sys.stderr.write(
            f"unknown operation: {operation!r}\n\n{USAGE}"
        )
        return EXIT_REFUSE

    try:
        return handlers[operation](remainder)
    except UsageError as error:
        sys.stderr.write(f"usage error: {error}\n")
        return EXIT_REFUSE
    except UnsafePathError as error:
        sys.stderr.write(f"REFUSE: unsafe path: {error}\n")
        return EXIT_REFUSE
    except RefusalError as error:
        sys.stderr.write(f"REFUSE: {error}\n")
        return EXIT_REFUSE
    except IncompleteError as error:
        sys.stderr.write(f"INCOMPLETE: {error}\n")
        return EXIT_INCOMPLETE
    except OSError as error:
        sys.stderr.write(f"REFUSE: filesystem error: {error}\n")
        return EXIT_REFUSE
    except Exception as error:  # noqa: BLE001 - the boundary of the CLI
        sys.stderr.write(
            f"internal error: {type(error).__name__}: {error}\n"
        )
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "INCOMPLETE",
    "PASS",
    "REFUSE",
    "USAGE",
    "UsageError",
    "main",
]
