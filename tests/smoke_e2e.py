"""ChenHai harness end-to-end smoke demonstration.

    python tests/smoke_e2e.py [--keep]

Runs the whole sequence against a temporary scratch directory:

1. build a synthetic TaskSpec;
2. ``init``;
3. ``stage`` the synthetic input;
4. ``validate`` -> expect INCOMPLETE;
5. ``place`` the required artifacts;
6. ``validate`` -> expect PASS;
7. verify the manifest hashes independently;
8. delete the temporary workspace.

Everything is synthetic. No calibration evidence, no private path and no
experimental artifact is read, written or required.

The scratch root is a fresh temporary directory, so the run can never write into
this repository or into a real workspace. ``--keep`` leaves it in place for
inspection and prints its path.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402  (sandbox-safe scratch directory)

from skills.chenhai_harness import (  # noqa: E402
    init_workspace,
    place_artifact,
    sha256_file,
    stage_workspace,
    validate_workspace,
)
from skills.chenhai_harness.outcomes import INCOMPLETE, PASS  # noqa: E402
from skills.chenhai_harness.workspace import (  # noqa: E402
    INPUT_MANIFEST_RELATIVE,
    OUTPUT_MANIFEST_RELATIVE,
    TASK_SPEC_RELATIVE,
    VALIDATION_REPORT_RELATIVE,
)

DEMO_DIR = PROJECT_ROOT / "fixtures" / "m03_r2_demo"
DEMO_TEMPLATE = DEMO_DIR / "task_spec.template.json"

SYNTHETIC_DOSSIER = {
    "README.txt": "synthetic dossier entry (demo only)\n",
    "register/entry_001.txt": "synthetic register entry (demo only)\n",
}

SYNTHETIC_ARTIFACTS = {
    "final_answer": (
        "legal_analysis",
        "answer.md",
        b"# Synthetic final answer\n\nNo real authority is cited here.\n",
    ),
    "citation_record": (
        "legal_analysis",
        "citations.json",
        b'{"synthetic": true, "entries": []}\n',
    ),
}


def _step(number: int, text: str) -> None:
    print(f"[smoke {number}] {text}")


def run_smoke(*, keep: bool = False, scratch: Path | None = None) -> dict:
    """Run the sequence and return a machine-readable summary.

    Raises ``AssertionError`` when an expected observation does not hold, so a
    caller can rely on the exception rather than on parsing the log.
    """
    owns_scratch = scratch is None
    if owns_scratch:
        scratch = _bootstrap.make_scratch_dir(prefix="chenhai_smoke_")
    scratch = Path(scratch).resolve()
    observations: dict[str, object] = {"scratch": str(scratch)}

    try:
        # ---------------------------------------------------------------- 1
        _step(1, "build a synthetic TaskSpec")
        dossier = scratch / "source" / "dossier"
        for relative, content in SYNTHETIC_DOSSIER.items():
            target = dossier / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        workspace_root = scratch / "workspace"
        template = _bootstrap.load_demo_spec_template()
        template["workspace_root"] = str(workspace_root)
        template["inputs"][0]["source_path"] = str(dossier)
        spec_path = scratch / "task_spec.json"
        spec_path.write_text(
            json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        observations["task_id"] = template["task_id"]
        observations["topic"] = template["topic"]

        # ---------------------------------------------------------------- 2
        _step(2, f"init {workspace_root}")
        init_result = init_workspace(spec_path)
        assert init_result.created, "init did not report creating the workspace"
        assert (workspace_root / TASK_SPEC_RELATIVE).is_file(), "TaskSpec not persisted"
        observations["init"] = init_result.to_json()

        # ---------------------------------------------------------------- 3
        _step(3, "stage the synthetic input")
        stage_result = stage_workspace(workspace_root)
        assert stage_result.entry_count == len(SYNTHETIC_DOSSIER), (
            f"staged {stage_result.entry_count} entries, "
            f"expected {len(SYNTHETIC_DOSSIER)}"
        )
        observations["stage"] = stage_result.to_json()

        # ---------------------------------------------------------------- 4
        _step(4, "validate -> expect INCOMPLETE")
        first = validate_workspace(workspace_root)
        assert first.status == INCOMPLETE, f"expected INCOMPLETE, got {first.status}"
        assert first.report["missing_required_artifacts"], "no missing artifact reported"
        observations["validate_incomplete"] = first.report
        print(f"           status={first.status}")

        # ---------------------------------------------------------------- 5
        _step(5, "place the required artifacts")
        placed = []
        for index, (role, (topic, filename, payload)) in enumerate(
            SYNTHETIC_ARTIFACTS.items()
        ):
            source = scratch / "produced" / f"{index}_{filename}"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(payload)
            placed.append(
                place_artifact(
                    workspace_root, source, artifact_role=role, topic=topic
                ).to_json()
            )
        observations["place"] = placed

        # ---------------------------------------------------------------- 6
        _step(6, "validate -> expect PASS")
        second = validate_workspace(workspace_root)
        assert second.status == PASS, (
            f"expected PASS, got {second.status}: {json.dumps(second.report)}"
        )
        observations["validate_pass"] = second.report
        print(f"           status={second.status}")

        # ---------------------------------------------------------------- 7
        _step(7, "verify manifest hashes independently")
        verified = _verify_manifests(workspace_root)
        observations["verified_hashes"] = verified
        assert verified["entries_checked"] > 0, "no manifest entries were verified"
        assert verified["mismatches"] == [], f"hash mismatches: {verified['mismatches']}"
        print(
            f"           checked {verified['entries_checked']} manifest entries, "
            "all digests match"
        )

        observations["ok"] = True
        return observations
    finally:
        # ------------------------------------------------------------------ 8
        if keep:
            _step(8, f"keeping the temporary workspace: {scratch}")
        else:
            _step(8, f"deleting the temporary workspace: {scratch}")
            shutil.rmtree(scratch, ignore_errors=True)


def _verify_manifests(workspace_root: Path) -> dict[str, object]:
    """Re-hash every recorded file and compare against the manifest."""
    mismatches: list[str] = []
    checked = 0
    manifests = (
        (workspace_root / INPUT_MANIFEST_RELATIVE, "entries"),
        (workspace_root / OUTPUT_MANIFEST_RELATIVE, "artifacts"),
    )
    for manifest_path, key in manifests:
        if not manifest_path.is_file():
            mismatches.append(f"{manifest_path.name}: manifest missing")
            continue
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in document[key]:
            checked += 1
            target = workspace_root / entry["relative_path"]
            if not target.is_file():
                mismatches.append(f"{entry['relative_path']}: missing")
                continue
            actual = sha256_file(target)
            if actual != entry["sha256_lower"]:
                mismatches.append(
                    f"{entry['relative_path']}: {actual} != {entry['sha256_lower']}"
                )
            if target.stat().st_size != entry["size_bytes"]:
                mismatches.append(
                    f"{entry['relative_path']}: size {target.stat().st_size} "
                    f"!= {entry['size_bytes']}"
                )
    report = workspace_root / VALIDATION_REPORT_RELATIVE
    return {
        "entries_checked": checked,
        "mismatches": mismatches,
        "validation_report_present": report.is_file(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the temporary smoke workspace in place for inspection",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_smoke(keep=args.keep)
    except AssertionError as error:
        print(f"SMOKE_FAILED: {error}")
        return 1

    print("SMOKE_SUMMARY " + json.dumps(
        {
            "ok": summary["ok"],
            "task_id": summary["task_id"],
            "validate_incomplete": summary["validate_incomplete"]["status"],
            "validate_pass": summary["validate_pass"]["status"],
            "entries_checked": summary["verified_hashes"]["entries_checked"],
        },
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
