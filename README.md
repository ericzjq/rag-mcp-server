# Modular RAG MCP Server

> 一个可插拔、可观测的模块化 RAG (检索增强生成) 服务框架，通过 MCP (Model Context Protocol) 协议对外暴露工具接口，支持 Copilot / Claude 等 AI 助手直接调用。

---

## 🏗️ 项目概览

- **Ingestion Pipeline**：PDF → Markdown → Chunk → Transform → Embedding → Upsert（支持多模态图片描述）
- **Hybrid Search**：Dense (向量) + Sparse (BM25) + RRF Fusion + 可选 Rerank
- **MCP Server**：通过标准 MCP 协议暴露 `query_knowledge_hub`、`list_collections`、`get_document_summary` 等 Tools
- **Dashboard**：Streamlit 六页面管理平台（系统总览 / 数据浏览 / Ingestion 管理 / 追踪可视化 / 评估面板）
- **Evaluation**：Ragas + Custom 评估体系，支持 golden test set 回归测试

📖 详细架构与排期见 [DEV_SPEC.md](DEV_SPEC.md)。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆后进入项目根目录
cd mcp_server

# 创建虚拟环境并安装（可编辑模式）
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. 配置 API Key

复制配置模板并填入密钥（或使用环境变量）：

```bash
cp config/settings.yaml.example config/settings.yaml
# 编辑 config/settings.yaml，至少填写：
# - llm.api_key、embedding.api_key（或对应 provider 的 key）
# - 若使用 Qwen：embedding 可设 provider: qwen + api_key；vision_llm 可共用同一 DashScope key
```

> `config/settings.yaml` 已在 `.gitignore` 中，请勿提交含密钥的文件。

### 3. 首次摄取与查询

```bash
# 从项目根目录执行，确保 PYTHONPATH 包含 src
export PYTHONPATH=src   # Windows: set PYTHONPATH=src

# 摄取一个 PDF（请替换为你的文档路径）
python scripts/ingest.py --path /path/to/your/doc.pdf

# 检索测试
python scripts/query.py --query "你的问题" --top-k 5
```

---

## ⚙️ 配置说明

主配置文件为 `config/settings.yaml`，主要字段含义如下：

| 配置节 | 说明 |
|--------|------|
| **llm** | 主推理 LLM：`provider`（如 openai / deepseek / ollama）、`model`、`api_key`、`base_url`（可选） |
| **embedding** | 文本向量：`provider`（openai / azure / ollama / qwen）、`model`、`api_key`、`base_url`（可选）。Qwen 使用 DashScope OpenAI 兼容接口。 |
| **vector_store** | 向量库：`provider` 固定为 chroma，`persist_directory` 为本地目录（如 `data/chroma`） |
| **retrieval** | 检索参数：`top_k` 粗排条数、`rerank_top_m` 精排候选数 |
| **rerank** | 精排：`provider` 为 none / llm / cross_encoder |
| **splitter** | 分块：`chunk_size`、`chunk_overlap` |
| **evaluation** | 评估：`provider` 为 ragas / custom |
| **vision_llm** | （可选）图转文：`provider`（qwen / deepseek / azure）、`api_key`、`model` 等，用于 PDF 内图片描述 |

更多示例见 `config/settings.yaml.example`。

---

## 🔌 MCP 配置示例

### GitHub Copilot

在 Copilot 使用的 MCP 配置（如 `mcp.json`）中增加本 Server：

```json
{
  "mcpServers": {
    "mcp-server": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/mcp_server",
      "env": {
        "PYTHONPATH": "/path/to/mcp_server/src"
      }
    }
  }
}
```

请将 `cwd` 和 `PYTHONPATH` 中的 `/path/to/mcp_server` 替换为你的项目根目录绝对路径。

### Claude Desktop

在 Claude Desktop 配置目录下的 `claude_desktop_config.json` 中增加：

```json
{
  "mcpServers": {
    "mcp-server": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/mcp_server",
      "env": {
        "PYTHONPATH": "/path/to/mcp_server/src"
      }
    }
  }
}
```

配置完成后重启 Copilot / Claude Desktop，即可在对话中调用本 Server 提供的 `query_knowledge_hub` 等工具。

