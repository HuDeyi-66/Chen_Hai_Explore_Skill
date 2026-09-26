[English](./README.md) | [简体中文](./README.zh-CN.md) | [繁體中文](./README.zh-TW.md) | [日本語](./README.ja.md)

# ChenHai（海琛）

**证据探查与评估 Skill（Evidence Exploration and Evaluation Skill）**

> 海琛负责判断：我们现在知道得够不够。
>
> 它也负责让证据在边界明确、命名清楚、可审计的环境中被处理。

**开发状态：Reserved / Planned（已预留 / 规划中）；证据约束 Harness MVP 已实现**

本仓库是本 Skill 的正式（canonical）未来实现仓库。
其初始提交用于在实现开始之前，先固定 Skill 契约、架构边界与计划中的公开接口。
第一个最小运行时切片——证据约束 Harness MVP——已在 `skills/chenhai_harness/`
下实现，并在下文说明。证据充分性判断职责仍停留在设计阶段，尚未实现。

## 它是什么

ChenHai 是 SeaFlow 中负责**证据探查与评估**的 Skill。
它评估当前已掌握的证据是否足够，识别尚未解决的证据缺口，
并为编排层产出重试 / 补取建议。

海琛不仅判断证据是否充分，也约束证据如何被组织、命名和置于可审计的处理环境中。
这后半句是对前半句的扩展，而不是替换。

## 为什么需要它

检索流水线可以返回结果，而待证事项仍然缺乏支撑。必须有人判断覆盖度、
指出不充分之处、并说明应当重试什么。ChenHai 的存在，是为了让这一判断
显式、可检视，并与检索、最终法律推理相互分离。

## 核心职责

- 证据覆盖度评估；
- 不充分性检测；
- 检索风险 / 召回风险信号；
- 在存在 qrels 时的基准精确率 / 召回率评估；
- 在缺乏完整 ground truth 时的运行时覆盖度代理指标；
- 识别尚未解决的证据缺口；
- 为编排层产出重试 / 补取建议。

扩展职责 —— 证据约束（evidence discipline）：

- 约束证据如何被组织与处理；
- 约束证据产物的命名；
- 构建并校验受控评估工作区；
- 在正式证据任务开始前校验证据处理环境是否规范、可审计。

原有的"充分性判断"职责保持不变。证据约束是对它的扩展，而不是重新定义。

## 证据边界

ChenHai **不**：

- 自行检索证据；
- 编造缺失证据；
- 静默填补缺口；
- 作出最终的规范判断或法律判断；
- 直接改动正式证据；
- 充当通用文件管理器；
- 充当通用工作流引擎；
- 重命名与证据任务无关的任意用户文件；
- 仅凭命名策略决定实质内容；
- 制造虚假的审计证据；
- 事后重建缺失的历史证据。

架构规则：ChenHai 检测不充分并请求补取；XianHai 决定时序与补取编排；
检索类 Skill 负责实际检索。

## 证据约束 Harness（Evidence Discipline Harness）

ChenHai 同时约束两件事：证据是否**充分**，以及证据被处理的环境是否**规范**。
后者在本仓库中称为证据约束 Harness：它是一层证据层面的约束，而不是通用文件系统功能，
也不是企业级编排框架。

具体而言，ChenHai 可以约束：可用证据的范围、证据处理任务发生的位置、期望产出哪些产物、
这些产物如何命名、允许或禁止写入与访问什么，以及由此形成的证据状态日后如何被审计。

### 语义化产物命名

证据产物应当可以按主题与产物角色被识别。ChenHai 可以定义或执行命名规则，优先采用
`<topic>_<artifact-role>.<ext>` 形式；在上下文需要时，采用
`<case-or-task>_<topic>_<artifact-role>.<ext>` 形式。

示意形态（并非已冻结的约定）：

```
collision_liability_evidence_ledger.csv
missing_authority_assessment.md
route_source_inventory.json
port_law_conflict_matrix.csv
```

应当避免 `output1.txt`、`result_final.md`、`data_new.json`、`test2.csv` 这类含混标签：
它们没有传达主题、角色或来源，只会让后续审计更困难。

命名约定预计仍会演进；本阶段不冻结任何刚性的通用文件名文法。架构层面的要求是：
文件名应当传达主题与证据 / 产物角色、避免无意义的泛化标签、提升可追溯性与后续可审计性，
并在可行时保持确定性。

ChenHai 约束产物的命名。它**不会**仅仅为了满足命名规则而编造文件内容。

### 受控证据工作区

