"""The end-to-end sequence, asserted inside the discovered suite.

``tests/smoke_e2e.py`` is the human-runnable demonstration; this module is the
same sequence under test discovery, so the demonstration cannot rot without the
suite going red.

The sequence proves the acceptance path for the whole MVP:

1. synthetic TaskSpec            -> 2. init
3. stage                         -> 4. validate == INCOMPLETE
5. place required artifacts      -> 6. validate == PASS
7. manifest hashes re-verified   -> 8. temporary workspace removed
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import smoke_e2e  # noqa: E402

from skills.chenhai_harness.outcomes import INCOMPLETE, PASS  # noqa: E402


class EndToEndSmokeTests(unittest.TestCase):
    def test_documented_sequence_reaches_pass(self) -> None:
        summary = smoke_e2e.run_smoke()

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["task_id"], "M03_R2")
        self.assertEqual(summary["topic"], "missing_authority")

        # Step 4: an initialised, staged workspace is INCOMPLETE, not PASS.
        self.assertEqual(summary["validate_incomplete"]["status"], INCOMPLETE)
        self.assertEqual(
            summary["validate_incomplete"]["missing_required_artifacts"],
            [
                "m03_r2__legal_analysis__citation_record.json",
                "m03_r2__legal_analysis__final_answer.md",
            ],
        )

        # Step 6: after placement the same workspace is PASS.
        self.assertEqual(summary["validate_pass"]["status"], PASS)
        self.assertEqual(summary["validate_pass"]["hash_mismatches"], [])
        self.assertEqual(summary["validate_pass"]["integrity_errors"], [])

        # Step 7: the recorded digests were re-derived, not trusted.
        self.assertEqual(summary["verified_hashes"]["mismatches"], [])
        self.assertTrue(summary["verified_hashes"]["validation_report_present"])
        self.assertGreaterEqual(summary["verified_hashes"]["entries_checked"], 4)

    def test_smoke_run_removes_its_own_workspace(self) -> None:
        summary = smoke_e2e.run_smoke()
        self.assertFalse(
            Path(str(summary["scratch"])).exists(),
            "the temporary smoke workspace was not removed",
        )

    def test_smoke_run_never_writes_into_the_repository(self) -> None:
        """The fixture directory must be byte-identical before and after."""
        fixture_dir = smoke_e2e.DEMO_DIR

        def snapshot() -> dict[str, bytes]:
            return {
                path.relative_to(fixture_dir).as_posix(): path.read_bytes()
                for path in sorted(fixture_dir.rglob("*"))
                if path.is_file()
            }

        before = snapshot()
        smoke_e2e.run_smoke()
        self.assertEqual(before, snapshot(), "the smoke run modified repository fixtures")

    def test_kept_scratch_can_be_inspected(self) -> None:
        import _bootstrap

        target = _bootstrap.make_scratch_dir(prefix="chenhai_kept_")
        self.addCleanup(_bootstrap.remove_scratch_dir, target)
        summary = smoke_e2e.run_smoke(keep=True, scratch=target)
        self.assertTrue(target.exists())
        self.assertEqual(summary["validate_pass"]["status"], PASS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
