"""``init`` and ``stage``: workspace creation, staging, and their refusals."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support  # noqa: E402

from skills.chenhai_harness import init_workspace, stage_workspace  # noqa: E402
from skills.chenhai_harness.outcomes import RefusalError  # noqa: E402
from skills.chenhai_harness.taskspec import parse_task_spec  # noqa: E402
from skills.chenhai_harness.workspace import (  # noqa: E402
    CORE_DIRECTORIES,
    INPUT_MANIFEST_RELATIVE,
    TASK_SPEC_RELATIVE,
)

DOSSIER_FILES = {
    "README.txt": "synthetic dossier entry\n",
    "register/entry_001.txt": "synthetic register entry\n",
    "register/entry_002.txt": "another synthetic register entry\n",
}


class InitTests(unittest.TestCase):
    """Requirements 1 and 2: valid init, and invalid TaskSpec refusal."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch

    def _prepare(self, **overrides: object) -> Path:
        workspace_root = self.root / "workspace"
        spec = _support.minimal_spec(workspace_root, **overrides)
        dossier = self.root / "dossier"
        _support.make_dossier(dossier, DOSSIER_FILES)
        return _support.write_spec(self.root / "task_spec.json", spec)

    def test_valid_init_creates_exactly_the_four_core_directories(self) -> None:
        spec_path = self._prepare()
        result = init_workspace(spec_path)
        workspace_root = self.root / "workspace"

        self.assertTrue(result.created)
        self.assertFalse(result.already_initialised)
        self.assertEqual(result.task_id, "M03_R2")
        self.assertEqual(
            sorted(result.created_directories), sorted(CORE_DIRECTORIES)
        )

        entries = sorted(child.name for child in workspace_root.iterdir())
        self.assertEqual(entries, sorted(CORE_DIRECTORIES))
        self.assertNotIn("task_spec.json", entries)

    def test_init_persists_the_task_spec_verbatim_under_manifests(self) -> None:
        spec_path = self._prepare()
        init_workspace(spec_path)
        persisted = _support.read_json_file(self.root / "workspace" / TASK_SPEC_RELATIVE)
        submitted = _support.read_json_file(spec_path)
        self.assertEqual(persisted, submitted)
        # Round-trips through the validator without loss.
        self.assertEqual(parse_task_spec(persisted).to_json(), submitted)

    def test_init_is_idempotent_for_the_same_spec(self) -> None:
        spec_path = self._prepare()
        first = init_workspace(spec_path)
        second = init_workspace(spec_path)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertTrue(second.already_initialised)
        self.assertEqual(second.created_directories, ())

    def test_init_refuses_to_redefine_an_initialised_workspace(self) -> None:
        spec_path = self._prepare()
        init_workspace(spec_path)

        other = _support.minimal_spec(self.root / "workspace", task_id="M99_R9")
        other_path = _support.write_spec(self.root / "other_spec.json", other)
        with self.assertRaises(RefusalError) as caught:
            init_workspace(other_path)
        self.assertIn("different task spec", str(caught.exception))

    def test_init_refuses_a_target_holding_unrelated_content(self) -> None:
        workspace_root = self.root / "workspace"
        workspace_root.mkdir(parents=True)
        (workspace_root / "someone_elses_data.csv").write_text("a,b\n", encoding="utf-8")
        spec_path = self._prepare()

        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("not created by the harness", str(caught.exception))
        # Nothing was deleted.
        self.assertTrue((workspace_root / "someone_elses_data.csv").is_file())

    def test_init_refuses_referenced_content_in_a_managed_directory(self) -> None:
        workspace_root = self.root / "workspace"
        (workspace_root / "manifests").mkdir(parents=True)
        (workspace_root / "manifests" / "stale.json").write_text("{}", encoding="utf-8")
        spec_path = self._prepare()

        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("unreferenced content", str(caught.exception))

    def test_init_refuses_a_workspace_root_that_is_a_file(self) -> None:
        workspace_root = self.root / "workspace"
        workspace_root.write_text("not a directory", encoding="utf-8")
        spec_path = self._prepare()
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("not a directory", str(caught.exception))

    def test_invalid_schema_version_is_refused(self) -> None:
        spec_path = self._prepare(schema_version="9.9")
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("schema_version", str(caught.exception))

    def test_missing_required_field_is_refused(self) -> None:
        workspace_root = self.root / "workspace"
        spec = _support.minimal_spec(workspace_root)
        del spec["expected_artifacts"]
        _support.make_dossier(self.root / "dossier", DOSSIER_FILES)
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("missing required field", str(caught.exception))

    def test_unknown_field_is_refused_rather_than_ignored(self) -> None:
        spec_path = self._prepare(extra_field="silently dropped?")
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("unknown field", str(caught.exception))

    def test_unsupported_input_mode_is_refused(self) -> None:
        workspace_root = self.root / "workspace"
        spec = _support.minimal_spec(workspace_root)
        spec["inputs"][0]["mode"] = "move"
        _support.make_dossier(self.root / "dossier", DOSSIER_FILES)
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("unsupported mode", str(caught.exception))

    def test_duplicate_canonical_artifacts_are_refused(self) -> None:
        workspace_root = self.root / "workspace"
        spec = _support.minimal_spec(workspace_root)
        spec["expected_artifacts"].append(dict(spec["expected_artifacts"][0]))
        _support.make_dossier(self.root / "dossier", DOSSIER_FILES)
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        with self.assertRaises(RefusalError) as caught:
            init_workspace(spec_path)
        self.assertIn("collides", str(caught.exception))

    def test_missing_task_spec_file_is_refused(self) -> None:
        with self.assertRaises(RefusalError):
            init_workspace(self.root / "absent.json")


