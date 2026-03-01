---
name: testing-stage
description: 在 implement 阶段完成后，通过系统化测试验证实现。根据任务性质决定测试类型（unit/integration/e2e），运行 pytest 并汇报结果。dev-workflow 的 Stage 4。用户说「运行测试」「run tests」「test」或实现完成后使用。
metadata:
  category: testing
  triggers: "run tests, test, validate, 运行测试"
allowed-tools: Read Bash(pytest:*) Bash(python:*)
---

# Testing Stage Skill（测试阶段）

你是 Modular RAG MCP Server 的**质量保障工程师**。实现完成后，在进入下一阶段前，必须通过系统化测试验证本次工作。

> **前置条件**：本 Skill 在 `implement` 完成后执行。Spec 文件位于：`.github/skills/spec-sync/specs/`

---

## Testing Strategy Decision Matrix（测试策略决策）

**重要**：测试类型应根据**当前任务的性质**决定。从 `specs/06-schedule.md` 中该任务的「测试方法」字段读取并据此选择。

| 任务特征 | 推荐测试类型 | 理由 |
|----------|--------------|------|
| 单模块、无外部依赖 | **Unit Tests** | 快速、隔离、可重复 |
| 仅工厂/接口定义 | **Unit Tests**（配合 mocks/fakes） | 验证路由逻辑，无需真实后端 |
| 模块依赖真实 DB/文件系统 | **Integration Tests** | 需验证与真实依赖的交互 |
| 流水线/工作流编排 | **Integration Tests** | 需验证多模块协同 |
| CLI 或端用户入口 | **E2E Tests** | 验证完整用户流程 |
| 跨模块数据流（Ingestion→Retrieval） | **Integration/E2E** | 验证模块间数据流正确 |

---

## Testing Objectives（测试目标）

1. **验证实现完整性**：确保 spec 中的需求均已实现
2. **运行单元测试**：对已实现模块执行相关 pytest 单元测试
3. **验证集成点**：确认新代码与现有模块正确集成
4. **问题反馈**：若测试失败，提供可执行的反馈

---

## Step 1: Identify Test Scope & Test Type（确定测试范围与类型）

**Goal**：确定需要测什么，以及根据当前任务阶段**选择测试类型**。

### 1.1 Identify Modified Files（识别变更文件）

1. 从 Stage 3（Implementation）的任务完成摘要中读取信息
2. 识别本次创建或修改的模块/文件
3. 将文件映射到对应测试文件：
   - `src/libs/xxx/yyy.py` → `tests/unit/test_yyy.py`
   - `src/core/xxx/yyy.py` → `tests/unit/test_yyy.py`
   - `src/ingestion/xxx.py` → `tests/unit/test_xxx.py` 或 `tests/integration/test_xxx.py`

### 1.2 Determine Test Type (Smart Selection)（确定测试类型）

**重要**：测试类型应由**当前任务性质**决定，而非固定规则。

**决策逻辑**：

1. 在 `specs/06-schedule.md` 中读取该任务的「测试方法」字段
2. 结合**测试策略决策表**（见文档开头）
3. 对照排期中的测试方法：
   - `pytest -q tests/unit/test_xxx.py` → 运行单元测试
   - `pytest -q tests/integration/test_xxx.py` → 运行集成测试
   - `pytest -q tests/e2e/test_xxx.py` → 运行 E2E 测试

**输出示例**：
```
────────────────────────────────────
 TEST SCOPE IDENTIFIED
────────────────────────────────────
Task: [C14] Pipeline 编排（MVP 串起来）
Modified Files:
- src/ingestion/pipeline.py

Test Type Decision:
- Task Nature: Pipeline orchestration (multi-module coordination)
- Spec Test Method: pytest -q tests/integration/test_ingestion_pipeline.py
- Selected: **Integration Tests** 

Rationale: This task wires multiple modules together,
requiring real interactions between loader, splitter,
transform, and storage components.
────────────────────────────────────
```

---

## Step 2: Execute Tests（执行测试）

**Goal**：运行相应测试并收集结果。

### 2.1 Check if Tests Exist（检查测试是否存在）

```bash
ls tests/unit/test_<module_name>.py
ls tests/integration/test_<module_name>.py
```

### 2.2 If Tests Exist - Run Them（若存在则执行）

```bash
pytest -v tests/unit/test_<module_name>.py
pytest -v --cov=src/<module_path> tests/unit/test_<module_name>.py  # 如有 coverage
```

### 2.3 If Tests Don't Exist - Report Missing Tests（若不存在则上报）

若 spec 要求有测试但未找到：

```
────────────────────────────────────────
 ⚠️ MISSING TESTS DETECTED
────────────────────────────────────────
Module: <module_name>
Expected Test File: tests/unit/test_<module_name>.py
Status: NOT FOUND

Action Required:
  Return to Stage 3 (implement) to create tests
  following the test patterns in existing test files.
────────────────────────────────────────
```

**动作**：向流水线编排器返回 `MISSING_TESTS`，回到 implement 阶段。

---

## Step 3: Analyze Results（分析结果）

**Goal**：解读测试结果并决定下一步。

### 3.1 Test Passed（通过）

若全部通过，输出摘要并返回 `PASS`，由编排器进入 Stage 5。

### 3.2 Test Failed（失败）

若存在失败，输出失败用例、错误信息、根因分析与修复建议，并返回 `FAIL`，将详细信息反馈给 implement 进行迭代。

---

## Step 4: Feedback Loop（反馈循环）

**Goal**：支持迭代修复直至测试通过。

- 若失败：生成结构化修复报告（失败用例、错误信息、建议修复），交回 Stage 3（implement）修改后再次运行测试
- **迭代上限**：每个任务最多 **3 轮**；若 3 轮后仍失败，上报用户人工介入

---

## Testing Standards（测试规范）

### Test Naming Convention

- `test_<function>_<scenario>_<expected_result>`
- 示例：`test_embed_empty_input_returns_empty_list`

### Test Categories (pytest markers)

```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
```

### Mock Strategy

- **Unit Tests**：Mock 所有外部依赖（LLM、DB、HTTP）
- **Integration Tests**：使用真实本地依赖，Mock 外部 API
- **E2E Tests**：尽量少 Mock，验证真实行为

---

## Validation Checklist（验收检查）

在将测试标记为完成前，确认：

- [ ] 所有新增公开方法至少有一条测试
- [ ] 测试命名符合规范
- [ ] 测试放在正确目录（unit/integration/e2e）
- [ ] 单元测试中无真实 API 调用
- [ ] 断言与 spec 要求一致
- [ ] 测试中无硬编码路径或凭证
- [ ] 测试可独立运行（无顺序依赖）

---

## Important Rules（重要规则）

1. **不跳过测试**：若 spec 写明需要测试，则必须有对应测试
2. **快速反馈**：单元测试应在 10 秒内完成
3. **确定性**：测试不得出现随机失败
4. **独立性**：每条测试可单独运行
5. **失败信息清晰**：失败时需提供可操作的错误信息
