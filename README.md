[English](./README.md) | [简体中文](./README.zh-CN.md) | [繁體中文](./README.zh-TW.md) | [日本語](./README.ja.md)

# ChenHai（海琛）

**Evidence Exploration and Evaluation Skill**

> ChenHai asks whether the evidence is sufficient.
>
> It also helps ensure that evidence is produced inside a disciplined, auditable
> environment.

**Development status: Reserved / Planned**

This repository is the canonical future implementation home of the Skill.
The repository is intentionally code-light at this stage.
Its initial commits preserve the Skill contract, architectural boundary, and
planned public interface before implementation begins.

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

Planned conceptual elements — documented as intent, **not yet implemented**:

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

No runtime class, package, schema or sandbox API is designed or claimed to exist at
this stage.

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
repository's initial commits. Implementation has not started. The conceptual
interface and roadmap are described in [SKILL.md](./SKILL.md).

This repository makes no benchmark, performance or production-readiness claim.
Precision and recall evaluation is a planned responsibility, not a reported result.

## Repository status

| Field | Value |
| --- | --- |
| Status | Reserved / Planned |
| Implementation | Not started (documentation-first) |
| Default branch | main |
| Languages | English, 简体中文, 繁體中文, 日本語 |

## License

MIT License. Copyright (c) 2026 Peng Wang (Hu Deyi). See [LICENSE](./LICENSE).