---

## 📊 Dashboard 使用指南

### 启动

在项目根目录执行：

```bash
python scripts/start_dashboard.py
```

或直接使用 Streamlit：

```bash
streamlit run src/observability/dashboard/app.py
```

浏览器会打开默认地址（通常为 http://localhost:8501）。

### 页面说明

| 页面 | 功能 |
|------|------|
| **系统总览** | 展示当前 LLM/Embedding/Reranker 等组件配置与向量条数等统计 |
| **数据浏览器** | 按集合查看已摄入文档列表、Chunk 详情与关联图片 |
| **Ingestion 管理** | 上传 PDF、选择集合、触发摄取、查看进度；支持删除已摄入文档 |
| **Ingestion 追踪** | 摄取历史列表与各阶段耗时条形图 |
| **Query 追踪** | 查询历史、按关键词筛选、Dense/Sparse 与 Rerank 阶段耗时 |
| **评估** | 选择 golden test set 路径、运行评估、查看 hit_rate / mrr 等指标 |

---

## 🧪 运行测试

在项目根目录、且已激活虚拟环境时：

```bash
# 设置 PYTHONPATH（若未设置）
export PYTHONPATH=src

# 单元测试（默认 -q）
pytest

# 按层级运行
pytest tests/unit -q
pytest tests/integration -q
pytest tests/e2e -q

# 仅 E2E 标记的用例（部分需配置文件或网络）
pytest -m e2e -q

# 详细输出
pytest -v
```

部分 E2E 用例依赖 `config/settings.yaml` 存在或需访问外部 API，可先完成配置后再跑 `pytest -m e2e`。

---

## 📋 全链路 E2E 验收（I5）

可按以下顺序手动验证完整流程：

1. **摄取**：`python scripts/ingest.py --path <PDF 文件路径> [--collection test]`  
   示例（使用项目内测试用 PDF）：`python scripts/ingest.py --path tests/fixtures/sample_documents/simple.pdf --collection test`
2. **查询**：`python scripts/query.py --query "测试查询" [--verbose]`，应返回检索结果
3. **Dashboard**：`python scripts/start_dashboard.py`，在「数据浏览器」与「Ingestion 追踪」中可看到刚摄入的文档与记录
4. **评估**：`python scripts/evaluate.py [--test-set tests/fixtures/golden_test_set.json]`，输出 hit_rate、mrr 等指标（依赖 golden test set 与已摄入数据）

全量自动化测试：`pytest -q`，应全部通过。

---

## ❓ 常见问题

**Q：API Key 如何配置？**  
A：在 `config/settings.yaml` 中填写对应 provider 的 `api_key`；也可通过环境变量在启动前注入，避免明文写入文件。

**Q：依赖安装失败或版本冲突？**  
A：使用项目根目录下的 `pip install -e .` 安装，以 `pyproject.toml` 为准。若需使用 Ragas 评估，请按 DEV_SPEC 或错误提示安装可选依赖。

**Q：MCP Client 连接不上 / 无响应？**  
A：确认 `cwd` 与 `PYTHONPATH` 指向项目根与 `src`；Server 使用 stdio 传输，无需端口。查看 stderr 日志排查配置或导入错误。

**Q：摄取时 Embedding 报 404 或 403？**  
A：检查 `embedding.base_url` 与 `embedding.model` 是否与所选服务商一致（如 DeepSeek 需 `/v1` 路径；Qwen 使用 DashScope 兼容地址）。API Key 是否有效、网络/代理是否可达。

**Q：Dashboard 启动后页面空白或报错？**  
A：确保在项目根目录启动，且 `config/settings.yaml` 存在且可读；部分页面依赖 Chroma 等数据目录，首次使用可先跑一次 ingest 再打开 Dashboard。

---

## 📂 分支说明

| 分支 | 用途 |
|------|------|
| **main** | 最新代码，适合直接使用或二次开发 |
| **dev** | 保留完整提交历史的开发分支 |
| **clean-start** | 仅工程骨架与 DEV_SPEC，适合按文档从零实现 |

---

## 📄 License

MIT
