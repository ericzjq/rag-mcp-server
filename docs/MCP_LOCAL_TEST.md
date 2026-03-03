# 本地测试 MCP Server 接口

MCP Server 使用 **stdio** 传输（标准输入/输出），无 HTTP 端口。下面三种方式可在本地验证接口是否正常。

---

## 前置条件

1. **在项目根目录**执行所有命令（即包含 `config/`、`scripts/`、`src/` 的目录）。
2. **设置 PYTHONPATH**（否则无法找到 `mcp_server`、`core` 等包）：
   ```bash
   export PYTHONPATH=src
   # Windows CMD: set PYTHONPATH=src
   # Windows PowerShell: $env:PYTHONPATH="src"
   ```
3. **配置文件**：`config/settings.yaml` 存在且可解析。  
   - `query_knowledge_hub` 会走真实检索（Embedding + Chroma + Reranker），需配置有效的 embedding/llm 等。  
   - 若仅验证「能返回结构、不报错」，可先用最小配置（无有效 API Key 时检索可能为空，但 initialize / tools/list 仍可成功）。

---

## 方式一：运行本地测试脚本（推荐）

项目提供脚本，自动启动 Server 并依次调用三个工具，并打印响应：

```bash
cd /path/to/mcp_server
export PYTHONPATH=src
python scripts/test_mcp_local.py
```

脚本会依次执行：

| 步骤 | 说明 |
|------|------|
| initialize | 校验 Server 启动与协议版本 |
| tools/list | 列出 `query_knowledge_hub`、`list_collections`、`get_document_summary` |
| tools/call query_knowledge_hub | 传入 `query="测试查询"`、`top_k=3`，打印文本摘要与 citations 条数 |
| tools/call list_collections | 列出 `data/documents/` 下集合名 |
| tools/call get_document_summary | 传入 `doc_id="test_doc_id"`（无对应元数据时会返回规范错误，属预期） |

若全部步骤无报错并打印「全部请求已完成，MCP Server 接口运行正常」，则说明接口运行正常。

---

## 方式二：运行 E2E 自动化测试

使用 pytest 模拟 Client 发送 JSON-RPC，断言返回结构：

```bash
export PYTHONPATH=src
pytest tests/e2e/test_mcp_client.py -v
```

- 会启动真实 `mcp_server.server` 子进程，发送 initialize → tools/list → tools/call（query_knowledge_hub）。
- 依赖 `config/settings.yaml` 存在；若不存在会自动 **skip**。
- 会断言：initialize 含 serverInfo、tools 列表含 query_knowledge_hub、call 返回的 content 与 structuredContent.citations 存在。

适合 CI 或本地一键校验协议与返回形状。

---

## 方式三：使用 MCP 客户端（Copilot / Claude Desktop）

在 IDE 或 Claude Desktop 中配置本 Server 后，在对话里直接使用「查询知识库」等能力，即是对接口的真人可用性测试。

配置示例见 README 的「MCP 配置示例」：正确设置 `command`、`args`、`cwd`、`PYTHONPATH` 后，Client 会通过 stdio 与本 Server 通信。

---

## 常见问题

- **ModuleNotFoundError: No module named 'mcp_server'**  
  未设置 `PYTHONPATH=src` 或未在项目根目录执行。

- **配置文件不存在**  
  复制 `config/settings.yaml.example` 为 `config/settings.yaml`，并按需填写 api_key 等。

- **query_knowledge_hub 返回空或报错**  
  需已用 `scripts/ingest.py` 摄入过文档，且 `config/settings.yaml` 中 embedding/vector_store 等配置正确；否则检索结果为空或调用失败属正常。

- **get_document_summary 返回 error**  
  该接口依赖 `data/db/document_metadata.json`（或配置的 metadata 路径）中存在对应 doc_id；测试时用不存在的 doc_id 会返回规范错误，用于验证「错误格式」也是正确的。
