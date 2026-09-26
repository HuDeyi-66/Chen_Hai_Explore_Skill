"""``place`` and ``validate``: placement, manifests, the completeness gate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support  # noqa: E402

from skills.chenhai_harness import (  # noqa: E402
    init_workspace,
    place_artifact,
    stage_workspace,
    validate_workspace,
)
from skills.chenhai_harness.outcomes import INCOMPLETE, PASS, REFUSE, RefusalError  # noqa: E402
from skills.chenhai_harness.workspace import (  # noqa: E402
    OUTPUT_MANIFEST_RELATIVE,
    VALIDATION_REPORT_RELATIVE,
)

DOSSIER_FILES = {"README.txt": "synthetic dossier entry\n"}

ANSWER_FILENAME = "m03_r2__legal_analysis__final_answer.md"
CITATION_FILENAME = "m03_r2__legal_analysis__citation_record.json"

ANSWER_BYTES = b"# Synthetic answer\n\nNo real authority is cited here.\n"
CITATION_BYTES = b'{"synthetic": true, "entries": []}\n'


def declared_artifacts() -> list[dict[str, object]]:
    return [
        {
            "artifact_role": "final_answer",
            "topic": "legal_analysis",
            "extension": ".md",
            "required": True,
        },
        {
            "artifact_role": "citation_record",
            "topic": "legal_analysis",
            "extension": ".json",
            "required": True,
        },
    ]


class HarnessTestCase(unittest.TestCase):
    """Shared setup: a scratch root, a synthetic dossier and two artifacts."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch
        self.workspace_root = self.root / "workspace"

        _support.make_dossier(self.root / "dossier", DOSSIER_FILES)
        spec = _support.minimal_spec(
            self.workspace_root, expected_artifacts=declared_artifacts()
        )
        self.spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        self.init_result = init_workspace(self.spec_path)

    def artifact_file(self, name: str, payload: bytes) -> Path:
        target = self.root / "produced" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return target

    def place_both(self) -> tuple[object, object]:
        first = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        second = place_artifact(
            self.workspace_root,
            self.artifact_file("citations.json", CITATION_BYTES),
            artifact_role="citation_record",
            topic="legal_analysis",
        )
        return first, second

    def report(self) -> dict:
        return _support.read_json_file(
            self.workspace_root / VALIDATION_REPORT_RELATIVE
        )


