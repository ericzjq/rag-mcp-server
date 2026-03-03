# 端到端测试说明 (E2E Tests)

本文档按测试文件逐步说明：每个 E2E 测试在测什么、哪些环节使用**真实**数据/LLM、哪些使用 **Mock**，以及测试的**输入**与**输出**。

---

## 1. 测试文件总览

| 文件 | 测试数量 | 标记 | 说明 |
|------|----------|------|------|
| `tests/e2e/test_data_ingestion.py` | 2 | 无 mark | 摄取脚本与 Pipeline 产物、二次跳过 |
| `tests/e2e/test_mcp_client.py` | 1 | `@pytest.mark.e2e` | MCP Server 子进程 + tools/list、query_knowledge_hub |
| `tests/e2e/test_dashboard_smoke.py` | 6 | `@pytest.mark.e2e` | Dashboard 六页加载冒烟 |
| `tests/e2e/test_recall.py` | 1 | `@pytest.mark.e2e` | 基于 golden set 的召回率回归 |

---

## 2. test_data_ingestion.py

### 2.1 `test_ingest_script_help`

| 项目 | 说明 |
|------|------|
| **目的** | 确认 `scripts/ingest.py` 可执行且 `--help` 正常。 |
| **真实 / Mock** | 无 Mock、无真实 API：仅子进程执行脚本，不读配置、不跑 Pipeline。 |
| **输入** | 命令：`python scripts/ingest.py --help`，工作目录为项目根。 |
| **输出** | `returncode == 0`；stdout 中包含 `--path`、`--collection`、`--force`。 |

---

### 2.2 `test_ingest_produces_data_db_and_skips_on_second_run`

| 项目 | 说明 |
|------|------|
| **目的** | 跑一次摄取在临时目录下产生产物（BM25 索引、integrity DB）；再跑一次（不 `--force`）应被跳过。 |
| **真实** | • 临时目录 `tmp_path` 下的真实文件与目录<br>• 真实**最小 PDF**：用 `pypdf.PdfWriter` 生成的单页空白 PDF<br>• 真实 **config**：`tmp_path/config/settings.yaml`（可解析的 YAML）<br>• 真实 **ChromaStore**：`persist_directory=tmp_path/data/chroma`<br>• 真实 **SQLiteIntegrityChecker**：`tmp_path/data/db/ingestion_history.db`<br>• 真实 **BM25 索引**：写入 `tmp_path/data/db/bm25/`<br>• 真实 **ImageStorage**：SQLite + 本地目录<br>• 真实 **Splitter**（LangChain）、**SparseEncoder**（BM25 词频）等 Pipeline 内部组件 |
| **Mock** | • **Loader**：`_MockLoader` 不读 PDF 内容，直接返回固定 `Document(id="e2e_doc", text="Chunk one.\n\nChunk two.", metadata={"source_path": path})`<br>• **BatchProcessor**：`_MockBatchProcessor` 不调 Embedding API，返回固定 `dense_vector=[0.1]*4`，仅用真实 SparseEncoder 生成 sparse_vector |
| **输入** | • `tmp_path`（pytest 提供的临时目录）<br>• 上述 config 与 PDF 路径<br>• `pipeline.run(pdf_path, collection="e2e", force=False)` 调用两次 |
| **输出** | • 第一次：`result1` 中无 `skipped` 或未跳过；`records_count >= 1`；`bm25_dir/index.json` 存在；`ingestion_history.db` 存在<br>• 第二次：`result2.get("skipped") is True` |

---

## 3. test_mcp_client.py

### 3.1 `test_mcp_client_tools_list_and_query_knowledge_hub_returns_citations`

| 项目 | 说明 |
|------|------|
| **目的** | 以子进程启动真实 MCP Server，通过 stdin 发送 JSON-RPC，完成 initialize → tools/list → tools/call（query_knowledge_hub），并校验返回结构中含有 citations。 |
| **真实** | • **MCP Server 进程**：`python -m mcp_server.server`，使用项目根为 cwd，`PYTHONPATH=src`<br>• **配置文件**：`config/settings.yaml`（若存在）— 内含真实 API Key 时，Server 内会走真实 **Embedding**、**Chroma**、**Reranker** 等<br>• **query_knowledge_hub**：传入 `query="测试查询"`，Server 内部执行完整检索链路（HybridSearch + 可选 Reranker），即**真实检索、真实向量库、真实配置** |
| **Mock** | 无 Mock；若 `config/settings.yaml` 不存在则 **skip**。 |
| **输入** | • 环境：`PYTHONPATH=src` + 项目根<br>• 标准输入依次写入三行 JSON-RPC：<br>  - `initialize`<br>  - `tools/list`<br>  - `tools/call`，`name="query_knowledge_hub"`, `arguments={"query":"测试查询"}` |
| **输出** | • initialize：`result` 存在且含 `serverInfo`<br>• tools/list：`result.tools` 中存在 `query_knowledge_hub`<br>• tools/call：无 `error`；`result.content` 非空；`result.content[0].type == "text"` 且含 `text`；`result.structuredContent.citations` 存在且为 list |

---

## 4. test_dashboard_smoke.py

六条用例结构相同，仅页面与预期标题不同，下表以「系统总览」为例说明；其余五页（数据浏览器、Ingestion 管理、Ingestion 追踪、Query 追踪、评估）同理。

### 4.1 通用流程（以 `test_dashboard_overview_page_loads` 为例）

