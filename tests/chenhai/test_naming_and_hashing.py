"""Naming, hashing, path safety and atomic writes.

These are the four primitives every operation depends on. Testing them directly
means a failure elsewhere can be attributed to an operation rather than to a
shared helper that quietly does the wrong thing.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support  # noqa: E402

from skills.chenhai_harness import hashing, jsonio, naming  # noqa: E402
from skills.chenhai_harness.paths import (  # noqa: E402
    UnsafePathError,
    relative_destination,
    require_absolute,
    resolve_input_source,
    resolve_under,
)
from skills.chenhai_harness.taskspec import parse_task_spec  # noqa: E402


class SemanticNamingTests(unittest.TestCase):
    """Requirement 7: canonical, deterministic filename generation."""

    def test_canonical_filename_matches_the_documented_shape(self) -> None:
        self.assertEqual(
            naming.canonical_filename(
                task_id="M03_R2",
                topic="legal_analysis",
                artifact_role="final_answer",
                extension=".md",
            ),
            "m03_r2__legal_analysis__final_answer.md",
        )

    def test_normalization_is_deterministic_and_lowercases_ascii(self) -> None:
        first = naming.normalize_component("  MiXeD  Case  ", field="topic")
        second = naming.normalize_component("  MiXeD  Case  ", field="topic")
        self.assertEqual(first, "mixed_case")
        self.assertEqual(first, second)

    def test_separator_runs_collapse_to_a_single_underscore(self) -> None:
        for raw in ("a   b", "a---b", "a...b", "a - _ b", "  a.b  "):
            with self.subTest(raw=raw):
                self.assertEqual(naming.normalize_component(raw, field="topic"), "a_b")

    def test_embedded_double_dot_is_not_a_traversal(self) -> None:
        """``a...b`` is ordinary text and collapses; a standalone ``..`` does not."""
        self.assertEqual(naming.normalize_component("a...b", field="topic"), "a_b")
        for raw in ("..", "../x", "x/..", "x/../y", ".\\..\\y"):
            with self.subTest(raw=raw):
                with self.assertRaises(UnsafePathError):
                    naming.normalize_component(raw, field="topic")

    def test_unicode_is_preserved_after_nfkc(self) -> None:
        # Full-width digits normalise to ASCII; non-ASCII letters are kept as
        # written, because transliterating them would be an inference.
        self.assertEqual(
            naming.normalize_component("Ｍ０３＿Ｒ２", field="task_id"), "m03_r2"
        )
        self.assertEqual(
            naming.normalize_component("海琛 R2", field="topic"), "海琛_r2"
        )

    def test_path_separators_are_refused(self) -> None:
        for raw in ("a/b", "a\\b", "../etc", "..", ".", "a/../b"):
            with self.subTest(raw=raw):
                with self.assertRaises(UnsafePathError):
                    naming.normalize_component(raw, field="topic")

    def test_component_that_normalises_to_nothing_is_refused(self) -> None:
        for raw in ("   ", "---", "...", "///", "__"):
            with self.subTest(raw=raw):
                with self.assertRaises(UnsafePathError):
                    naming.normalize_component(raw, field="artifact_role")

    def test_extension_normalization_and_inference(self) -> None:
        self.assertEqual(naming.normalize_extension("md"), ".md")
        self.assertEqual(naming.normalize_extension("  .MD  "), ".md")
        self.assertEqual(naming.extract_extension("answer.md"), ".md")
        self.assertEqual(naming.extract_extension("C:\\tmp\\answer.JSON"), ".json")
        for raw in (".", "..", ".m d", ".m/d", ""):
            with self.subTest(raw=raw):
                with self.assertRaises(UnsafePathError):
                    naming.normalize_extension(raw)

    def test_extension_is_never_inferred_from_a_suffixless_name(self) -> None:
        with self.assertRaises(UnsafePathError):
            naming.extract_extension("answer")

    def test_documented_rules_declare_no_content_inference(self) -> None:
        rules = naming.describe_rules()
        self.assertFalse(rules["content_inference"])
        self.assertEqual(rules["separator"], "__")
        self.assertIn("..", " ".join(str(item) for item in rules["rejects"]))


class HashTests(unittest.TestCase):
    """Requirement 6: SHA-256 correctness, checked against known vectors."""

    def test_empty_payload_matches_the_published_vector(self) -> None:
        self.assertEqual(
            hashing.sha256_bytes(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_known_vector_abc(self) -> None:
        self.assertEqual(
            hashing.sha256_bytes(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_file_digest_matches_an_independent_computation(self) -> None:
        scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, scratch)
        target = scratch / "payload.bin"
        payload = bytes(range(256)) * 4096  # exercises the chunked reader
        target.write_bytes(payload)
        self.assertEqual(
            hashing.sha256_file(target), hashlib.sha256(payload).hexdigest()
        )

    def test_digest_is_lowercase_hex_of_fixed_length(self) -> None:
        digest = hashing.sha256_bytes(b"anything")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())
        int(digest, 16)

    def test_identical_files_are_recognised(self) -> None:
        scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, scratch)
        first = scratch / "a.bin"
        second = scratch / "b.bin"
        third = scratch / "c.bin"
        first.write_bytes(b"same")
        second.write_bytes(b"same")
        third.write_bytes(b"different")
        self.assertTrue(hashing.files_are_identical(first, second))
        self.assertFalse(hashing.files_are_identical(first, third))


class SafePathTests(unittest.TestCase):
    """Requirement 3: path traversal refusal."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch / "workspace"
        self.root.mkdir(parents=True)

    def test_resolve_under_accepts_a_child(self) -> None:
        child = self.root / "output" / "artifact.md"
        self.assertEqual(resolve_under(self.root, child, field="x"), child.resolve())

    def test_resolve_under_refuses_a_sibling_and_a_parent(self) -> None:
        outside = self.root.parent / "elsewhere"
        with self.assertRaises(UnsafePathError):
            resolve_under(self.root, outside, field="x")
        with self.assertRaises(UnsafePathError):
            resolve_under(self.root, self.root.parent, field="x")

    def test_resolve_under_refuses_a_dot_dot_escape(self) -> None:
        escaping = self.root / "output" / ".." / ".." / "escaped.md"
        with self.assertRaises(UnsafePathError):
            resolve_under(self.root, escaping, field="x")

    def test_require_absolute_refuses_relative_and_dot_dot(self) -> None:
        with self.assertRaises(UnsafePathError):
            require_absolute("relative/root", field="workspace_root")
        with self.assertRaises(UnsafePathError):
            require_absolute("D:/a/../b" if os.name == "nt" else "/a/../b", field="workspace_root")

    def test_relative_destination_refuses_absolute_and_escape(self) -> None:
        for raw in (
            "/etc/passwd",
            "D:/outside/x",
            "C:\\outside\\x",
            "../outside",
            "input/../../outside",
            "",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(UnsafePathError):
                    relative_destination(raw, field="destination")

    def test_resolve_input_source_refuses_dot_dot(self) -> None:
        with self.assertRaises(UnsafePathError):
            resolve_input_source("../secrets", workspace_root=self.root, field="source_path")

    def test_spec_refuses_a_destination_outside_input(self) -> None:
        spec = _support.minimal_spec(self.root)
        spec["inputs"][0]["destination"] = "output/dossier"
        with self.assertRaises(UnsafePathError):
            parse_task_spec(spec)

    def test_spec_refuses_a_traversing_destination(self) -> None:
        spec = _support.minimal_spec(self.root)
        spec["inputs"][0]["destination"] = "input/../../escaped"
        with self.assertRaises(UnsafePathError):
            parse_task_spec(spec)

    def test_spec_refuses_a_traversing_source(self) -> None:
        spec = _support.minimal_spec(self.root)
        spec["inputs"][0]["source_path"] = "../../etc"
        with self.assertRaises(UnsafePathError):
            parse_task_spec(spec)

    def test_spec_refuses_a_relative_workspace_root(self) -> None:
        spec = _support.minimal_spec(self.root)
        spec["workspace_root"] = "relative/workspace"
        with self.assertRaises(UnsafePathError):
            parse_task_spec(spec)

    def test_spec_refuses_an_artifact_role_with_a_separator(self) -> None:
        spec = _support.minimal_spec(self.root)
        spec["expected_artifacts"][0]["artifact_role"] = "../escape"
        with self.assertRaises(UnsafePathError):
            parse_task_spec(spec)


class AtomicWriteTests(unittest.TestCase):
    """Requirement: atomic manifest writes with deterministic serialisation."""

    def setUp(self) -> None:
        self._scratch = _support.BOOTSTRAP.make_scratch_dir()
        self.addCleanup(_support.BOOTSTRAP.remove_scratch_dir, self._scratch)
        self.root = self._scratch

    def test_serialisation_is_deterministic_and_key_sorted(self) -> None:
        payload = {"b": 1, "a": {"d": 4, "c": 3}}
        first = jsonio.dumps(payload)
        second = jsonio.dumps(payload)
        self.assertEqual(first, second)
        self.assertLess(first.index('"a"'), first.index('"b"'))
        self.assertTrue(first.endswith("\n"))
        self.assertNotIn("\r", first)

    def test_key_order_in_the_source_does_not_change_the_bytes(self) -> None:
        self.assertEqual(
            jsonio.dumps({"a": 1, "b": 2}), jsonio.dumps({"b": 2, "a": 1})
        )

    def test_atomic_write_leaves_no_temporary_files(self) -> None:
        target = self.root / "manifests" / "input_manifest.json"
        jsonio.atomic_write_json(target, {"entries": []})
        self.assertTrue(target.is_file())
        leftovers = [
            child.name for child in target.parent.iterdir() if child.name != target.name
        ]
        self.assertEqual(leftovers, [])

    def test_atomic_write_replaces_existing_content_completely(self) -> None:
        target = self.root / "report.json"
        jsonio.atomic_write_json(target, {"status": "REFUSE", "padding": "x" * 4096})
        jsonio.atomic_write_json(target, {"status": "PASS"})
        self.assertEqual(
            json.loads(target.read_text(encoding="utf-8")), {"status": "PASS"}
        )

    def test_read_json_reports_malformed_documents_as_value_error(self) -> None:
        target = self.root / "broken.json"
        target.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            jsonio.read_json(target)

    def test_read_json_accepts_a_utf8_byte_order_mark(self) -> None:
        """Windows editors and PowerShell write a BOM by default."""
        target = self.root / "bom.json"
        target.write_bytes(
            b"\xef\xbb\xbf" + jsonio.dumps({"task_id": "M03_R2"}).encode("utf-8")
        )
        self.assertEqual(jsonio.read_json(target), {"task_id": "M03_R2"})

    def test_written_documents_never_contain_a_bom(self) -> None:
        target = self.root / "clean.json"
        jsonio.atomic_write_json(target, {"task_id": "M03_R2"})
        self.assertFalse(target.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
