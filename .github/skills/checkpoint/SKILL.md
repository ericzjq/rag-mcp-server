r

## name: checkpoint

description: 汇总已完成工作、更新 DEV_SPEC.md 中的进度，并为下一轮迭代做准备。dev-workflow 的最终阶段。在任务实现与测试均完成后，或用户说「完成检查点」「checkpoint」「保存进度」「save progress」「任务完成」时使用。  
metadata:  
  category: progress-tracking  
  triggers: "checkpoint, save progress, 完成检查点, 保存进度, 任务完成"  
allowed-tools: Bash(python:*) Bash(git:*) Read Write

# Checkpoint & Progress Persistence（检查点与进度持久化）

本 Skill 负责**任务完成汇总**与**进度同步**，确保已完成工作被正确记录，且 `DEV_SPEC.md` 中的排期保持最新。

> **单一职责**：Summarize → Persist → Prepare Next

---

## When to Use This Skill（何时使用）

- 某任务的实现与测试**均已完成**时
- 需要**手动更新** DEV_SPEC.md 中的进度时
- 需要为已完成工作**生成 commit 信息**时
- 作为 `dev-workflow` 的**最终 Stage（Stage 5）**被调用时

---

## Workflow（流程）

```
Step 1: Summarize → Step 1.5: User Confirm (WHAT) → Step 2: Persist Progress → Step 3: Commit Prep
(Summarize)           (Verify work done)              (Update DEV_SPEC)        (WHETHER)
```

Tests Passed → Step 1 生成摘要 → Step 1.5 用户确认摘要 → 若确认则 Step 2 更新 DEV_SPEC.md → Step 3 生成 commit 信息并询问是否执行 commit → 若用户同意则执行 git commit，否则结束。

---

## Step 1: Work Summary（工作总结）

**Goal**：生成清晰、结构化的完成工作摘要。

### 1.1 Collect Information

从当前会话收集：Task ID、Task Name、创建/修改的文件列表、测试结果（通过/失败、覆盖率）、实现迭代次数（测试-修复轮数）。

### 1.2 Generate Summary Report

按固定格式输出：任务标识、文件变更（Created/Modified）、测试结果、迭代次数、Spec 引用（DEV_SPEC.md Section X.Y）。

---

## Step 1.5: User Confirmation (Verify WHAT Was Done)（用户确认：确认「做了什么」）

**Goal**：在持久化进度前，将摘要呈现给用户确认，确保**总结准确**（不是决定是否保存，而是确认内容对不对）。

### 1.5.1 Confirmation Prompt

输出摘要并询问：总结是否准确？回复 "confirm" / "确认" 则保存进度到 DEV_SPEC.md；"revise" / "修改" 则重新生成摘要。说明：此处仅验证摘要，DEV_SPEC 在确认后更新；是否 git commit 在后续 Step 3 再决定。

### 1.5.2 Handle User Response

用户回复 "confirm" / "yes" / "确认" / "是" → 进入 Step 2；"revise" / "no" / "修改" / "否" → 询问需修正处并重新生成摘要。**未得到明确确认前不得进入 Step 2**。

---

## Step 2: Persist Progress（持久化进度）

**Goal**：更新 `DEV_SPEC.md`，将本任务标记为已完成，同时更新完成时间与备注。

> **自动执行**：在 Step 1.5 用户确认后自动执行，无需再次输入。

### 2.1 Locate Task in DEV_SPEC.md

1. 读取 **GLOBAL** 文件 `DEV_SPEC.md`（非章节文件）
2. 按任务标识定位：如 `### [Task ID]：[Task Name]` 或 `- [ ] [Task ID] [Task Name]`

### 2.2 Update Progress Marker

将未完成标记改为已完成，支持多种风格：`[ ]` → `[x]`、`(进行中)` → `(已完成)` 等，与文档现有风格一致。

若任务已完成，更新任务完成时间：YYYY-MM-DD，更新备注：简短总结

### 2.2.1 Update Overall Progress Table（总体进度表）

**重要**：更新单任务状态后，必须同时更新 **📈 总体进度** 表（位置：DEV_SPEC.md 中 `### 📈 总体进度` 或 `### Overall Progress`）。更新「已完成」数量与「进度」百分比。

### 2.3 Step 2 Output Format

更新完成后输出：Task、Status 变更（如 [ ] -> [x]）、阶段进度更新说明。

---

## Step 3: Commit Preparation（提交准备）

**Goal**：生成结构化 commit 信息，并询问用户是否执行 commit。

### 3.1 Commit Message Template

**Subject 格式**：`<type>(<scope>): [Phase X.Y] <brief description>`

类型：feat / fix / refactor / test / docs / chore；scope 为模块名；描述简短（< 50 字符）。

### 3.2 Generate Commit Message

按模板输出 Subject、Description（含完成的任务、变更摘要、测试命令与结果、Refs）。

### 3.3 User Commit Confirmation (Decide WHETHER to Commit)

**此处确认「是否执行 commit」**。提示用户：回复 "yes" / "commit" / "是" 则执行 git add + git commit；"no" / "skip" / "否" 则结束，用户可稍后手动提交。

### 3.4 Execute Commit (If Confirmed)

若用户确认：`git add <变更文件>`，`git commit -m "<subject>" -m "<description>"`，并输出提交成功信息（Commit hash、Branch、任务完成提示）。

### 3.5 Skip Commit (If Declined)

若用户选择不提交：说明 DEV_SPEC 已更新、git commit 已跳过，并给出可稍后手动执行的 git 命令示例。

---

## Quick Commands


| 用户说                         | 行为                     |
| --------------------------- | ---------------------- |
| "checkpoint" / "完成检查点"      | 完整流程（Step 1～3）含两次确认    |
| "save progress" / "保存进度"    | 仅 Step 1.5～2（确认 + 持久化） |
| "commit message" / "生成提交信息" | 仅 Step 3（生成 commit 信息） |
| "commit for me" / "帮我提交"    | Step 3 + 执行 git commit |


---

## Important Rules（重要规则）

1. **始终更新 GLOBAL DEV_SPEC.md**：进度以该文件为唯一事实来源
2. **保持现有格式**：与文档中已有的标记风格一致（checkbox / emoji / 文字）
3. **原子更新**：每次只更新一个任务
4. **两次用户确认**：Step 1.5 确认摘要后再持久化；Step 3.3 确认后再执行 git commit；**不得跳过**
5. **同时更新两处进度**：标记任务完成时，既要更新该任务状态，完成时间与备注，也要更新 📈 总体进度表
6. **可追溯**：每个检查点都需引用定义该任务的 spec 章节

