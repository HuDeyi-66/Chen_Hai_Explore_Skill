# ChenHai（海琛） — Evidence Exploration and Evaluation Skill

> ChenHai asks whether the evidence is sufficient.
>
> It also helps ensure that evidence is produced inside a disciplined, auditable
> environment.

## Status

Reserved / Planned; the Evidence Discipline Harness MVP is implemented.

This repository is the canonical future implementation home of the Skill. Its
initial commits preserve the Skill contract, architectural boundary, and planned
public interface. The first runtime slice — the evidence discipline harness — is
implemented under `skills/chenhai_harness/` and documented below. The evidence
sufficiency role remains designed but not implemented.

## Purpose

ChenHai evaluates evidence sufficiency and helps construct disciplined, auditable
evidence environments. It assesses coverage, detects insufficiency, and produces
recovery recommendations for orchestration.

The sufficiency role is primary and unchanged. The environment-discipline role is
an extension of it: ChenHai asks not only whether the evidence is enough, but also
whether the evidence environment is disciplined enough to produce an auditable
result.

## Responsibilities

- evidence coverage assessment;
- insufficiency detection;
- retrieval-risk and recall-risk signals;
- benchmark precision / recall evaluation when qrels exist;
- runtime coverage proxies where full ground truth is unavailable;
- identification of unresolved evidence gaps;
- production of retry and recovery recommendations for orchestration.

Evidence discipline extension:

- **semantic output naming** — defining or enforcing naming rules so that evidence
  outputs are identifiable by topic and by artifact role;
- **controlled evidence workspace** — helping construct or validate a
  purpose-specific environment for a formal evidence task before that task runs;
- evidence-environment validation ahead of a formal evidence task.

Of the evidence-discipline extension, all three items now have a concrete MVP
implementation: `init` and `validate` cover workspace construction and
environment validation, and the naming policy is enforced by `place` and checked
by `validate`. See the "Evidence Discipline Harness MVP" section below. None of
the sufficiency responsibilities above is implemented.

## Non-Responsibilities

- retrieving evidence itself;
- inventing missing evidence;
- silently filling evidence gaps;
- making final normative or legal judgments;
- directly mutating canonical evidence;
- acting as a generic file manager;
- acting as a general workflow engine;
- renaming arbitrary user files unrelated to evidence tasks;
- deciding substantive content merely from filename policy;
- creating fake audit evidence;
- reconstructing missing historical evidence after the fact.

The evidence-discipline extension constrains evidence handling. It does not
manufacture evidence.

Architecture rule: ChenHai detects insufficiency and requests recovery. XianHai
decides temporal and recovery orchestration. Retrieval Skills perform retrieval.

## Inputs

Conceptually, ChenHai consumes:

- evidence references already registered elsewhere in the evidence runtime;
- the matter, question or claim set against which sufficiency is judged;
- statements of what a retrieval attempt was asked to find and what it returned;
- optional ground-truth material such as qrels, where it exists;
- requests for coverage assessment or gap inspection.

Input formats, schemas or transport mechanisms for the sufficiency role are not
yet designed. The harness MVP does define one concrete input contract — the
TaskSpec, JSON schema version `0.1` — and that is documented in the "Evidence
Discipline Harness MVP" section below.

## Outputs

Conceptually, ChenHai produces:

- coverage assessments over the current evidence;
- insufficiency findings that name what is missing or thin;
- retrieval-risk and recall-risk signals;
- unresolved evidence gaps;
- retry and recovery recommendations addressed to orchestration callers;
- evaluation results when ground-truth material is available.

Output formats, schemas or storage mechanisms for the sufficiency role are not yet
designed. The harness MVP produces three concrete machine-readable documents,
also documented in the section below: `manifests/input_manifest.json`,
`manifests/output_manifest.json` and `checks/validation_report.json`.

## Evidence Boundary

ChenHai does not retrieve, does not invent and does not mutate evidence. It
evaluates what exists and reports what does not. Any recommendation it produces is
a request, not an action: the decision to retry belongs to orchestration, the
retrieval itself belongs to retrieval Skills, and normative conclusions belong to
neither.