在正式的证据任务开始之前，ChenHai 可以帮助构建或校验一个面向特定任务的受控环境——
概念上就是"先把考场搭好"。该环境明确：允许的输入、冻结的证据来源、可写输出位置、
禁止访问的路径、期望的产物、证据清单、任务特有约束、评估规则、完整性校验与失败条件。

概念顺序如下：

```
定义任务
    ↓
定义证据边界
    ↓
构建受控工作区
    ↓
冻结 / 确定允许的输入
    ↓
定义期望产出
    ↓
执行任务
    ↓
评估证据的充分性与完整性
```

其目的是减少：证据污染、对禁入材料的意外访问、来源含混、失控写入、陈旧或无关上下文、
事后重建，以及评估泄漏。

计划中的概念元素 —— 这里作为意图记录。MVP 目前已实现语义化命名策略、受控工作区规范、
期望产物声明、完整性门槛与完整性校验；其余元素仍只是意图：

- ControlledEvidenceWorkspace（受控证据工作区）
- 输入边界
- 输出边界
- 证据清单
- 期望产物集合
- 语义化命名策略
- 读写边界
- 冻结来源声明
- 完整性校验
- 完整性门槛
- 失败 / 拒答状态

除该 Harness MVP 之外，没有设计任何进一步的运行时类、包、schema 或沙箱 API，
也不声称它们已经存在。MVP 本身没有实现任何沙箱 API，也不作此声明。

## 证据约束 Harness MVP（Evidence Discipline Harness MVP）

Harness 的第一个最小运行时切片已经实现，位于本仓库的
[`skills/chenhai_harness/`](./skills/chenhai_harness/)。
它是一个小型的、确定性的文件系统 Harness：**不依赖任何 LLM**，不做检索，
不做语义推断，也不判断产物内容在实质上是否正确。

其目的不是提升检索质量，而是减少实验 / 证据工作区的人工处理。

### 为什么需要这个 Harness

在受控条件下产出证据，不只是"写对字节"的问题。哪些输入被允许、期望产出什么、
实际产出了什么、以及这些内容此后是否被改动过——这些问题原本依赖人的自觉和记忆。
Harness 把它们变成机械可查的。

### 四个操作

```
TaskSpec
    ↓
init       构建受控工作区
    ↓
stage      暂存允许的输入
    ↓
place      放置声明的产物
    ↓
hash / manifest
    ↓
validate   校验期望产出
    ↓
PASS / INCOMPLETE / REFUSE
```

工作区只包含四个目录，不引入更深的层级：

```
<workspace_root>/
    input/
    output/
    manifests/
    checks/
```

| 操作 | 作用 |
| --- | --- |
| `init` | 校验 TaskSpec 并创建工作区，把 spec 持久化到 `manifests/task_spec.json`。若目标位置已有不兼容内容则拒绝，而不是删除或重置。 |
| `stage` | 按声明暂存输入（`mode: "copy"`，支持单文件与目录递归）到 `input/`，并在 `manifests/input_manifest.json` 中逐文件记录 `relative_path`、`size_bytes`、`sha256_lower` 与 `source_path`。原始输入永不被修改。 |
| `place` | 把已经产出的产物按规范文件名复制到 `output/`，并更新 `manifests/output_manifest.json`。默认复制而非移动，绝不检查产物内容；命名冲突时除非字节完全一致否则拒绝；字节一致时该操作是幂等的。 |
| `validate` | 校验 TaskSpec 完整性、工作区布局、必需产物、规范文件名、期望位置、清单与文件哈希一致性、受控输出目录中的意外文件，以及路径边界。写入 `checks/validation_report.json`。 |

```
python -m skills.chenhai_harness init <task_spec.json>
python -m skills.chenhai_harness stage <workspace>
python -m skills.chenhai_harness place <workspace> <source_file> --role final_answer --topic legal_analysis
python -m skills.chenhai_harness validate <workspace>
```

退出码：`0` 表示 PASS 或操作成功，`2` 表示 INCOMPLETE，`3` 表示 REFUSE，
`1` 表示意外的内部错误。`2` 与 `3` 刻意区分：调用方必须能够区分
"还没做完"和"不可信"。

### TaskSpec

仅使用 JSON，schema 版本为 `0.1`，必需顶层字段为 `schema_version`、`task_id`、
`topic`、`workspace_root`、`inputs`、`expected_artifacts`。出现未知字段会被拒绝，
而不是被静默忽略。唯一支持的暂存 `mode` 是 `copy`，且 `inputs[].destination`
必须位于 `input/` 之内。

### 命名约定

```
<normalized_task_id>__<normalized_topic>__<normalized_artifact_role><extension>
```

例如：`m03_r2__legal_analysis__final_answer.md`。

