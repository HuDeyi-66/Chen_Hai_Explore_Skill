# ChenHai（海琛） — Evidence Exploration and Evaluation Skill

> ChenHai asks whether the evidence is sufficient.
>
> It also helps ensure that evidence is produced inside a disciplined, auditable
> environment.

## Status

Reserved / Planned

This repository is the canonical future implementation home of the Skill. The
repository is intentionally code-light at this stage. Its initial commits preserve
the Skill contract, architectural boundary, and planned public interface before
implementation begins.

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

Input formats, schemas or transport mechanisms are not yet designed.

## Outputs

Conceptually, ChenHai produces:

- coverage assessments over the current evidence;
- insufficiency findings that name what is missing or thin;
- retrieval-risk and recall-risk signals;
- unresolved evidence gaps;
- retry and recovery recommendations addressed to orchestration callers;
- evaluation results when ground-truth material is available.

Output formats, schemas or storage mechanisms are not yet designed.

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

The planned interface is described only in concepts. No Python API, function
signature, data schema, package name or CLI command has been designed yet, and
none is invented here.

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

These are named concepts only. No concrete Python class, function signature, data
schema, package name or CLI command is designed here, and none is invented. The
interfaces are not claimed to exist. The naming convention and the workspace
specification are both expected to evolve.

Naming, encoding, error behaviour and integration surface remain to be designed.

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