The evidence-discipline extension does not widen this boundary. ChenHai may define
the evaluation "room" — its boundaries, permitted inputs and expected outputs — but
it does not retrieve the evidence, does not own temporal orchestration, does not own
provenance graph semantics, and does not become a general filesystem manager. The
harness constrains evidence handling; it does not manufacture evidence.

## Relationship to SeaFlow

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
dependency between these Skills has been implemented at this stage.

Skill boundaries:

- **ShanHai** retrieves and structures legal textual evidence;
- **LuoHai** handles structured and tabular evidence;
- **WenHai** registers and preserves documentary assets;
- **XianHai** organizes evidence temporally and manages temporal gaps and rechecks;
- **JueHai** connects evidence through graph relations and provenance paths;
- **ChenHai** evaluates sufficiency and constrains the evidence-evaluation
  environment.

ChenHai may define the evaluation "room". It does not retrieve the evidence itself,
does not own temporal orchestration, does not own provenance graph semantics, and
does not become a general filesystem manager.

Conceptual flow with the evidence-discipline extension in place:

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

## Planned Interface

The planned interface for the sufficiency role is described only in concepts. No
Python API, function signature or data schema for coverage, insufficiency, gaps or
recovery is designed yet, and none is invented here. The harness MVP does have a
concrete interface; it is documented in the "Evidence Discipline Harness MVP"
section below, and it covers only evidence-workspace discipline.

Conceptually the Skill is expected to expose:

- a notion of an evidence set under evaluation;
- a notion of coverage over that set;
- a notion of insufficiency, distinct from mere absence of results;
- a notion of retrieval risk and recall risk;
- a notion of an unresolved evidence gap;
- a notion of a retry or recovery recommendation;
- a notion of evaluation against available ground truth.

Conceptually the Skill is also expected to expose, for the evidence-discipline
extension:

- a **semantic naming policy** — rules that make an output identifiable by topic and
  artifact role, rather than a frozen universal filename grammar;
- a **controlled workspace specification** — the purpose-specific environment in
  which a formal evidence task is performed;
- an **evidence boundary declaration** — which inputs are permitted, and which paths
  are prohibited;
- an **expected artifact declaration** — what the task is expected to produce;
- a **completeness gate** — whether the expected artifacts and evidence are present;
- an **integrity check** — whether the evidence state is intact and traceable.

These are named concepts only, with one exception: the semantic naming policy, the
controlled workspace specification, the expected artifact declaration, the
completeness gate and the integrity check now have a concrete MVP implementation,
described in the "Evidence Discipline Harness MVP" section immediately below.
Everything else here remains conceptual and no interface for it is invented. The
naming convention and the workspace specification are both expected to evolve.

For the sufficiency role, naming, encoding, error behaviour and integration
surface remain to be designed.

## Evidence Discipline Harness MVP

The harness MVP is implemented in this repository under
[`skills/chenhai_harness/`](./skills/chenhai_harness/). It is a small
deterministic filesystem harness whose purpose is to reduce manual experiment and
evidence workspace handling. It contains no LLM dependency, performs no retrieval,
performs no semantic inference, and makes no judgement about whether an artifact's
content is substantively correct.

### Why it exists

Producing evidence under controlled conditions is not only a matter of producing
the right bytes. Which inputs were permitted, what was expected, what was actually
produced, and whether any of it has changed since are questions that otherwise
depend on human discipline and on someone's memory of what they did. The harness
makes those questions mechanical.

### The four operations

| Operation | Purpose |
| --- | --- |
| `init` | Validate a TaskSpec and create the controlled workspace: `input/`, `output/`, `manifests/`, `checks/`. Refuses to overwrite incompatible content. |
| `stage` | Copy declared inputs (`mode: "copy"`, files or directories recursively) into `input/` and record every file's size and SHA-256 in `manifests/input_manifest.json`. |
| `place` | Copy an already-produced artifact into `output/` under its canonical filename and update `manifests/output_manifest.json`. Refuses a collision unless the bytes are identical. |
| `validate` | Check TaskSpec integrity, layout, required artifacts, naming compliance, expected location, manifest hashes, unexpected output files, and path boundaries. Writes `checks/validation_report.json`. |