class PlaceTests(HarnessTestCase):
    """Requirements 8, 13 and 14: placement, collision refusal, idempotence."""

    def test_place_copies_under_the_canonical_name_and_records_it(self) -> None:
        source = self.artifact_file("answer.md", ANSWER_BYTES)
        result = place_artifact(
            self.workspace_root,
            source,
            artifact_role="final_answer",
            topic="legal_analysis",
        )

        self.assertEqual(result.filename, ANSWER_FILENAME)
        self.assertEqual(result.relative_path, f"output/{ANSWER_FILENAME}")
        self.assertEqual(result.sha256_lower, _support.sha256_of(ANSWER_BYTES))
        self.assertEqual(result.size_bytes, len(ANSWER_BYTES))
        self.assertFalse(result.idempotent)

        placed = self.workspace_root / "output" / ANSWER_FILENAME
        self.assertEqual(placed.read_bytes(), ANSWER_BYTES)
        # Non-destructive: the source file is still there.
        self.assertEqual(source.read_bytes(), ANSWER_BYTES)

        manifest = _support.read_json_file(
            self.workspace_root / OUTPUT_MANIFEST_RELATIVE
        )
        self.assertEqual(manifest["artifact_count"], 1)
        entry = manifest["artifacts"][0]
        self.assertEqual(entry["relative_path"], f"output/{ANSWER_FILENAME}")
        self.assertEqual(entry["sha256_lower"], _support.sha256_of(ANSWER_BYTES))
        self.assertEqual(entry["artifact_role"], "final_answer")
        self.assertEqual(entry["topic"], "legal_analysis")
        self.assertTrue(entry["required"])

    def test_extension_is_inferred_from_the_source_filename(self) -> None:
        result = place_artifact(
            self.workspace_root,
            self.artifact_file("citations.JSON", CITATION_BYTES),
            artifact_role="citation_record",
            topic="legal_analysis",
        )
        self.assertEqual(result.filename, CITATION_FILENAME)

    def test_explicit_extension_overrides_inference(self) -> None:
        result = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.txt", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
            extension=".md",
        )
        self.assertEqual(result.filename, ANSWER_FILENAME)

    def test_role_and_topic_are_normalized_into_the_name(self) -> None:
        result = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="  Final Answer  ",
            topic="Legal  Analysis",
        )
        self.assertEqual(result.filename, ANSWER_FILENAME)

    def test_collision_with_different_bytes_is_refused(self) -> None:
        place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                self.workspace_root,
                self.artifact_file("answer.md", b"different bytes\n"),
                artifact_role="final_answer",
                topic="legal_analysis",
            )
        self.assertIn("collision", str(caught.exception))
        # The original placement is untouched.
        self.assertEqual(
            (self.workspace_root / "output" / ANSWER_FILENAME).read_bytes(),
            ANSWER_BYTES,
        )

    def test_identical_replacement_is_idempotent(self) -> None:
        first = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        second = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        self.assertFalse(first.idempotent)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.sha256_lower, second.sha256_lower)

        manifest = _support.read_json_file(
            self.workspace_root / OUTPUT_MANIFEST_RELATIVE
        )
        self.assertEqual(manifest["artifact_count"], 1)

    def test_place_refuses_a_missing_source(self) -> None:
        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                self.workspace_root,
                self.root / "absent.md",
                artifact_role="final_answer",
                topic="legal_analysis",
            )
        self.assertIn("not a regular file", str(caught.exception))

    def test_place_refuses_an_unsafe_role(self) -> None:
        with self.assertRaises(RefusalError):
            place_artifact(
                self.workspace_root,
                self.artifact_file("answer.md", ANSWER_BYTES),
                artifact_role="../escape",
                topic="legal_analysis",
            )

    def test_place_does_not_inspect_content_to_choose_a_name(self) -> None:
        """A mislabelled artifact keeps its declared label."""
        result = place_artifact(
            self.workspace_root,
            self.artifact_file("notes.md", b"PK\x03\x04 this is really a zip\n"),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        self.assertEqual(result.filename, ANSWER_FILENAME)

    def test_place_requires_an_initialised_workspace(self) -> None:
        uninitialised = self.root / "uninitialised"
        uninitialised.mkdir()
        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                uninitialised,
                self.artifact_file("answer.md", ANSWER_BYTES),
                artifact_role="final_answer",
                topic="legal_analysis",
            )
        self.assertIn("not initialised", str(caught.exception))


