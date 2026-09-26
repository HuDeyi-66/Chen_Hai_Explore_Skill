[English](./README.md) | [简体中文](./README.zh-CN.md) | [繁體中文](./README.zh-TW.md) | [日本語](./README.ja.md)

# ChenHai（海琛）

**Evidence Exploration and Evaluation Skill**

> ChenHai asks whether the evidence is sufficient.
>
> It also helps ensure that evidence is produced inside a disciplined, auditable
> environment.

**Development status: Reserved / Planned; Evidence Discipline Harness MVP implemented**

This repository is the canonical future implementation home of the Skill. Its
initial commits preserve the Skill contract, architectural boundary, and planned
public interface. The first minimal runtime slice — the Evidence Discipline
Harness MVP — is now implemented under `skills/chenhai_harness/` and documented
below. The evidence sufficiency role remains designed but not implemented.

## What it is

ChenHai is the SeaFlow Skill responsible for evidence exploration and evaluation.
It assesses whether the evidence currently held is enough, identifies unresolved
evidence gaps, and produces retry or recovery recommendations for orchestration.

ChenHai evaluates evidence sufficiency and helps construct disciplined, auditable
evidence environments. The second half of that sentence is an extension of the
first, not a replacement for it.

## Why it exists

A retrieval pipeline can return results and still leave a matter under-supported.
Someone has to judge coverage, name the insufficiency, and say what should be
retried. ChenHai exists so that this judgement is explicit, inspectable and
separable from both retrieval and final legal reasoning.

## Core responsibilities

- evidence coverage assessment;
- insufficiency detection;
- retrieval-risk and recall-risk signals;
- benchmark precision / recall evaluation when qrels exist;
- runtime coverage proxies where full ground truth is unavailable;
- identification of unresolved evidence gaps;
- production of retry and recovery recommendations for orchestration.

Extended role — evidence discipline:

- evidence discipline over how evidence is organized and handled;
- output naming discipline for evidence artifacts;
- construction and validation of a controlled evaluation workspace;
- evidence-environment validation before a formal evidence task runs.

The original sufficiency role is preserved. Evidence discipline is an extension of
it, not a redefinition of the Skill.

## Evidence boundary

ChenHai does **not**:

- retrieve evidence itself;
- invent missing evidence;
- silently fill gaps;
- make final normative or legal judgments;
- directly mutate canonical evidence;
- act as a generic file manager;
- act as a general workflow engine;
- rename arbitrary user files unrelated to evidence tasks;
- decide substantive content merely from filename policy;
- create fake audit evidence;
- reconstruct missing historical evidence after the fact.

Architecture rule: ChenHai detects insufficiency and requests recovery. XianHai
decides temporal and recovery orchestration. Retrieval Skills perform retrieval.

## Evidence Discipline Harness

ChenHai constrains both the **sufficiency** of evidence and the **discipline of the
environment** in which evidence is processed. The second concern is described here
as the Evidence Discipline Harness: an evidentiary constraint layer, not a general
filesystem feature and not an enterprise orchestration framework.

In practice, ChenHai may constrain what evidence is available, where the
evidence-processing task occurs, what outputs are expected, how those outputs are
named, what may or may not be written or accessed, and how the resulting evidence
state can later be audited.

### Semantic output naming

Evidence outputs should be named so they are identifiable by topic and by artifact
role. ChenHai may define or enforce naming rules, preferring patterns of the form
`<topic>_<artifact-role>.<ext>`, or where context requires
`<case-or-task>_<topic>_<artifact-role>.<ext>`.

Illustrative shapes (not frozen conventions):

```
collision_liability_evidence_ledger.csv
missing_authority_assessment.md
route_source_inventory.json
port_law_conflict_matrix.csv
```

Ambiguous labels such as `output1.txt`, `result_final.md`, `data_new.json` or
`test2.csv` should be avoided, because they do not communicate subject, role or
provenance and make later audit harder.

The naming convention is expected to evolve; no rigid universal filename grammar is
frozen at this stage. The architectural requirement is that filenames communicate
subject and evidence/artifact role, avoid meaningless generic labels, improve
traceability and later auditability, and be deterministic where practical.

The harness MVP implements a concrete, deterministic instance of this requirement:
`<normalized_task_id>__<normalized_topic>__<normalized_artifact_role><extension>`,
for example `m03_r2__legal_analysis__final_answer.md`. See the Evidence Discipline
Harness MVP section below.

ChenHai constrains output naming. It does **not** fabricate file content merely to
satisfy a naming rule.

### Controlled evidence workspace