CLI:

```
python -m skills.chenhai_harness init <task_spec.json>
python -m skills.chenhai_harness stage <workspace>
python -m skills.chenhai_harness place <workspace> <source_file> --role final_answer --topic legal_analysis
python -m skills.chenhai_harness validate <workspace>
```

Exit codes: `0` PASS or successful operation, `2` INCOMPLETE, `3` REFUSE,
`1` unexpected internal error.

### TaskSpec

JSON only, schema version `0.1`, with the required top-level fields
`schema_version`, `task_id`, `topic`, `workspace_root`, `inputs` and
`expected_artifacts`. Absolute host paths are required for `workspace_root`;
`inputs[].destination` must stay inside `input/`; the only supported `mode` is
`copy`. Unknown fields are refused rather than ignored.

### Naming convention

```
<normalized_task_id>__<normalized_topic>__<normalized_artifact_role><extension>
```

Example: `m03_r2__legal_analysis__final_answer.md`.

Normalisation is deterministic: NFKC, surrounding whitespace trimmed, ASCII
lowercased, runs of characters that are not ASCII `[a-z0-9]` or Unicode
alphanumerics collapsed to a single underscore, path separators and standalone
`..` rejected, and empty results rejected. The name comes from the TaskSpec or
from an explicit command argument only — never from file content.

### PASS / INCOMPLETE / REFUSE

- **PASS** — every required artifact is present under its canonical name and every
  recorded digest still matches.
- **INCOMPLETE** — the workspace is sound but required artifacts are absent. Not
  finished is not the same as not trustworthy.
- **REFUSE** — invalid spec, unsafe path, naming violation, manifest corruption,
  hash mismatch, collision, or an unexpected file in `output/`. `REFUSE` outranks
  `INCOMPLETE`.

### Explicit limitation: this is not an OS sandbox

The MVP is **not** an operating-system sandbox. It does not prevent an external
model, process, or user from reading or writing arbitrary paths, and it does not
contain, jail, or otherwise isolate anything. It only constructs a controlled
workspace, constrains the paths its own operations will construct and write,
stages known inputs, records manifests, and validates the resulting workspace. No
filesystem isolation is implemented and none is claimed.

The four core directories are the whole hierarchy. The harness is not a general
file manager, does not rename unrelated files, does not retrieve evidence, does
not mutate canonical evidence, and makes no claim about evidence sufficiency.

### Tests and demo

```
python tests/run_all.py     # unittest discovery
pytest tests                # the same suite
python tests/smoke_e2e.py   # synthetic end-to-end demonstration
```

`fixtures/m03_r2_demo/` is entirely synthetic: no real calibration evidence and
no private path is present.

## Development Roadmap

1. Fix the conceptual vocabulary of coverage, insufficiency and gap in this
   repository.
2. Define the boundary against retrieval Skills and against XianHai, and record it
   as the canonical contract.
3. Design the planned interface at the conceptual level and review it before any
   code is written, including the semantic naming policy and the controlled
   workspace specification.
4. Implement coverage assessment, then insufficiency detection, then recovery
   recommendation.
5. Add ground-truth-based evaluation where qrels exist, and keep the proxy path
   clearly labelled as a proxy.
6. Publish an implementation only when the contract is honoured end to end.

Each stage is a prerequisite for the next. No stage is claimed as complete.

Status of the stages: 1 and 2 are recorded in this repository as the canonical
contract. Stage 3 is recorded conceptually; of the concepts it names, the
semantic naming policy, the controlled workspace specification, the expected
artifact declaration, the completeness gate and the integrity check now have a
concrete MVP implementation in `skills/chenhai_harness/`, while the coverage,
insufficiency, gap and recovery notions remain conceptual only. Stages 4 to 6 are
not started. The evidence sufficiency role is unchanged and unimplemented; the
harness MVP is an extension of the Skill, not a substitute for its primary role.