class ValidateTests(HarnessTestCase):
    """Requirements 9, 10, 11 and 12: the completeness gate."""

    def test_missing_required_artifacts_yield_incomplete(self) -> None:
        stage_workspace(self.workspace_root)
        result = validate_workspace(self.workspace_root)

        self.assertEqual(result.status, INCOMPLETE)
        report = self.report()
        self.assertEqual(report["status"], INCOMPLETE)
        self.assertEqual(report["task_id"], "M03_R2")
        self.assertEqual(
            report["missing_required_artifacts"],
            sorted([ANSWER_FILENAME, CITATION_FILENAME]),
        )
        self.assertEqual(report["hash_mismatches"], [])
        self.assertEqual(report["integrity_errors"], [])
        self.assertEqual(report["unexpected_output_files"], [])
        self.assertEqual(report["naming_violations"], [])

    def test_one_of_two_required_artifacts_still_yields_incomplete(self) -> None:
        stage_workspace(self.workspace_root)
        place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, INCOMPLETE)
        self.assertEqual(
            result.report["missing_required_artifacts"], [CITATION_FILENAME]
        )

    def test_complete_workspace_yields_pass(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        result = validate_workspace(self.workspace_root)

        self.assertEqual(result.status, PASS)
        report = self.report()
        self.assertEqual(report["status"], PASS)
        self.assertEqual(report["missing_required_artifacts"], [])
        self.assertEqual(report["unexpected_output_files"], [])
        self.assertEqual(report["naming_violations"], [])
        self.assertEqual(report["hash_mismatches"], [])
        self.assertEqual(report["integrity_errors"], [])

    def test_report_status_matches_the_documented_schema(self) -> None:
        stage_workspace(self.workspace_root)
        validate_workspace(self.workspace_root)
        report = self.report()
        self.assertEqual(
            sorted(report),
            sorted(
                [
                    "schema_version",
                    "task_id",
                    "status",
                    "missing_required_artifacts",
                    "unexpected_output_files",
                    "naming_violations",
                    "hash_mismatches",
                    "integrity_errors",
                ]
            ),
        )

    def test_hash_mismatch_on_a_placed_artifact_is_refused(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        self.assertEqual(validate_workspace(self.workspace_root).status, PASS)

        tampered = self.workspace_root / "output" / ANSWER_FILENAME
        tampered.write_bytes(ANSWER_BYTES + b"tampered after placement\n")

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        # Two findings, because both the digest and the recorded size changed.
        # The size check is not redundant: it catches a same-length rewrite whose
        # digest comparison would be the only other signal.
        self.assertEqual(len(result.report["hash_mismatches"]), 2)
        self.assertTrue(
            all(
                ANSWER_FILENAME in mismatch
                for mismatch in result.report["hash_mismatches"]
            )
        )

    def test_hash_mismatch_on_a_staged_input_is_refused(self) -> None:
        stage_workspace(self.workspace_root)
        target = self.workspace_root / "input" / "dossier" / "README.txt"
        target.write_text("mutated\n", encoding="utf-8")

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertIn("README.txt", result.report["hash_mismatches"][0])

    def test_unexpected_output_file_is_refused(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        (self.workspace_root / "output" / "scratch_notes.txt").write_text(
            "not declared\n", encoding="utf-8"
        )

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertEqual(len(result.report["unexpected_output_files"]), 1)
        self.assertIn("scratch_notes.txt", result.report["unexpected_output_files"][0])

    def test_canonical_shaped_but_undeclared_output_is_a_naming_violation(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        (self.workspace_root / "output" / "m03_r2__other_topic__final_answer.md").write_text(
            "undeclared role/topic\n", encoding="utf-8"
        )

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertEqual(len(result.report["naming_violations"]), 1)
        self.assertEqual(result.report["unexpected_output_files"], [])

    def test_missing_output_manifest_is_an_integrity_error(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        (self.workspace_root / OUTPUT_MANIFEST_RELATIVE).unlink()

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "output manifest is missing" in item
                for item in result.report["integrity_errors"]
            )
        )

    def test_corrupt_output_manifest_is_an_integrity_error(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        (self.workspace_root / OUTPUT_MANIFEST_RELATIVE).write_text(
            "{not json", encoding="utf-8"
        )
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any("unreadable" in item for item in result.report["integrity_errors"])
        )

    def test_tampered_task_spec_is_refused(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        spec_path = self.workspace_root / "manifests" / "task_spec.json"
        document = _support.read_json_file(spec_path)
        document["task_id"] = "HACKED"
        _support.write_spec(spec_path, document)

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(result.report["integrity_errors"])

    def test_missing_task_spec_is_refused(self) -> None:
        stage_workspace(self.workspace_root)
        (self.workspace_root / "manifests" / "task_spec.json").unlink()
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "is missing" in item and "TaskSpec" in item
                for item in result.report["integrity_errors"]
            )
        )

    def test_incomplete_layout_is_an_integrity_error(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        (self.workspace_root / "checks").rmdir()
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "layout is incomplete" in item
                for item in result.report["integrity_errors"]
            )
        )

    def test_refuse_outranks_incomplete(self) -> None:
        """A tampered workspace with a missing artifact is REFUSE, not INCOMPLETE."""
        stage_workspace(self.workspace_root)
        place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        (self.workspace_root / "output" / "stray.txt").write_text("x", encoding="utf-8")

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertEqual(result.report["missing_required_artifacts"], [CITATION_FILENAME])

    def test_validation_is_repeatable_and_leaves_identical_reports(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        validate_workspace(self.workspace_root)
        first = (self.workspace_root / VALIDATION_REPORT_RELATIVE).read_bytes()
        validate_workspace(self.workspace_root)
        second = (self.workspace_root / VALIDATION_REPORT_RELATIVE).read_bytes()
        self.assertEqual(first, second)

    def test_validate_writes_a_report_even_when_refusing(self) -> None:
        stage_workspace(self.workspace_root)
        (self.workspace_root / "output" / "stray.txt").write_text("x", encoding="utf-8")
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertEqual(self.report()["status"], REFUSE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