| 项目 | 说明 |
|------|------|
| **目的** | 在无浏览器环境下用 Streamlit AppTest 执行单页 `run(config_path=..., work_dir=...)`，确认页面渲染不抛异常且出现预期标题。 |
| **真实** | • **Streamlit 运行时**：`st.testing.v1.AppTest.from_string(script)` 真实执行脚本<br>• **页面逻辑**：真实 `observability.dashboard.pages.overview.run()` 等，真实调用 ConfigService、ChromaStore.get_collection_stats 等（但数据来自临时目录） |
| **Mock / 最小数据** | • **配置**：`tmp_path/config/settings.yaml` 为最小可解析 YAML（无真实 API Key，仅满足 load_settings 不报错）<br>• **工作目录**：`work_dir=tmp_path`，Chroma 等路径指向临时目录，通常无真实已摄入数据<br>• 不发起真实 Embedding/LLM 请求；若有 Chroma 读操作，读到的是空或临时数据 |
| **输入** | • `tmp_path`<br>• 页面模块路径（如 `observability.dashboard.pages.overview`）<br>• 预期标题（如 `"系统总览"`）<br>• 脚本字符串：`import streamlit as st; from <module> import run; run(config_path=..., work_dir=...)` |
| **输出** | • `AppTest.run(timeout=10)` 无未捕获异常<br>• `at.title` 至少一条，且 `at.title[0].value == expected_title` |

### 4.2 六条用例一览

| 测试函数 | 页面模块 | 预期标题 |
|----------|----------|----------|
| `test_dashboard_overview_page_loads` | overview | 系统总览 |
| `test_dashboard_data_browser_page_loads` | data_browser | 数据浏览器 |
| `test_dashboard_ingestion_manager_page_loads` | ingestion_manager | Ingestion 管理 |
| `test_dashboard_ingestion_traces_page_loads` | ingestion_traces | Ingestion 追踪 |
| `test_dashboard_query_traces_page_loads` | query_traces | Query 追踪 |
| `test_dashboard_evaluation_panel_page_loads` | evaluation_panel | 评估 |

---

## 5. test_recall.py

### 5.1 `test_recall_hit_rate_above_threshold`

| 项目 | 说明 |
|------|------|
| **目的** | 使用项目配置与 golden test set 跑完整评估流程（HybridSearch + Evaluator），做召回率回归：整体 hit_rate 不低于设定阈值。 |
| **真实** | • **配置**：`config/settings.yaml` 或 `MCP_CONFIG_PATH` 指向的配置文件<br>• **Golden test set**：`tests/fixtures/golden_test_set.json`（含 `test_cases`，每条有 `query`、`expected_chunk_ids`、`expected_sources`）<br>• **HybridSearch**：真实 Dense + Sparse + Fusion，即真实 **Embedding API**、**Chroma**、**BM25 索引**<br>• **EvalRunner**：真实 Evaluator（如 CustomEvaluator），用 golden 的 expected_chunk_ids 算 hit_rate / mrr |
| **Mock** | 无 Mock；若 `golden_test_set.json` 无 `test_cases` 或配置文件不存在则 **skip**。 |
| **输入** | • `tests/fixtures/golden_test_set.json`（示例内容：两条 query，如「如何配置 Azure OpenAI？」「RAG 检索流程是什么？」及对应 expected_chunk_ids）<br>• 配置文件路径<br>• `EvalRunner.run(golden_path, top_k=10)` |
| **输出** | • `report.hit_rate >= MIN_HIT_RATE_THRESHOLD`（当前阈值为 0.0）<br>• `len(report.query_results) == len(test_cases)` |

> **注意**：golden 中的 `expected_chunk_ids` 需与当前向量库/BM25 中实际摄入的 chunk id 对应，否则命中率可能为 0。通常需先对指定文档做 ingest，再跑该测试。

---

## 6. 汇总表：真实 vs Mock

| 测试 | 真实数据/服务 | Mock / 最小化 |
|------|----------------|----------------|
| **test_ingest_script_help** | 无（仅执行 --help） | 无 |
| **test_ingest_produces_data_db_...** | 临时目录、真实 PDF 文件、Chroma、SQLite、BM25、Splitter、SparseEncoder | Loader（固定 Document）、BatchProcessor（固定 dense 向量，不调 Embedding API） |
| **test_mcp_client_tools_list_...** | MCP Server 进程、config/settings.yaml、HybridSearch（Embedding + Chroma + Reranker）、query_knowledge_hub 全链路 | 无（缺 config 则 skip） |
| **test_dashboard_*_page_loads** | Streamlit、页面代码、ConfigService、临时 config 与 work_dir | 最小 config（无真实 Key）、临时目录（无真实业务数据） |
| **test_recall_hit_rate_...** | config、golden_test_set.json、HybridSearch、Chroma、BM25、Evaluator | 无（缺 config 或 test_cases 则 skip） |

---

## 7. 运行方式

```bash
# 运行全部 E2E（部分会 skip 若缺 config / golden）
export PYTHONPATH=src
pytest tests/e2e -v

# 仅运行带 @pytest.mark.e2e 的用例
pytest tests/e2e -v -m e2e

# 运行单文件
pytest tests/e2e/test_data_ingestion.py -v
pytest tests/e2e/test_mcp_client.py -v -m e2e
pytest tests/e2e/test_dashboard_smoke.py -v -m e2e
pytest tests/e2e/test_recall.py -v -m e2e
```

依赖说明：

- **test_mcp_client**、**test_recall**：需要有效的 `config/settings.yaml`（含 API Key 等）；test_recall 还需向量库中已有与 golden 中 expected_chunk_ids 对应的数据，否则可能 0 命中。
- **test_dashboard_smoke**：仅需可解析的 config（可为最小配置），不依赖真实 API 或真实数据。
- **test_data_ingestion**：不依赖外部 API，仅用临时目录与 Mock 编码层。