Before a formal evidence task, ChenHai may help construct or validate a
purpose-specific environment — conceptually, "building the exam room" before the
task is attempted. The environment establishes allowed inputs, frozen evidence
sources, writable output locations, prohibited paths, expected artifacts, evidence
manifests, task-specific constraints, evaluation rules, integrity checks and
failure conditions.

The conceptual sequence is:

```
define task
    ↓
define evidence boundary
    ↓
construct controlled workspace
    ↓
freeze / identify permitted inputs
    ↓
define expected outputs
    ↓
perform task
    ↓
evaluate evidence sufficiency and integrity
```

The purpose is to reduce evidence contamination, accidental access to forbidden
material, ambiguous provenance, uncontrolled writes, stale or unrelated context,
post-hoc reconstruction and evaluation leakage.

Planned conceptual elements — documented as intent. The MVP now implements the
semantic naming policy, the controlled workspace specification, the expected
artifact declaration, the completeness gate and the integrity check; the remaining
elements are still intent only:

- ControlledEvidenceWorkspace
- Input boundary
- Output boundary
- Evidence manifest
- Expected artifact set
- Semantic naming policy
- Read/write boundary
- Frozen-source declaration
- Integrity verification
- Completeness gate
- Failure / refusal state

Beyond the harness MVP, no further runtime class, package, schema or sandbox API
is designed or claimed to exist. The MVP implements no sandbox API and claims
none.

## Evidence Discipline Harness MVP

The first minimal runtime slice of the harness is implemented in this repository
under [`skills/chenhai_harness/`](./skills/chenhai_harness/). It is a small
deterministic filesystem harness. It contains **no LLM dependency**, performs no
retrieval, performs no semantic inference, and makes no judgement about whether an
artifact's content is substantively correct.

The purpose is not to improve retrieval quality. The purpose is to reduce manual
experiment and evidence workspace handling.

### Why the harness exists

Producing evidence under controlled conditions is not only a matter of producing
the right bytes. Which inputs were permitted, what was expected, what was actually
produced, and whether any of it has changed since are questions that otherwise
depend on human discipline and on someone's memory of what they did. The harness
makes those questions mechanical rather than remembered.

### The four operations

```
TaskSpec
    ↓
init       controlled workspace
    ↓
stage      allowed inputs
    ↓
place      declared artifacts
    ↓
hash / manifest
    ↓
validate   expected outputs
    ↓
PASS / INCOMPLETE / REFUSE
```

The workspace contains only four directories, and no deeper hierarchy:

```
<workspace_root>/
    input/
    output/
    manifests/
    checks/
```

| Operation | Purpose |
| --- | --- |
| `init` | Validate the TaskSpec and create the workspace. Persists the spec at `manifests/task_spec.json`. Refuses incompatible existing content instead of deleting or resetting it. |
| `stage` | Copy declared inputs (`mode: "copy"`; single files or directories recursively) into `input/` and record `relative_path`, `size_bytes`, `sha256_lower` and `source_path` for every staged file in `manifests/input_manifest.json`. Original inputs are never modified. |
| `place` | Copy an already-produced artifact into `output/` under its canonical filename and update `manifests/output_manifest.json`. Copies rather than moves, never inspects the artifact's content, refuses a collision unless the bytes are identical, and is idempotent when they are. |
| `validate` | Check TaskSpec integrity, workspace layout, required artifacts, canonical filename compliance, expected location, manifest/file hash consistency, unexpected files in the controlled output directory, and path-boundary violations. Writes `checks/validation_report.json`. |

```
python -m skills.chenhai_harness init <task_spec.json>
python -m skills.chenhai_harness stage <workspace>
python -m skills.chenhai_harness place <workspace> <source_file> --role final_answer --topic legal_analysis
python -m skills.chenhai_harness validate <workspace>
```

Exit codes: `0` PASS or successful operation, `2` INCOMPLETE, `3` REFUSE, and `1`
for an unexpected internal error. `2` and `3` are deliberately distinct: a caller
must be able to tell "not finished yet" from "not trustworthy".

### TaskSpec

JSON only, schema version `0.1`, with the required top-level fields
`schema_version`, `task_id`, `topic`, `workspace_root`, `inputs` and
`expected_artifacts`. Unknown fields are refused rather than silently dropped. The
only supported staging `mode` is `copy`, and `inputs[].destination` must stay
inside `input/`.

### Naming convention

```
<normalized_task_id>__<normalized_topic>__<normalized_artifact_role><extension>
```

Example: `m03_r2__legal_analysis__final_answer.md`.

Normalisation is deterministic: NFKC, surrounding whitespace trimmed, ASCII
lowercased, runs of characters that are not ASCII `[a-z0-9]` or Unicode
alphanumerics collapsed to a single underscore, path separators and standalone
`..` rejected, empty results rejected. Names come from the TaskSpec or from an
explicit command argument only — **never** from inspecting file content.