规范化过程是确定性的：NFKC、去除首尾空白、ASCII 转小写、把非 `[a-z0-9]` 且
非 Unicode 字母数字的连续字符折叠为单个下划线、拒绝路径分隔符与独立的 `..`、
拒绝规范化后为空的结果。文件名只来自 TaskSpec 或显式命令参数，
**绝不**通过检查文件内容推断。

### PASS / INCOMPLETE / REFUSE

- **PASS** —— 全部必需产物存在、命名合规、哈希一致。
- **INCOMPLETE** —— 工作区本身有效，但缺少一个或多个必需的期望产物。
- **REFUSE** —— spec 非法、路径不安全、命名违规、清单损坏、哈希不匹配、命名冲突，
  或其他完整性违规（包括受控输出目录中出现意外文件）。`REFUSE` 优先于 `INCOMPLETE`。

### 明确限制：这不是操作系统沙箱

**本 MVP 不是操作系统沙箱。** 它不能阻止外部模型、进程或用户读写任意路径。
它没有实现任何文件系统隔离，也不应被推断出这类能力。

它所做的范围很窄：构建受控工作区、约束**自身**操作会构造与写入的路径、暂存已知输入、
记录清单、约束并校验受管理的输出、校验最终工作区状态。路径检查约束的是
*本 Harness 自身*的行为，而不是其他程序能做什么。

相应地，Harness 不是通用文件管理器，不会重命名无关的用户文件，不检索证据，
不改动正式证据，也不判断产物在实质上是否正确。它只做证据工作区层面的约束。

### 测试与演示

```
python tests/run_all.py     # unittest 发现
pytest tests                # 同一套测试
python tests/smoke_e2e.py   # 合成端到端演示
```

`fixtures/m03_r2_demo/` 只包含一个小型合成演示，不含任何真实标定证据、
私有路径或私有实验产物。

### Harness 的边界

该能力约束的是证据处理方式，而不是制造证据。

ChenHai 可以定义评估的"考场"，但它不自行检索证据，不掌握时序编排，
不掌握溯源图语义，也不会变成通用文件管理器或通用工作流引擎。

## 它如何嵌入 SeaFlow

```
证据获取 / 资产
    ↓
ShanHai / LuoHai / WenHai / 未来视觉证据
    ↓
XianHai
时序组织 / 断层 / 复核
    ↕
JueHai
关系 / 溯源路径
    ↓
ChenHai
覆盖度 / 不充分性 / 评估
    ↓
证据不充分时发出补取请求
```

以上是**架构关系**，不是已实现的耦合。当前阶段，这些 Skill 之间并不存在硬性运行时依赖。

各 Skill 边界保持清晰：

| Skill | 负责范围 |
| --- | --- |
| ShanHai | 检索 / 结构化法律文本证据 |
| LuoHai | 处理结构化 / 表格类证据 |
| WenHai | 登记与保存文档类资产 |
| XianHai | 按时间组织证据，管理时序断层 / 复核 |
| JueHai | 通过图关系与溯源路径连接证据 |
| ChenHai | 评估充分性，**并**约束证据评估环境 |

ChenHai 可以定义评估环境，但它不检索证据，不掌握时序编排，不掌握溯源图语义，
也不会变成通用文件管理器。

引入 Harness 后的概念流程：

```
证据进入
    ↓
ChenHai 校验环境是否规范
    ↓
证据任务在受控边界内执行
    ↓
产物采用语义化 / 可追溯命名
    ↓
ChenHai 评估覆盖度 / 不充分性
    ↓
如有需要，请求补取
```

## 计划中的开发

本仓库的初始提交确立 Skill 契约、边界与计划中的接口。证据约束 Harness MVP 已实现；
证据充分性判断职责尚未实现。概念性接口与路线图见 [SKILL.md](./SKILL.md)。

本仓库不作任何基准测试、性能或生产可用性声明。精确率 / 召回率评估是计划中的职责，
而不是已经报告的结果。Harness MVP 不对证据质量、检索质量或充分性作任何声明。

## 仓库状态

| 项目 | 内容 |
| --- | --- |
| 状态 | Reserved / Planned（已预留 / 规划中）；Harness MVP 已实现 |
| 实现 | `skills/chenhai_harness/` 中的证据约束 Harness MVP；充分性职责尚未开始 |
| 默认分支 | main |
| 语言 | English, 简体中文, 繁體中文, 日本語 |

证据约束 Harness MVP 在 [README.md](./README.md)（英文）与本文件（简体中文）中说明；
繁體中文与日本語版本目前只描述 Skill 契约。

## 许可证

MIT License。Copyright (c) 2026 Peng Wang (Hu Deyi)。详见 [LICENSE](./LICENSE)。
