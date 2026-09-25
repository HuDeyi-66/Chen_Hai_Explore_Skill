# ChenHai（海琛） — Evidence Exploration and Evaluation Skill

## Status

Reserved / Planned

This repository is the canonical future implementation home of the Skill. The
repository is intentionally code-light at this stage. Its initial commits preserve
the Skill contract, architectural boundary, and planned public interface before
implementation begins.

## Purpose

ChenHai evaluates whether the current evidence is enough. It assesses coverage,
detects insufficiency, and produces recovery recommendations for orchestration.

## Responsibilities

- evidence coverage assessment;
- insufficiency detection;
- retrieval-risk and recall-risk signals;
- benchmark precision / recall evaluation when qrels exist;
- runtime coverage proxies where full ground truth is unavailable;
- identification of unresolved evidence gaps;
- production of retry and recovery recommendations for orchestration.

## Non-Responsibilities

- retrieving evidence itself;
- inventing missing evidence;
- silently filling gaps;
- making final normative or legal judgments;
- directly mutating canonical evidence.

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

Naming, encoding, error behaviour and integration surface remain to be designed.

## Development Roadmap

1. Fix the conceptual vocabulary of coverage, insufficiency and gap in this
   repository.
2. Define the boundary against retrieval Skills and against XianHai, and record it
   as the canonical contract.
3. Design the planned interface at the conceptual level and review it before any
   code is written.
4. Implement coverage assessment, then insufficiency detection, then recovery
   recommendation.
5. Add ground-truth-based evaluation where qrels exist, and keep the proxy path
   clearly labelled as a proxy.
6. Publish an implementation only when the contract is honoured end to end.

Each stage is a prerequisite for the next. No stage is claimed as complete.