class StageTests(unittest.TestCase):
    """Requirements 4, 5 and 15: file staging, recursive staging, no mutation."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch
        self.workspace_root = self.root / "workspace"
        self.dossier = self.root / "dossier"

    def _initialise(self, files: dict[str, str] | None = None) -> None:
        _support.make_dossier(self.dossier, DOSSIER_FILES if files is None else files)
        spec = _support.minimal_spec(self.workspace_root)
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        init_workspace(spec_path)

    def test_single_file_input_is_staged_and_hashed(self) -> None:
        source = _support.make_dossier(self.root / "single", {"note.md": "hello\n"})
        spec = _support.minimal_spec(self.workspace_root)
        spec["inputs"][0]["source_path"] = str(source / "note.md")
        spec["inputs"][0]["destination"] = "input/note.md"
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        init_workspace(spec_path)

        result = stage_workspace(self.workspace_root)
        staged = self.workspace_root / "input" / "note.md"
        self.assertTrue(staged.is_file())
        self.assertEqual(staged.read_bytes(), b"hello\n")
        self.assertEqual(result.entry_count, 1)
        self.assertEqual(result.copied, ("input/note.md",))

        manifest = _support.read_json_file(
            self.workspace_root / INPUT_MANIFEST_RELATIVE
        )
        entry = manifest["entries"][0]
        self.assertEqual(entry["relative_path"], "input/note.md")
        self.assertEqual(entry["size_bytes"], 6)
        self.assertEqual(entry["sha256_lower"], _support.sha256_of(b"hello\n"))
        self.assertEqual(entry["source_path"], str(source / "note.md"))

    def test_directory_input_is_staged_recursively(self) -> None:
        self._initialise()
        result = stage_workspace(self.workspace_root)

        staged = sorted(
            path.relative_to(self.workspace_root / "input").as_posix()
            for path in (self.workspace_root / "input").rglob("*")
            if path.is_file()
        )
        self.assertEqual(
            staged,
            [
                "dossier/README.txt",
                "dossier/register/entry_001.txt",
                "dossier/register/entry_002.txt",
            ],
        )
        self.assertEqual(result.entry_count, 3)

    def test_manifest_entries_are_sorted_deterministically(self) -> None:
        self._initialise()
        stage_workspace(self.workspace_root)
        manifest_path = self.workspace_root / INPUT_MANIFEST_RELATIVE
        first = manifest_path.read_bytes()
        stage_workspace(self.workspace_root)
        self.assertEqual(manifest_path.read_bytes(), first)

        manifest = _support.read_json_file(manifest_path)
        paths = [entry["relative_path"] for entry in manifest["entries"]]
        self.assertEqual(paths, sorted(paths))

    def test_every_entry_hash_matches_the_staged_bytes(self) -> None:
        self._initialise()
        stage_workspace(self.workspace_root)
        manifest = _support.read_json_file(
            self.workspace_root / INPUT_MANIFEST_RELATIVE
        )
        for entry in manifest["entries"]:
            with self.subTest(entry=entry["relative_path"]):
                target = self.workspace_root / entry["relative_path"]
                payload = target.read_bytes()
                self.assertEqual(entry["sha256_lower"], _support.sha256_of(payload))
                self.assertEqual(entry["size_bytes"], len(payload))

    def test_original_inputs_are_not_modified(self) -> None:
        self._initialise()
        before = {
            path.relative_to(self.dossier).as_posix(): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in sorted(self.dossier.rglob("*"))
            if path.is_file()
        }
        stage_workspace(self.workspace_root)
        after = {
            path.relative_to(self.dossier).as_posix(): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in sorted(self.dossier.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(before, after)
        # The staging copy is a distinct file, not the original.
        self.assertNotEqual(
            (self.workspace_root / "input" / "dossier" / "README.txt").resolve(),
            (self.dossier / "README.txt").resolve(),
        )

    def test_missing_source_is_refused_and_no_manifest_is_written(self) -> None:
        spec = _support.minimal_spec(self.workspace_root)
        spec["inputs"][0]["source_path"] = str(self.root / "absent_dir")
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        init_workspace(spec_path)

        with self.assertRaises(RefusalError) as caught:
            stage_workspace(self.workspace_root)
        self.assertIn("does not exist", str(caught.exception))
        self.assertFalse((self.workspace_root / INPUT_MANIFEST_RELATIVE).exists())

    def test_existing_identical_staging_target_is_not_an_error(self) -> None:
        self._initialise()
        first = stage_workspace(self.workspace_root)
        second = stage_workspace(self.workspace_root)
        self.assertEqual(first.entry_count, second.entry_count)
        self.assertEqual(second.copied, ())
        self.assertEqual(
            len(second.already_present), first.entry_count
        )

    def test_existing_divergent_staging_target_is_refused(self) -> None:
        self._initialise()
        stage_workspace(self.workspace_root)
        tampered = self.workspace_root / "input" / "dossier" / "README.txt"
        tampered.write_text("replaced\n", encoding="utf-8")

        with self.assertRaises(RefusalError) as caught:
            stage_workspace(self.workspace_root)
        self.assertIn("refusing to overwrite", str(caught.exception))

    def test_empty_source_directory_is_refused(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        spec = _support.minimal_spec(self.workspace_root)
        spec["inputs"][0]["source_path"] = str(empty)
        spec_path = _support.write_spec(self.root / "task_spec.json", spec)
        init_workspace(spec_path)

        with self.assertRaises(RefusalError) as caught:
            stage_workspace(self.workspace_root)
        self.assertIn("no files to stage", str(caught.exception))

    def test_stage_requires_an_initialised_workspace(self) -> None:
        self.workspace_root.mkdir(parents=True)
        with self.assertRaises(RefusalError) as caught:
            stage_workspace(self.workspace_root)
        self.assertIn("not initialised", str(caught.exception))

    def test_corrupt_existing_manifest_is_refused(self) -> None:
        self._initialise()
        stage_workspace(self.workspace_root)
        (self.workspace_root / INPUT_MANIFEST_RELATIVE).write_text(
            "{not json", encoding="utf-8"
        )
        with self.assertRaises(RefusalError) as caught:
            stage_workspace(self.workspace_root)
        self.assertIn("unreadable", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
