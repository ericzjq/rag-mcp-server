# 如何对检索执行 RAGAS 评估

本文说明在当前项目中如何对**一次或多次检索**执行 RAGAS 评估（Faithfulness、Answer Relevancy、Context Precision 等）。

---

## 1. 机制说明

- **评估单位**：RAGAS 在项目里按 **golden test set** 批量执行。每条 test case = 一次「检索 + 评估」：对给定 `query` 做 HybridSearch + Reranker 得到 `retrieved_ids`，再交给 Evaluator（如 RagasEvaluator）计算该条 query 的 RAGAS 指标。
- **一次检索的 RAGAS**：即 golden 文件中的**一条** test case 对应的那次检索的 RAGAS；要评估「一次」检索，只需在 golden 里只保留一条 test case，或跑完评估后在报告里看某一条 query 的 metrics。
- **依赖**：Ragas 库（`pip install ragas`）、配置中 `evaluation.provider: ragas`，以及 LLM 配置（Ragas 内部会调用 LLM 计算部分指标）。

---

## 2. 前置准备

### 2.1 安装 Ragas

```bash
pip install ragas
# 或项目虚拟环境
.venv/bin/pip install ragas
```

### 2.2 配置

在 `config/settings.yaml` 中：

- 设置 **evaluation.provider** 为 **ragas**：
  ```yaml
  evaluation:
    provider: ragas
  ```
- 确保 **llm** 段已配置（Ragas 会用到 LLM），例如：
  ```yaml
  llm:
    provider: openai   # 或 azure / deepseek 等
    model: gpt-4o-mini
    api_key: "sk-..."
  ```

### 2.3 Golden Test Set

准备一个 JSON 文件，包含若干条「query + 期望命中的 chunk」：

```json
{
  "test_cases": [
    {
      "query": "你的查询文本",
      "expected_chunk_ids": ["chunk_id_1", "chunk_id_2"],
      "expected_sources": ["文档名.pdf"]
    }
  ]
}
```

- **query**：用于检索的问题文本。
- **expected_chunk_ids**：期望被召回的 chunk 的 id，需与**已摄入**的向量库/BM25 中的 chunk_id 一致（否则 hit_rate/mrr 会异常，RAGAS 仍会算，但可能基于占位上下文）。
- **expected_sources**：可选，仅作说明。

若只想对**一次检索**做 RAGAS，在 `test_cases` 里只保留一条即可。

#### 如何知道文档被分为多少 chunk、每个 chunk_id 与内容？

项目里**真正写入向量库的 chunk_id** 是**确定性哈希**（由 `source_path + chunk_index + 内容哈希` 生成），是一串 64 位十六进制字符串。填写 `expected_chunk_ids` 时，必须使用这些**真实 id**，不能自己编。

**推荐方式：用 Dashboard「数据浏览器」查看**

1. 启动 Dashboard：`.venv/bin/python scripts/start_dashboard.py`
2. 打开 **「数据浏览器」** 页
3. 在文档列表中，每个文档会显示 **「（N chunks, M 图）」**，这里的 **N** 即该文档被分成的 **chunk 数量**
4. 点击某文档旁的 **「查看详情」**
5. 在详情中会列出该文档的 **Chunks**：每个块是一个可展开项，**标题即该 chunk 的 chunk_id**，展开后可以看到**正文内容**和 **metadata**

把这里看到的 chunk_id 复制到 golden 的 `expected_chunk_ids` 即可（可多选你期望被某条 query 命中的若干 chunk）。

**辅助方式：用「在线检索」反查 id**

- 在 Dashboard **「在线检索」** 页输入一条与目标文档相关的 query，执行检索
- 召回结果中每条会显示 **chunk_id**（及 score、内容）
- 这些 chunk_id 与向量库中一致，可直接用于 golden 的 `expected_chunk_ids`

**小结**：文档被分为多少 chunk → 看「数据浏览器」里该文档的 chunk 数；每个 chunk 的 id 和内容 → 在同一页「查看详情」里逐个查看；或通过「在线检索」用 query 召回后从结果里抄写 chunk_id。

### 2.4 数据就绪

- 已对相关文档执行过 **ingest**（`scripts/ingest.py` 或 Dashboard 上传摄取），这样检索才能返回与 golden 中 `expected_chunk_ids` 对应的数据。

---

## 3. 执行 RAGAS 评估

### 方式一：命令行脚本（推荐）

在项目根目录执行：

```bash
# 使用默认 golden 路径 tests/fixtures/golden_test_set.json、默认 config
.venv/bin/python scripts/evaluate.py

# 指定 golden 文件与 top_k
.venv/bin/python scripts/evaluate.py --test-set path/to/your_golden.json --top-k 10

# 指定配置文件
.venv/bin/python scripts/evaluate.py --config config/settings.yaml
```

输出为 JSON，包含：

- `hit_rate`、`mrr`：召回层面指标
- `query_results`：每条 query 的 `query`、`retrieved_ids`、`expected_chunk_ids`、`hit_rate`、`mrr`、**metrics**（RAGAS：faithfulness、answer_relevancy、context_precision 等）

每条 `query_results[i]` 即**一次检索**的 RAGAS 结果。

### 方式二：Dashboard

1. 启动 Dashboard：`.venv/bin/python scripts/start_dashboard.py`
2. 打开 **「评估」** 页：
   - 填写 **Golden test set 路径**（如 `tests/fixtures/golden_test_set.json` 或你的单条 golden）
   - 设置 **top_k**
   - 点击 **「运行评估」**
3. 运行完成后：
   - 当前页会展示 hit_rate、mrr 及各 query 的 metrics（含 RAGAS）
   - 报告会自动保存到 **logs/eval_report_latest.json**
4. 打开 **「RAGAS 评估结果」** 页：
   - 路径填 `logs/eval_report_latest.json`（或其它已保存的报告路径）
   - 点击 **「加载报告」**，即可查看汇总指标与每条 query 的 RAGAS 明细

---

## 4. 只评估「一次」检索

- **做法一**：golden 里只保留一条 test case，然后按上面任一种方式执行；得到的 `query_results` 只有一条，即这一次检索的 RAGAS。
- **做法二**：用多条 test case 跑完评估后，在脚本输出的 `query_results` 或 Dashboard「RAGAS 评估结果」页中，只看你关心的那条 query 的 metrics。

---

## 5. 常见问题

- **Ragas 报错或指标全 0**：检查是否 `pip install ragas`、配置中 `evaluation.provider: ragas`，以及 llm 配置正确（Ragas 会调 LLM）。
- **hit_rate 为 0**：说明 `expected_chunk_ids` 与当前索引中的 chunk_id 对不上，需先对目标文档做 ingest，并让 golden 中的 id 与真实 chunk_id 一致（或先用「在线检索」页查一次，确认返回的 chunk_id 再写入 golden）。
- **报告文件找不到**：Dashboard 运行评估后默认写入项目根下的 `logs/eval_report_latest.json`；在「RAGAS 评估结果」页若填相对路径，会相对项目根解析。
