[English](./README.md) | [简体中文](./README.zh-CN.md) | [繁體中文](./README.zh-TW.md) | [日本語](./README.ja.md)

# ChenHai（海琛）

**Evidence Exploration and Evaluation Skill**

> ChenHai asks whether the evidence is sufficient.

**Development status: Reserved / Planned**

This repository is the canonical future implementation home of the Skill.
The repository is intentionally code-light at this stage.
Its initial commits preserve the Skill contract, architectural boundary, and
planned public interface before implementation begins.

## What it is

ChenHai is the SeaFlow Skill responsible for evidence exploration and evaluation.
It assesses whether the evidence currently held is enough, identifies unresolved
evidence gaps, and produces retry or recovery recommendations for orchestration.

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

## Evidence boundary

ChenHai does **not**:

- retrieve evidence itself;
- invent missing evidence;
- silently fill gaps;
- make final normative or legal judgments;
- directly mutate canonical evidence.

Architecture rule: ChenHai detects insufficiency and requests recovery. XianHai
decides temporal and recovery orchestration. Retrieval Skills perform retrieval.

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
