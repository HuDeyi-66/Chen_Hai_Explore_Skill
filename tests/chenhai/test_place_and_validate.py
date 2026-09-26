"""``place`` and ``validate``: placement, manifests, the completeness gate."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support  # noqa: E402

from skills.chenhai_harness import (  # noqa: E402
    init_workspace,
    place_artifact,
    stage_workspace,
    validate_workspace,
)
from skills.chenhai_harness.__main__ import main  # noqa: E402
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


class ManifestCoverageTests(HarnessTestCase):
    """CH-001: the manifest must account for every managed input/output file.

    Hash checking alone proves existing entries are accurate. These tests cover
    the other direction: that the manifest's path set equals the filesystem's,
    so an unlisted file cannot hide inside a managed directory while validation
    still reports ``PASS``.
    """

    def output_manifest_path(self) -> Path:
        return self.workspace_root / OUTPUT_MANIFEST_RELATIVE

    def test_validate_refuses_required_output_omitted_from_manifest(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        self.assertEqual(validate_workspace(self.workspace_root).status, PASS)

        # The managed output file still exists and still hashes correctly; only
        # its manifest entry is gone.
        document = _support.read_json_file(self.output_manifest_path())
        document["artifacts"] = []
        document["artifact_count"] = 0
        self.output_manifest_path().write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "not recorded in the output manifest" in item
                for item in result.report["hash_mismatches"]
            ),
            result.report["hash_mismatches"],
        )

    def test_validate_refuses_unlisted_staged_input(self) -> None:
        stage_workspace(self.workspace_root)
        self.assertEqual(
            validate_workspace(self.workspace_root).status, INCOMPLETE
        )

        smuggled = self.workspace_root / "input" / "dossier" / "unlisted.txt"
        smuggled.write_bytes(b"never staged through the manifest\n")

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "not recorded in the input manifest" in item
                for item in result.report["hash_mismatches"]
            ),
            result.report["hash_mismatches"],
        )

    def test_validate_refuses_duplicate_manifest_entries(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()

        path = self.output_manifest_path()
        document = _support.read_json_file(path)
        duplicated = list(document["artifacts"])
        duplicated.append(dict(document["artifacts"][0]))
        document["artifacts"] = duplicated
        document["artifact_count"] = len(duplicated)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "recorded 2 times in the output manifest" in item
                for item in result.report["hash_mismatches"]
            ),
            result.report["hash_mismatches"],
        )

    def test_validate_refuses_input_manifest_entry_without_a_file(self) -> None:
        stage_workspace(self.workspace_root)
        # Remove a staged file while leaving its manifest entry in place, so the
        # manifest points at something that no longer exists.
        (self.workspace_root / "input" / "dossier" / "README.txt").unlink()

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "recorded in the input manifest but missing on disk" in item
                for item in result.report["hash_mismatches"]
            ),
            result.report["hash_mismatches"],
        )

    def test_empty_workspace_without_manifests_is_not_a_coverage_failure(self) -> None:
        """A freshly initialised workspace has nothing to account for."""
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, INCOMPLETE)
        self.assertEqual(result.report["hash_mismatches"], [])

    def test_covered_manifests_pass(self) -> None:
        """The positive direction, so the check cannot pass by always refusing."""
        stage_workspace(self.workspace_root)
        self.place_both()
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, PASS)
        self.assertEqual(result.report["hash_mismatches"], [])
        self.assertEqual(result.report["integrity_errors"], [])


class DeclarationGateTests(HarnessTestCase):
    """CH-002: place accepts declared artifacts only, and writes nothing on refuse."""

    def test_place_refuses_undeclared_artifact_without_writing(self) -> None:
        manifest_path = self.workspace_root / OUTPUT_MANIFEST_RELATIVE
        manifest_before = manifest_path.read_bytes() if manifest_path.is_file() else None

        source = self.artifact_file("rogue.md", b"# undeclared artifact\n")
        source_before = source.read_bytes()

        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                self.workspace_root,
                source,
                artifact_role="rogue_role",
                topic="rogue_topic",
            )
        self.assertIn("does not declare", str(caught.exception))

        # No output file, no manifest mutation, no partial write, no stray temp.
        output_entries = sorted(p.name for p in (self.workspace_root / "output").iterdir())
        self.assertEqual(output_entries, [])
        self.assertFalse(manifest_path.exists())
        if manifest_before is not None:
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
        # The source is untouched and never consumed.
        self.assertEqual(source.read_bytes(), source_before)

    def test_place_refuses_undeclared_topic_even_when_role_matches(self) -> None:
        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                self.workspace_root,
                self.artifact_file("answer.md", ANSWER_BYTES),
                artifact_role="final_answer",
                topic="undeclared_topic",
            )
        self.assertIn("does not declare", str(caught.exception))
        self.assertEqual(sorted(p.name for p in (self.workspace_root / "output").iterdir()), [])

    def test_place_refuses_undeclared_extension_even_when_role_and_topic_match(self) -> None:
        with self.assertRaises(RefusalError) as caught:
            place_artifact(
                self.workspace_root,
                self.artifact_file("answer.txt", ANSWER_BYTES),
                artifact_role="final_answer",
                topic="legal_analysis",
                extension=".txt",
            )
        self.assertIn("does not declare", str(caught.exception))
        self.assertEqual(sorted(p.name for p in (self.workspace_root / "output").iterdir()), [])

    def test_declaration_match_uses_the_same_normalization_as_the_filename(self) -> None:
        """A differently-spelled but equivalent declaration must still match."""
        result = place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="  Final_Answer  ",
            topic="Legal Analysis",
        )
        self.assertEqual(result.filename, ANSWER_FILENAME)
        self.assertFalse(result.idempotent)

    def test_refusal_does_not_mutate_an_existing_manifest(self) -> None:
        stage_workspace(self.workspace_root)
        place_artifact(
            self.workspace_root,
            self.artifact_file("answer.md", ANSWER_BYTES),
            artifact_role="final_answer",
            topic="legal_analysis",
        )
        manifest_path = self.workspace_root / OUTPUT_MANIFEST_RELATIVE
        before = manifest_path.read_bytes()

        with self.assertRaises(RefusalError):
            place_artifact(
                self.workspace_root,
                self.artifact_file("rogue.md", b"# undeclared\n"),
                artifact_role="rogue_role",
                topic="rogue_topic",
            )
        self.assertEqual(manifest_path.read_bytes(), before)


class EscapedChecksDirectoryTests(HarnessTestCase):
    """CH-003: validation must never write through an escaped checks directory."""

    def _make_junction(self, link: Path, target: Path) -> bool:
        """Create a Windows directory junction. Returns False when unavailable.

        A junction exercises the real thing this blocker is about: a path that
        *resolves* outside the workspace while still sitting at the expected
        lexical location. A ``..`` traversal cannot express that and is
        deliberately not used as a substitute.
        """
        if os.name != "nt":
            return False
        target.mkdir(parents=True, exist_ok=True)
        if link.exists():
            if link.is_symlink() or os.path.islink(str(link)):
                link.unlink()
            else:
                shutil.rmtree(link, ignore_errors=True)
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0 and link.exists()

    def test_validate_refuses_escaped_checks_junction_without_external_write(self) -> None:
        external = self.root / "external_target"
        link = self.workspace_root / "checks"
        if not self._make_junction(link, external):
            self.skipTest("directory junctions are not available on this platform")

        # Make the workspace unsafe so REFUSE is the expected status, which is
        # exactly the path that previously wrote the report through the junction.
        (self.workspace_root / "output" / "stray.txt").write_text("x", encoding="utf-8")

        result = validate_workspace(self.workspace_root)

        self.assertEqual(result.status, REFUSE)
        self.assertTrue(
            any(
                "checks/" in item and "path boundary" in item
                for item in result.report["integrity_errors"]
            ),
            result.report["integrity_errors"],
        )
        # The refusal was returned to the caller even though it was not persisted.
        self.assertFalse(result.report_written)
        # Nothing at all was written across the boundary.
        self.assertEqual(
            sorted(p.name for p in external.iterdir()),
            [],
            "validation wrote through the escaped checks directory",
        )
        self.assertFalse((external / "validation_report.json").exists())
        self.assertFalse((external / "validation_report.json.tmp").exists())

    def test_validate_does_not_fall_back_to_any_outside_directory(self) -> None:
        """No parent, repository root, profile or temp fallback may be used."""
        external = self.root / "external_target_2"
        link = self.workspace_root / "checks"
        if not self._make_junction(link, external):
            self.skipTest("directory junctions are not available on this platform")

        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, REFUSE)
        self.assertFalse(result.report_written)
        self.assertEqual(sorted(p.name for p in external.iterdir()), [])
        # The report path still names the in-workspace location; it simply was
        # not persisted, which is the documented MVP behaviour.
        self.assertEqual(
            Path(result.report_path),
            self.workspace_root / VALIDATION_REPORT_RELATIVE,
        )
        self.assertFalse(Path(result.report_path).exists())

    def test_safe_checks_directory_still_persists_the_report(self) -> None:
        """The guard must not disable report writing in the normal case."""
        stage_workspace(self.workspace_root)
        result = validate_workspace(self.workspace_root)
        self.assertEqual(result.status, INCOMPLETE)
        self.assertTrue(result.report_written)
        self.assertTrue((self.workspace_root / VALIDATION_REPORT_RELATIVE).is_file())


class CliExitCodeTests(HarnessTestCase):
    """CLI exit codes for the three patched refusal paths."""

    def _run(self, arguments: list[str]) -> int:
        return main(arguments)

    def test_undeclared_place_exit_code_is_three(self) -> None:
        source = self.artifact_file("rogue.md", b"# undeclared\n")
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = self._run(
                [
                    "place",
                    str(self.workspace_root),
                    str(source),
                    "--role",
                    "rogue_role",
                    "--topic",
                    "rogue_topic",
                ]
            )
        self.assertEqual(code, 3)
        self.assertIn("REFUSE", buffer.getvalue())
        self.assertEqual(sorted(p.name for p in (self.workspace_root / "output").iterdir()), [])

    def test_manifest_coverage_failure_exit_code_is_three(self) -> None:
        stage_workspace(self.workspace_root)
        self.place_both()
        manifest_path = self.workspace_root / OUTPUT_MANIFEST_RELATIVE
        document = _support.read_json_file(manifest_path)
        document["artifacts"] = []
        document["artifact_count"] = 0
        manifest_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self._run(["validate", str(self.workspace_root)])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "REFUSE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
