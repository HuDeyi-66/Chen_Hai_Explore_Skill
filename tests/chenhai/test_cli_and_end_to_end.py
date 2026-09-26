"""The CLI: operation surface, exit codes, and stdout documents.

Subprocess assertions are kept to a minimum and always redirect output to real
files rather than pipes, because some sandboxed Windows setups deny a parent
process a pipe into a child. The in-process assertions carry the exit-code
contract; the subprocess checks only prove that the documented module invocation
actually starts and writes a machine-readable document.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support  # noqa: E402

from skills.chenhai_harness.__main__ import main  # noqa: E402

ANSWER_BYTES = b"# Synthetic answer\n\nNo real authority is cited here.\n"


class CliExitCodeTests(unittest.TestCase):
    """The documented exit codes: 0 PASS, 2 INCOMPLETE, 3 REFUSE, 1 internal."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch
        self.workspace_root = self.root / "workspace"

        _support.make_dossier(self.root / "dossier", {"README.txt": "synthetic\n"})
        self.spec_path = _support.write_spec(
            self.root / "task_spec.json",
            _support.minimal_spec(self.workspace_root),
        )

    def test_init_returns_zero_and_prints_a_document(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["init", str(self.spec_path)])
        self.assertEqual(code, 0)
        document = json.loads(buffer.getvalue())
        self.assertEqual(document["status"], "PASS")
        self.assertEqual(document["operation"], "init")
        self.assertEqual(document["task_id"], "M03_R2")

    def test_stage_returns_zero(self) -> None:
        import io
        from contextlib import redirect_stdout

        main(["init", str(self.spec_path)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["stage", str(self.workspace_root)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["operation"], "stage")

    def test_validate_returns_two_when_incomplete(self) -> None:
        import io
        from contextlib import redirect_stdout

        main(["init", str(self.spec_path)])
        main(["stage", str(self.workspace_root)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["validate", str(self.workspace_root)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "INCOMPLETE")

    def test_validate_returns_zero_when_complete(self) -> None:
        import io
        from contextlib import redirect_stdout

        main(["init", str(self.spec_path)])
        main(["stage", str(self.workspace_root)])
        source = self.root / "answer.md"
        source.write_bytes(ANSWER_BYTES)
        main(
            [
                "place",
                str(self.workspace_root),
                str(source),
                "--role",
                "final_answer",
                "--topic",
                "legal_analysis",
            ]
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["validate", str(self.workspace_root)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "PASS")

    def test_validate_returns_three_when_refusing(self) -> None:
        import io
        from contextlib import redirect_stdout

        main(["init", str(self.spec_path)])
        main(["stage", str(self.workspace_root)])
        (self.workspace_root / "output" / "stray.txt").write_text("x", encoding="utf-8")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["validate", str(self.workspace_root)])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "REFUSE")

    def test_refusal_from_init_returns_three(self) -> None:
        main(["init", str(self.spec_path)])
        other = _support.write_spec(
            self.root / "other.json",
            _support.minimal_spec(self.workspace_root, task_id="OTHER"),
        )
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = main(["init", str(other)])
        self.assertEqual(code, 3)
        self.assertIn("REFUSE", buffer.getvalue())

    def test_missing_required_option_returns_three(self) -> None:
        main(["init", str(self.spec_path)])
        source = self.root / "answer.md"
        source.write_bytes(ANSWER_BYTES)
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = main(
                ["place", str(self.workspace_root), str(source), "--role", "final_answer"]
            )
        self.assertEqual(code, 3)
        self.assertIn("--topic is required", buffer.getvalue())

    def test_unknown_operation_returns_three(self) -> None:
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = main(["frobnicate", str(self.workspace_root)])
        self.assertEqual(code, 3)
        self.assertIn("unknown operation", buffer.getvalue())

    def test_unexpected_internal_error_returns_one(self) -> None:
        """Exit code 1 is reserved for a harness bug, never for a refusal."""
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from skills.chenhai_harness import __main__ as cli

        original = cli.validate_workspace

        def exploding(*args, **kwargs):
            raise RuntimeError("simulated harness bug")

        cli.validate_workspace = exploding
        try:
            buffer = io.StringIO()
            with redirect_stderr(buffer):
                code = cli.main(["validate", str(self.workspace_root)])
        finally:
            cli.validate_workspace = original

        self.assertEqual(code, 1)
        self.assertIn("internal error", buffer.getvalue())

    def test_help_exits_zero(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("evidence discipline harness", buffer.getvalue())


class CliSubprocessTests(unittest.TestCase):
    """Prove the documented ``python -m skills.chenhai_harness`` invocation runs."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch

    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout_path = self.root / "stdout.txt"
        stderr_path = self.root / "stderr.txt"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(_support.BOOTSTRAP.PROJECT_ROOT)
        with open(stdout_path, "w", encoding="utf-8") as out, open(
            stderr_path, "w", encoding="utf-8"
        ) as err:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "skills.chenhai_harness", *arguments],
                cwd=str(_support.BOOTSTRAP.PROJECT_ROOT),
                stdout=out,
                stderr=err,
                env=environment,
                check=False,
            )
        return (
            completed.returncode,
            stdout_path.read_text(encoding="utf-8"),
            stderr_path.read_text(encoding="utf-8"),
        )

    def test_help_lists_the_four_operations_and_the_exit_codes(self) -> None:
        code, stdout, _ = self._run(["--help"])
        self.assertEqual(code, 0)
        for operation in ("init", "stage", "place", "validate"):
            self.assertIn(operation, stdout)
        for line in ("0  PASS", "2  INCOMPLETE", "3  REFUSE", "1  unexpected"):
            self.assertIn(line, stdout)

    def test_full_sequence_through_the_module_entry_point(self) -> None:
        _support.make_dossier(self.root / "dossier", {"README.txt": "synthetic\n"})
        workspace_root = self.root / "workspace"
        spec_path = _support.write_spec(
            self.root / "task_spec.json", _support.minimal_spec(workspace_root)
        )

        code, stdout, stderr = self._run(["init", str(spec_path)])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["operation"], "init")

        code, stdout, stderr = self._run(["stage", str(workspace_root)])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["entry_count"], 1)

        code, stdout, stderr = self._run(["validate", str(workspace_root)])
        self.assertEqual(code, 2, stderr)
        self.assertEqual(json.loads(stdout)["status"], "INCOMPLETE")

        source = self.root / "answer.md"
        source.write_bytes(ANSWER_BYTES)
        code, stdout, stderr = self._run(
            [
                "place",
                str(workspace_root),
                str(source),
                "--role",
                "final_answer",
                "--topic",
                "legal_analysis",
            ]
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(
            json.loads(stdout)["filename"], "m03_r2__legal_analysis__final_answer.md"
        )

        code, stdout, stderr = self._run(["validate", str(workspace_root)])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["status"], "PASS")

    def test_refusal_exit_code_through_the_module_entry_point(self) -> None:
        workspace_root = self.root / "workspace"
        workspace_root.mkdir()
        (workspace_root / "unrelated.txt").write_text("x", encoding="utf-8")
        spec_path = _support.write_spec(
            self.root / "task_spec.json", _support.minimal_spec(workspace_root)
        )
        code, _, stderr = self._run(["init", str(spec_path)])
        self.assertEqual(code, 3)
        self.assertIn("REFUSE", stderr)


class NoForbiddenDependencyTests(unittest.TestCase):
    """The MVP must not reach for an LLM, the network, or a subprocess."""

    def test_harness_imports_only_the_standard_library(self) -> None:
        self.assertTrue(
            _support.BOOTSTRAP.repository_has_no_llm_or_network_dependency(),
            "a harness module imports an LLM, network or subprocess library",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