### PASS / INCOMPLETE / REFUSE

- **PASS** — all required artifacts present, canonically named, and
  hash-consistent.
- **INCOMPLETE** — the workspace is valid but one or more required expected
  artifacts are missing.
- **REFUSE** — invalid spec, unsafe path, naming violation, manifest corruption,
  hash mismatch, collision, or another integrity violation, including an
  unexpected file inside the controlled output directory. `REFUSE` takes
  precedence over `INCOMPLETE`.

### Explicit limitation: this is not an OS sandbox

**This MVP is not an operating-system sandbox.** It does not prevent an external
model, process or user from reading or writing arbitrary paths. It implements no
filesystem isolation, and none should be inferred from the checks it performs.

What it does do is narrow and specific: it constructs a controlled workspace,
constrains the paths its own operations will construct and write, stages known
inputs, records manifests, constrains and validates managed outputs, and validates
the resulting workspace. The path checks constrain what *this harness* will do —
not what any other program can do.

Correspondingly, the harness is not a general file manager, does not rename
unrelated user files, does not retrieve evidence, does not mutate canonical
evidence, and does not decide whether an artifact is substantively correct. It is
evidence-workspace discipline only.

### Tests and demo

```
python tests/run_all.py     # unittest discovery
pytest tests                # the same suite
python tests/smoke_e2e.py   # synthetic end-to-end demonstration
```

The suite covers workspace creation, invalid-spec refusal, path-traversal refusal,
file and recursive-directory staging, SHA-256 correctness, semantic filename
generation, artifact placement, collision refusal, identical-placement
idempotence, missing-artifact `INCOMPLETE`, complete-workspace `PASS`, hash
mismatch `REFUSE`, unexpected-output `REFUSE`, and non-mutation of original
inputs.

`fixtures/m03_r2_demo/` holds one small synthetic demo. It contains no real
calibration evidence, no private path and no private experimental artifact.

### Boundary of the harness

The capability constrains evidence handling. It does not manufacture evidence.

ChenHai may define the evaluation "room". It does not retrieve the evidence itself,
does not own temporal orchestration, does not own provenance graph semantics, and
does not become a general filesystem manager or a general workflow engine.

## How it fits into SeaFlow

```
Evidence acquisition / assets
    ↓
ShanHai / LuoHai / WenHai / future Visual Evidence
    ↓
XianHai
temporal organization / gaps / recheck
    ↕
JueHai
relationships / provenance paths
    ↓
ChenHai
coverage / insufficiency / evaluation
    ↓
recovery request when evidence is insufficient
```

This is an architectural relationship, not implemented coupling. No hard runtime
dependency between these Skills exists at this stage.

Skill boundaries remain clean:

| Skill | Owns |
| --- | --- |
| ShanHai | retrieves / structures legal textual evidence |
| LuoHai | handles structured / tabular evidence |
| WenHai | registers and preserves documentary assets |
| XianHai | organizes evidence temporally, manages temporal gaps / rechecks |
| JueHai | connects evidence through graph relations and provenance paths |
| ChenHai | evaluates sufficiency **and** constrains the evidence-evaluation environment |

ChenHai may define the evaluation environment. It does not retrieve evidence, does
not own temporal orchestration, does not own provenance graph semantics, and does
not become a general filesystem manager.

Conceptual flow with the harness in place:

```
Evidence enters
    ↓
ChenHai checks environment discipline
    ↓
Evidence task executes inside controlled boundary
    ↓
Outputs use semantic / traceable naming
    ↓
ChenHai evaluates coverage / insufficiency
    ↓
Recovery requested if needed
```

## Planned development

The Skill contract, boundary and planned interface are established by this
repository's initial commits. The Evidence Discipline Harness MVP is implemented;
the evidence sufficiency role is not. The conceptual interface and roadmap are
described in [SKILL.md](./SKILL.md).

This repository makes no benchmark, performance or production-readiness claim.
Precision and recall evaluation is a planned responsibility, not a reported result.
The harness MVP makes no claim about evidence quality, retrieval quality or
sufficiency.

## Repository status

| Field | Value |
| --- | --- |
| Status | Reserved / Planned; harness MVP implemented |
| Implementation | Evidence Discipline Harness MVP in `skills/chenhai_harness/`; sufficiency role not started |
| Default branch | main |
| Languages | English, 简体中文, 繁體中文, 日本語 |

The Evidence Discipline Harness MVP is documented in English here and in
[README.zh-CN.md](./README.zh-CN.md); the 繁體中文 and 日本語 editions describe the
Skill contract only.

## License

MIT License. Copyright (c) 2026 Peng Wang (Hu Deyi). See [LICENSE](./LICENSE).
