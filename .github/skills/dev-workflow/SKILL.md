---

## name: dev-workflow
description: 开发流水线的主编排 Skill。用户说「下一阶段」「继续开发」「next task」「proceed」或要求继续开发时使用。按流水线协调 spec-sync、progress-tracker、implement、testing-stage、checkpoint，每轮完成一个子任务。
metadata:
  category: orchestration
  triggers: "next task, proceed, continue development, 下一阶段, 继续开发"
allowed-tools: Read

# Development Workflow Orchestrator（开发流水线编排）

你是 Modular RAG MCP Server 的**项目管家 AI**。当用户要求继续开发时，你必须**按顺序**执行以下流水线。

> **Meta-Skill 说明**：本 Skill 只负责编排其他 Skill，各 Stage 的**具体执行细节**见各自 Skill 的 SKILL.md，本文件仅定义**流水线顺序**与**阶段间协调**。

---

## Stage 0: Activate Virtual Environment（前置条件）

**在执行任意 Stage 之前**，先激活python项目的虚拟环境

> 此步骤为强制要求，在调用任何子 Skill 前必须完成。

---

## Pipeline Stages（流水线阶段）


| Stage | Skill              | 说明     | Skill 文件                                   |
| ----- | ------------------ | ------ | ------------------------------------------ |
| 1     | `spec-sync`        | 同步规格文档 | `.github/skills/spec-sync/SKILL.md`        |
| 2     | `progress-tracker` | 确定下一任务 | `.github/skills/progress-tracker/SKILL.md` |
| 3     | `implement`        | 执行实现   | `.github/skills/implement/SKILL.md`        |
| 4     | `testing-stage`    | 运行测试   | `.github/skills/testing-stage/SKILL.md`    |
| 5     | `checkpoint`       | 保存进度   | `.github/skills/checkpoint/SKILL.md`       |


> **各 Stage 的执行步骤、完成标准与输出格式**请参阅对应 SKILL.md。

---

## Pipeline Flow（流水线示意）

```
                    ┌──────────────────┐
                    │   User: "下一阶段"  │
                    └────────┬─────────┘
                             ▼
                  ┌──────────────────────┐
                  │  Stage 1: spec-sync  │
                  └────────┬─────────────┘
                           ▼
                  ┌──────────────────────┐
                  │ Stage 2: progress-   │
                  │         tracker      │
                  └────────┬─────────────┘
                           │
                     Exception? ──→ User Confirm → Update DEV_SPEC → Back to Stage1
                           │
                           ▼
                  ┌──────────────────────┐
          ┌──────▶│ Stage 3: implement   │
          │       └────────┬─────────────┘
          │                ▼
          │       ┌──────────────────────┐
          │       │ Stage 4: testing-    │
          │       │         stage        │
          │       └────────┬─────────────┘
          │                ▼
          │           ┌─────────┐
          │           │ Tests   │
          │           │ Pass?   │
          │           └────┬────┘
          │     No         │         Yes
          │     ┌──────────┴──────────┐
          │     ▼                     ▼
          │ Iteration < 3?     ┌──────────────────────┐
          │     │              │  Stage 5: checkpoint │
          │ Yes │              └──────────────────────┘
          └─────┘
                │ No (iteration >= 3)
                ▼
          ┌──────────────────┐
          │ Escalate to User │
          └──────────────────┘
```

---

## Inter-Stage Data Flow（阶段间数据传递）

编排器负责在阶段间传递上下文：


| From        | To      | 传递内容                         |
| ----------- | ------- | ---------------------------- |
| Stage 2     | Stage 3 | Task ID、Task Name、相关 Spec 章节 |
| Stage 3     | Stage 4 | 变更文件、模块路径                    |
| Stage 4     | Stage 3 | 测试失败信息（失败时用于迭代）              |
| Stage 4     | Stage 5 | 测试结果、迭代次数                    |
| Stage 2,3,4 | Stage 5 | Task ID、变更文件、测试摘要            |


---

## Quick Commands（快捷命令）

> **注意**：每次「next task」只完成**一个子任务**（如 A1→A2→A3），不会一次完成整个阶段（如 Phase A→Phase B）。


| 用户说                     | 流水线行为                         |
| ----------------------- | ----------------------------- |
| "next task" / "下一阶段"    | 完整流水线（Stage 1～5），完成**下一个子任务** |
| "continue" / "继续实现"     | 仅执行 Stage 3（假定任务已确定）          |
| "status" / "检查进度"       | 仅执行 Stage 2                   |
| "sync spec" / "同步规范"    | 仅执行 Stage 1                   |
| "run tests" / "运行测试"    | 仅执行 Stage 4                   |
| "fix progress" / "修正进度" | Stage 2 校验 + 更新 DEV_SPEC      |


---

## Orchestrator Rules（编排规则）

1. **委托**：各 Stage 的具体逻辑由对应 Skill 定义，编排器只负责调用与流转
2. **Spec 为唯一事实来源**：进度以 `DEV_SPEC.md` 为准
3. **Stage 顺序**：除非用户明确指定，否则按 1→2→3→4→5 执行
4. **单子任务**：每轮流水线只完成一个子任务
5. **用户确认**：Stage 2 结束后需等待用户确认再继续
6. **先测再检查点**：Stage 4 通过后才进入 Stage 5
7. **迭代上限**：最多 3 轮测试修复
8. **两步检查点**：Stage 5 需要两次用户确认：先确认工作总结（再自动更新 DEV_SPEC.md），再决定是否执行 git commit

