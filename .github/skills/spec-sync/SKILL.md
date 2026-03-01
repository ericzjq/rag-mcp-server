---
name: spec-sync
description: 同步 DEV_SPEC.md 并拆分为 specs/ 下的章节文件。运行 sync_spec.py 更新后，通过 SPEC_INDEX.md 导航。所有基于 spec 的操作都依赖此步骤。用户说「同步规范」「sync spec」或在进行任何依赖 spec 的任务前使用。
metadata:
  category: documentation
  triggers: "sync spec, update spec, 同步规范"
allowed-tools: Bash(python:*) Read
---

# Spec Sync（规格同步）

本 Skill 将主规格文档（`DEV_SPEC.md`）同步并拆分为更小的、按章节划分的文件，存放在 `specs/` 目录下。

> **前置条件**：所有基于 spec 的操作都依赖拆分后的 spec 文件，其他 Skill 需读取这些文件才能执行任务。

---

## 如何使用

### 在 dev-workflow 中（自动）

当你触发 dev-workflow（例如「下一阶段」或「继续开发」）时，**spec-sync 会作为 Stage 1 自动执行**，无需手动操作。

### 手动同步（仅特殊场景）

仅在以下情况手动执行：
- 在流水线外单独编辑了 `DEV_SPEC.md`
- spec 文件损坏或缺失
- 需要单独测试某个 Skill

```bash
# 正常同步
python .github/skills/spec-sync/sync_spec.py

# 强制重新生成（即使未检测到变更）
python .github/skills/spec-sync/sync_spec.py --force
```

---

### 同步脚本做了什么

脚本会执行以下操作：
1. 从项目根目录读取 `DEV_SPEC.md`
2. 计算哈希以检测变更
3. 将文档按章节拆分为 `specs/` 下的文件
4. 生成 `SPEC_INDEX.md` 作为导航索引

---

### 同步后：用 SPEC_INDEX.md 导航

**以 `SPEC_INDEX.md` 为入口**，了解各 spec 文件的内容：

```
Read: .github/skills/spec-sync/SPEC_INDEX.md
```

该索引文件提供：
- 各章节内容摘要
- 快速定位所需 spec 的参考

然后从 `specs/` 目录按需读取具体章节文件：

```
Read: .github/skills/spec-sync/specs/05-architecture.md
```

---

## 目录结构

```
.github/skills/spec-sync/
├── SKILL.md              ← 本文件
├── SPEC_INDEX.md         ← 自动生成的索引（导航）
├── sync_spec.py          ← 同步脚本
├── .spec_hash            ← 用于变更检测的哈希文件
└── specs/                ← 拆分后的章节文件
    ├── 01-overview.md
    ├── 02-features.md
    ├── 03-tech-stack.md
    ├── 04-testing.md
    ├── 05-architecture.md
    ├── 06-schedule.md
    └── 07-future.md
```

---

## 重要说明

- **不要直接编辑 `specs/` 下的文件** — 它们由脚本自动生成
- **始终只编辑 `DEV_SPEC.md`**，然后重新运行同步脚本
- 使用 `--force` 可在未检测到变更时仍强制重新生成：
  ```bash
  python .github/skills/spec-sync/sync_spec.py --force
  ```
