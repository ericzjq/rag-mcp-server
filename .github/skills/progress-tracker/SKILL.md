---
name: progress-tracker
description: 从项目排期中识别下一开发任务，并校验「声称的进度」与「实际代码状态」是否一致。充当开发中的 GPS，告诉你当前位置与下一步。dev-workflow 的 Stage 2。用户说「检查进度」「status」「下一个任务」「what's next」「定位任务」时使用。
metadata:
  category: progress-tracking
  triggers: "status, what's next, find task, 检查进度, 下一个任务, 定位任务"
allowed-tools: Read Bash(python:*)
---

# Progress Tracker & Task Discovery（进度跟踪与任务发现）

本 Skill 从项目排期中识别**下一开发任务**，并**校验**声称的进度与实际代码状态是否一致，充当开发「GPS」：告诉你当前在哪、下一步做什么。

> **单一职责**：Locate → Validate → Confirm

---

## When to Use This Skill（何时使用）

- 需要**确定下一个要做的任务**时
- 想**查看当前项目进度**时
- 怀疑**进度记录与实际代码不一致**时
- 作为 `dev-workflow` 的 **Stage 2** 被调用
- 中断后要**从正确位置恢复开发**时

---

## Workflow（流程）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Step 1              Step 2                Step 3              Step 4        │
│  Data Collection  →  Progress Validation → Task Identification → Confirm    │
│  (Data Prep)         (Validation)          (Task Confirm)       (User OK)    │
│                          │                                                   │
│                          ▼                                                   │
│                     Mismatch? → Escalate to User → Fix DEV_SPEC          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Data Collection（数据收集）

**Goal**：收集「声称的进度」与「实际代码状态」相关信息。

### 1.1 Read Schedule from Spec

1. 读取 `.github/skills/spec-sync/specs/06-schedule.md`（项目排期）
2. 解析任务表，识别：所有任务及其状态标记、当前阶段、已完成/进行中/未开始

### 1.2 Status Marker Recognition

| Marker | 含义 | Status |
|--------|------|--------|
| `[ ]` | 未开始 | `NOT_STARTED` |
| `[~]` | 进行中 | `IN_PROGRESS` |
| `[x]` | 已完成 | `COMPLETED` |
| `(进行中)` | 进行中 | `IN_PROGRESS` |
| `(已完成)` | 已完成 | `COMPLETED` |

### 1.3 Build Task List

按阶段输出任务列表（含当前任务标记）。

---

## Step 2: Progress Validation（进度校验）

**Goal**：验证声称的进度与实际代码库状态是否一致。

### 2.1 Identify Verification Targets

对每个标记为 `COMPLETED` 或 `IN_PROGRESS` 的任务，识别预期产物（如 A3 对应 `src/core/settings.py`、`settings.yaml` 等）。

### 2.2 Verify Artifacts Exist

检查文件/目录是否存在，代码文件能否正常 import，相关测试是否存在并可导入。

### 2.3 Detect and Handle Mismatches（发现并处理不一致）

若检测到不一致（如任务标为完成但文件缺失、import 报错、缺测试等），向用户上报并给出选项：

1. **修正 DEV_SPEC.md**：更新标记以反映实际状态 → 重新运行 spec-sync → 从 Step 1 重新开始
2. **确认已完成**：用户说明代码位置/分支，在记录后继续
3. **按实际进度继续**：以代码实际状态为准，覆盖排期中的「当前」任务，从修正后的任务继续

---

## Step 3: Task Identification（任务识别）

**Goal**：明确唯一的下一个要执行的任务。

### 3.1 Determine Next Task

**优先级**：若有 `IN_PROGRESS` → 该任务即为当前任务；否则取第一个 `NOT_STARTED`；若全部完成则报告 "All tasks complete"。

### 3.2 Gather Task Context

收集：Task ID、Task Name、Phase、Spec 章节、依赖的前置任务。

### 3.3 Output Task Information

输出当前/下一任务的完整信息（Phase、Task ID、Name、Status、Spec 引用、依赖、校验结果）。

---

## Step 4: User Confirmation（用户确认）

**Goal**：在继续前获得用户明确确认。

向用户展示即将执行的任务，选项：Confirm / 确认（继续）、Override / 指定其他（指定其他任务）、Cancel / 取消（中止）。根据用户选择返回任务信息给 Stage 3 或中止。

---

## Quick Commands

| 用户说 | 行为 |
|--------|------|
| "status" / "检查进度" | 仅执行 Step 1～3（报告状态，无需确认） |
| "what's next" / "下一个任务" | Step 1～3（识别下一任务） |
| "find task" / "定位任务" | 完整流程（Step 1～4） |
| "validate" / "验证进度" | 仅 Step 1～2（校验报告） |
| "fix progress" / "修正进度" | Step 2 的不一致处理流程 |

---

## Output Contract（输出约定）

被 `dev-workflow` 调用时，返回状态类型：`OK` | `MISMATCH` | `ALL_COMPLETE` | `CANCELLED`。若为 OK，需包含 Task ID、Task Name、Phase、Spec 引用、依赖是否满足等；若为 MISMATCH，需包含声称任务 vs 实际任务、缺失项及用户选项。

---

## Important Rules（重要规则）

1. **先校验再继续**：不假定排期一定准确，始终核对实际代码状态
2. **必须用户确认**：不自动进入实现，等待用户明确确认
3. **单任务聚焦**：每次只识别一个任务
4. **非破坏性**：本 Skill 仅读取与报告，不修改代码或 spec（除非用户在选择不一致处理时明确选 Option 1）
5. **优雅降级**：若 spec 文件缺失，可回退为直接读取 `DEV_SPEC.md`
