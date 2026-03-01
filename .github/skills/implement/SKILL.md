---
name: implement
description: 按 spec 驱动流程实现功能。先读 spec、提炼设计原则、规划文件策略，再编写带类型注解与 docstring 的生产级代码。用户要求实现功能、写代码或构建模块时使用。依赖 spec-sync 以访问规格文档。
metadata:
  category: implementation
  triggers: "implement, write code, build module, 实现, 写代码"
allowed-tools: Read Write Bash(python:*) Bash(pytest:*)
---

# Standard Operating Procedure: Implement from Spec（按 Spec 实现的标准流程）

你是 Modular RAG MCP Server 的**主架构师**。当用户要求实现某功能时，必须严格按以下流程执行。

> **前置条件**：本 Skill 依赖 `spec-sync` 提供的规格文档。Spec 文件位于：`.github/skills/spec-sync/specs/`

---

## Step 1: Spec Retrieval & Analysis（规格获取与分析）

**Goal**：在权威 spec 文档基础上开展工作，采用渐进式披露方式阅读。

### 1.1 Navigate Intelligently（按需导航）

不要通读整份 `DEV_SPEC.md`，而是：
- **先**读取 `.github/skills/spec-sync/SPEC_INDEX.md` 定位相关章节
- **再**只读取 `.github/skills/spec-sync/specs/` 下对应的章节文件

### 1.2 Extract Task-Specific Requirements（提取任务相关需求）

从目标章节中识别：
* **Inputs/Outputs**：期望的数据类型？
* **Dependencies**：是否依赖特定库？
* **Modified Files**：本任务需创建或修改哪些文件？
* **Verification Criteria**：验收标准是什么？

### 1.3 Extract Design Principles（提取设计原则）

**重要**：从 spec 中识别并提取与当前任务相关的设计原则。

**操作**：
1. 在 `specs/06-schedule.md` 中定位该任务
2. 交叉参考 `specs/03-tech-stack.md` 或 `specs/05-architecture.md`
3. 提取适用原则（Pluggable、Config-Driven、Fallback、Idempotent、Observable）
4. 在写代码前将原则记录下来

**输出模板**：
```
────────────────────────────────────
DESIGN PRINCIPLES FOR THIS TASK
────────────────────────────────────
Task: [Task ID] [Task Name]

Applicable Principles:
1. [Principle] - [Implementation requirement]
2. [Principle] - [Implementation requirement]

Source: specs/XX-xxx.md Section X.X
────────────────────────────────────
```

### 1.4 Acknowledge（向用户说明）

明确告知用户参考了哪一章节、适用了哪些原则。示例：
> *「我已查阅 `specs/03-tech-stack.md` Section 3.3.2。针对任务 B1（LLM Factory），适用的设计原则为：Pluggable Architecture（抽象基类 + 工厂）、Configuration-Driven（provider 来自 settings.yaml）、Graceful Error Handling。」*

**章节速查**（文件在 `.github/skills/spec-sync/specs/`）：
- **架构相关** → `05-architecture.md`
- **技术实现细节** → `03-tech-stack.md`
- **测试要求** → `04-testing.md`
- **排期/进度** → `06-schedule.md`

---

## Step 2: Technical Planning（技术规划）

**Goal**：在写第一行代码前，确保模块化并符合设计原则。

1. **File Strategy**：列出要创建或修改的文件（与排期中该任务的「Modified Files」交叉核对）
2. **Interface Design**：根据 Step 1.3 提取的原则设计接口：
   - 若适用 **Pluggable** → 先定义抽象基类
   - 若适用 **Factory Pattern** → 规划工厂函数签名
   - 若适用 **Config-Driven** → 明确需要的 settings.yaml 字段
3. **Dependency Check**：若需新依赖，规划更新 `pyproject.toml` 或 `requirements.txt`
4. **Design Principle Checklist**：在继续前确认规划覆盖 Step 1.3 中的每一条原则

---

## Step 3: Implementation（实现）

**Goal**：编写符合规范、可用于生产环境的代码。

1. **Coding Standards**：
   * **Type Hinting**：所有函数签名必须带类型注解
   * **Docstrings**：所有类与方法使用 Google 风格 docstring
   * **No Hardcoding**：使用配置或依赖注入
   * **Clean Code Principles**：
     - **Single Responsibility**：每个函数/类只做一件事
     - **Short & Focused**：函数尽量短（理想 < 20 行），类内聚
     - **Meaningful Names**：命名体现意图（如 `getUserById` 而非 `getData`）
     - **No Side Effects**：函数行为与名称一致，无隐藏副作用
     - **DRY**：抽象公共模式，避免重复
     - **Fail Fast**：尽早校验输入，抛出清晰异常
2. **Error Handling**：对 LLM、数据库等外部集成编写健壮的 try/except

---

## Step 4: Self-Verification (Before Testing)（交测前自检）

**Goal**：在交给 testing-stage 前自检并确保符合设计原则。

> **范围**：此处为**静态**自检（代码审查，不执行）。实际测试执行在 Stage 4（testing-stage）进行。

1. **Spec Compliance Check**：生成的代码是否违反 Step 1 中的任何约束？
2. **Design Principle Compliance Check**：逐条核对 Step 1.3 的原则是否落实：
   - [ ] **Pluggable** → 是否有抽象基类？实现是否可替换？
   - [ ] **Factory Pattern** → 工厂是否按配置正确路由？
   - [ ] **Config-Driven** → 魔法值是否都移到 settings.yaml？
   - [ ] **Fallback** → 失败时是否有优雅降级？
   - [ ] **Idempotent** → 操作是否可安全重复？
3. **Test File Verification**：确认测试文件已创建且结构正确（import、用例）
4. **Refinement**：若有占位符如 `pass`，替换为实际逻辑或带 TODO 说明的 `NotImplementedError`
5. **Final Output**：总结应用了哪些设计原则，例如：
   ```
   ────────────────────────────────────
    DESIGN PRINCIPLES APPLIED
   ────────────────────────────────────
   [x] Pluggable: BaseLLM abstract class defined
   [x] Factory: LLMFactory.create() routes by provider
   [x] Config-Driven: Provider read from settings.llm.provider
   [x] Error Handling: Unknown provider raises ValueError
   ────────────────────────────────────
   ```
