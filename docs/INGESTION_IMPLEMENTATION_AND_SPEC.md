# Ingestion 实现说明与 DEV_SPEC 对比

本文按**项目代码实际实现**逐步说明 Ingestion 每一步做了什么、用了什么策略，再与 `DEV_SPEC.md` 中的设计思路对比，标出一致与差异。

---

## 一、按步骤讲解：实现里每一步具体做了什么

整体流程（与代码一致）：**Integrity → Load → 登记图片 → Split → Transform → Encode → Store**。

### 1. Integrity（文件完整性检查）

**位置**：`pipeline.run()` 开头；实现依赖 `libs/loader/file_integrity.py`（默认 `SQLiteIntegrityChecker`）。

**具体动作**：

- 若未传 `force` 且配置了 `integrity_checker`：
  - 对当前文件路径计算 **SHA256**（`compute_sha256(path)`），得到 `file_hash`。
  - 查 SQLite 表 `ingestion_history`：`SELECT status FROM ingestion_history WHERE file_hash = ?`。
  - 若存在且 `status == 'success'`，则 **should_skip(file_hash) 为 True**，直接返回 `{"skipped": True, "file_hash": ...}`，不再执行 Load 及后续步骤。
- 若未配置 integrity 或 `force=True`，不查表、不跳过。
- **额外用途**：同一轮中算出的 `file_hash` 会写入 document metadata（见下），用于后续「按 file_hash 去重」与 chunk_id 生成。

**策略**：  
- **零成本增量**：相同文件（相同 SHA256）且曾成功摄取则跳过整条链路。  
- **存储**：SQLite，`data/db/ingestion_history.db`，WAL 模式；表结构含 `file_hash`(PK)、`file_path`、`status`、`error_msg`、`updated_at`。

---

### 2. Load（文档加载）

**位置**：`pipeline.run()` 中调用 `self._loader.load(path)`；默认 Loader 为 `libs/loader/pdf_loader.py` 的 **PdfLoader**。

**具体动作**：

- 用 **pypdf (PdfReader)** 逐页解析 PDF（**未使用** DEV_SPEC 中提到的 MarkItDown）。
- 每页：
  - **文本**：`page.extract_text()`，拼接成全文。
  - **图片**：`page.images` 遍历图片对象，取 `data`，按 PNG/JPEG 头判断后缀，写入 `data/images/{doc_hash}/{image_id}.png|.jpg`；在正文对应位置插入占位符 `[IMAGE: {image_id}]`；在列表里记录 `{id, path, page, text_offset, text_length, position}`。
- **doc_id**：`hashlib.sha256(Path(path).resolve().as_posix().encode()).hexdigest()[:16]`，与 path 绑定。
- 返回 **Document**：`id=doc_id`，`text=全文（含占位符）`，`metadata={source_path, images: [...]}`。
- 若 pipeline 在 Integrity 阶段算出了 `file_hash`，会 ** 覆盖一次 document**：`metadata` 增加 `file_hash`，便于下游去重与 chunk_id。

**策略**：  
- PDF → 纯文本 + 图片二进制落盘 + 占位符 + 元数据；图片失败只打日志，不阻塞。  
- 输出符合 C1 契约：Document 含 `id|text|metadata`，metadata 含 `source_path`、`images`。

---

### 3. 登记图片到 ImageStorage

**位置**：Load 之后、Split 之前；使用 `ingestion/storage/image_storage.py` 的 **ImageStorage**。

**具体动作**：

- 从 `document.metadata["images"]` 取出列表，对每一项若含 `id` 和 `path`，调用 `image_storage.register(id, path, collection=collection or document.id, doc_hash=document.id, page_num=...)`。
- 将「文档—图片」关系写入 **SQLite**（如 `data/db/image_index.db`），供后续数据浏览、删除、检索返回图片用。

**策略**：  
- Loader 只负责把图片写到磁盘并写在 Document.metadata；真正做「索引/登记」的是这一步，实现双轨存储中的「图片轨」。

---

### 4. Split（分块）

**位置**：`DocumentChunker.split_document(document)`；内部用 `libs/splitter` 的 **RecursiveCharacterTextSplitter**（LangChain）。

**具体动作**：

- **文本切分**：对 `document.text.strip()` 调用 `splitter.split_text()`。  
  - 默认实现为 **RecursiveCharacterTextSplitter**，`chunk_size`、`chunk_overlap` 来自 `settings.splitter`（如 512 / 50）。  
  - 按段落/换行/空格等递归切，尽量不打断 Markdown/代码块结构。
- **Chunk 构造**：对每个 segment 生成  
  - **id**：`{doc_id}_{index:04d}_{sha256(text)[:8]}`（与 DEV_SPEC 中「chunk_id 格式」一致）。  
  - **metadata**：`_inherit_metadata(document, index)` = **整份 document.metadata 的浅拷贝 + chunk_index**，因此 **每个 chunk 都带完整 document.metadata（含 images 列表）**。  
  - **start_offset / end_offset**：在全文中的字节偏移。  
  - **source_ref**：document.id。

**策略**：  
- 语义边界 + 定长控制（chunk_size/overlap）；不在此步做「只把图片 ref 给含占位符的 chunk」（图片过滤在 Transform 的 ImageCaptioner 中做）。

---

### 5. Transform（增强）

**位置**：对 `chunks` 依次执行 `self._transforms` 中每个 transform 的 `transform(chunks, trace)`。  
默认链：**ChunkRefiner → MetadataEnricher → ImageCaptioner**。

#### 5.1 ChunkRefiner

**策略**：  
- **规则去噪**：正则去掉多余空白、页眉页脚（如 "— 1 —"、Page N、N/M）、HTML 注释、仅由符号组成的行等；保留代码块与 Markdown。  
- **可选 LLM 重写**：默认 **use_llm=False**（避免大文档每 chunk 调 LLM）；若开启则用 prompt 模板 + LLM 重写，失败则回退到规则结果，并标记 metadata。

#### 5.2 MetadataEnricher

**策略**：  
- **规则**：title = 首行或前 N 字；summary = 前 N 字；tags = 从正文抽 `#tag` 或兜底 `["chunk"]`。  
- **可选 LLM**：默认 **use_llm=False**；若开启则调 LLM 生成 title/summary/tags（期望 JSON），失败则用规则结果并标记。

#### 5.3 ImageCaptioner

**策略**：  
- **只处理「本 chunk 正文里出现的图」**：从 `chunk.metadata.images` 取出 refs 后，用 `_image_refs_in_chunk_text()` 过滤，只保留在 `chunk.text` 中含 `[IMAGE: {id}]` 的 ref，避免因「每 chunk 都继承文档级 images」导致的同一张图被重复调 LLM。  
- **同图只调一次 LLM**：单次 `transform()` 内维护 `caption_cache: image_id -> caption`，同一 image_id 只请求一次 Vision LLM，其余 chunk 复用。  
- **可选 max_images**：可限制本次 transform 最多对 N 张图调 LLM（调试/控耗时）。  
- Vision LLM 不可用或单张失败：标记 `has_unprocessed_images`，不阻塞；caption 写回 `metadata["image_captions"]`。

---

### 6. Encode（编码）

**位置**：`BatchProcessor.process(chunks, batch_size=effective_batch)`；内部对每批先 **DenseEncoder** 再 **SparseEncoder**，合并成带 `dense_vector` 与 `sparse_vector` 的 **ChunkRecord**。

**Dense**：  
- 从 `libs/embedding` 的工厂创建当前配置的 Embedding（如 Qwen），对每批 `chunks` 的 `text` 调用 `embed(texts)`，得到向量列表，与 chunk 一一对应封装成 ChunkRecord（id、text、metadata、**dense_vector**）。  
- **Qwen 限制**：pipeline 中若 `embedding.provider == "qwen"`，则 `effective_batch = min(batch_size, 10)`，避免超过接口单次条数上限。

**Sparse**：  
- **SparseEncoder**：对每个 chunk 的 text 做简单分词（非字母数字切分、小写）、统计 term 频率，得到 `Dict[str, float]`（term -> tf），作为 ChunkRecord 的 **sparse_vector**，供 BM25 索引使用。

**策略**：  
- 双路编码（Dense + Sparse）、批处理；**未实现** DEV_SPEC 中的「按 content hash 差量计算、仅对新内容调 Embedding」的增量优化。

---

### 7. Store（写入）

**位置**：先 **VectorUpserter.upsert(records)** 写 Chroma，再用同一批 **stored_ids** 构造 **records_for_bm25**，用 **BM25Indexer.build(records_for_bm25).save()** 写 BM25。

**VectorUpserter**：  
- **chunk_id**：  
  - 若 metadata 有 **file_hash**：`chunk_id = SHA256(file_hash + chunk_index)`，同一文件不同 path 得到相同 id。  
  - 否则：`SHA256(source_path + chunk_index + content_hash[:8])`，兼容旧数据。  
- **去重**：在 upsert 前若 store 支持 `delete_by_metadata`，则先按 **file_hash** 删除、再按 **source_path** 删除，再写入当前 batch，保证同文件只保留一份、同 path 幂等。  
- 写入内容：id、vector、metadata（含 text，Chroma 需要）、不写 sparse_vector 到 Chroma。

**BM25**：  
- 使用 **与 Chroma 相同的 chunk_id**（由 VectorUpserter 返回的 id 列表构造 records_for_bm25），避免 Dense/Sparse 融合时同一 chunk 出现两套 id。  
- **当前实现**：每次对「当前文档」的 records 做 **build(records).save()**，即 **全量覆盖** 默认路径下的 BM25 索引文件（例如 `data/db/bm25/index.json`），而不是在已有索引上增量添加；多文档场景下若多次单文档摄取，BM25 中只会保留最后一次写入的文档的 chunk。

**Integrity 收尾**：  
- 若未跳过且未 force，则 `mark_success(file_hash, path)` 写入 SQLite，供下次 Integrity 跳过。

**策略**：  
- 向量存储：幂等 upsert + 按 file_hash/source_path 先删后写。  
- BM25：与向量库共用 chunk_id；当前为单文档全量覆盖索引文件，与 DEV_SPEC 中「增量/多文档」的设想有差异（见下对比）。

---

## 二、与 DEV_SPEC.md 的对比

### 2.1 一致的部分

| 设计点 (DEV_SPEC) | 实现情况 |
|-------------------|----------|
| **Integrity 前置、SHA256、SQLite、should_skip(success)** | 完全一致：`file_hash` 查表，成功则跳过整链。 |
| **Loader 输出 Document：id, text, metadata（source_path, images）** | 一致；PDF 用 pypdf 提取文本+图片，占位符 `[IMAGE: id]`，图片落盘。 |
| **Splitter 使用 RecursiveCharacterTextSplitter，语义边界** | 一致；chunk_size/chunk_overlap 来自配置。 |
| **Chunk 带 source_ref、chunk_index、start_offset/end_offset** | 一致；chunk_id 格式 `{doc_id}_{index:04d}_{hash}` 与 spec 描述一致。 |
| **Transform：规则 + 可选 LLM，失败回退不阻塞** | ChunkRefiner、MetadataEnricher 均规则兜底 + 可选 LLM；默认 LLM 关闭。 |
| **ImageCaptioner：Vision LLM 生成描述，写 metadata；不可用则降级** | 一致；并实现了「仅本 chunk 出现占位符的图」+「同图单次调用」的优化。 |
| **双路编码 Dense + Sparse（BM25），批处理** | 一致；Dense 走 Embedding 接口，Sparse 走 term 权重供 BM25。 |
| **Upsert 幂等、chunk_id 确定性** | 一致；且用 file_hash 时 id 与 path 解耦，与去重一致。 |
| **Pipeline 支持 on_progress、trace 各阶段** | 一致；trace 记录 load/split/transform/embed/upsert 及耗时。 |
| **DocumentManager 跨 Chroma/BM25/ImageStorage/Integrity 删除** | 有实现；按 source_path 或 chunk_ids 协调删除。 |

### 2.2 差异与说明

| 设计点 (DEV_SPEC) | 实现差异 | 说明 |
|-------------------|----------|------|
| **Loader 技术选型：MarkItDown** | 实际使用 **pypdf** | Spec 写「首选 MarkItDown」；当前为 pypdf 直接提取文本+图片，无 Markdown 转换。 |
| **Chunk metadata 中 image_refs：仅该 chunk 关联的图片** | 实现是 **整份 document.metadata 继承**，每个 chunk 都带全部 images | Spec 期望每个 Chunk 的 `image_refs` 只含本 chunk 关联的图；实现通过 ImageCaptioner 内「按 chunk 正文占位符过滤 + 同图缓存」弥补，避免重复调 LLM。 |
| **Embedding 差量：按 content hash 只对新内容算向量** | **未实现** | Spec 提到「仅针对新 content hash 执行向量化」；当前每份摄取都对当次 chunks 全量调 Embedding。 |
| **chunk_id 算法：hash(source_path + section_path + content_hash)** | 实现为 **file_hash + chunk_index** 或 **source_path + chunk_index + content_hash[:8]** | 与 spec 表述略有不同；实现强调与 file_hash 去重一致、同一文件同 id。 |
| **Upsert 前 Dedup & Normalize** | 实现为 **按 file_hash / source_path 删除后 upsert** | Spec 提到「向量/文本去重与哈希过滤」；实现用 file_hash（及 source_path）在向量库侧先删后写，无单独的 content-hash 去重层。 |
| **BM25 索引：增量/多文档** | 当前为 **单次 build(当前文档 records).save()，覆盖索引文件** | Spec 未明确说「每次只写当前文档」；实现上 BM25 是整索引覆盖，多文档多次摄取时仅保留最后一份文档的 chunk，与 Chroma 的「多文档累积」不一致。 |
| **图片描述注入：推荐注入正文** | 实现写 **metadata["image_captions"]** | Spec 推荐「描述替换/追加到正文」；当前只写入 metadata，检索仍主要靠正文与 Dense 向量（若需 caption 参与检索可后续把 caption 拼进 text 再 embed）。 |
| **图片描述幂等：processing_cache 按内容哈希复用** | **未实现** | Spec 提到为每张图描述算内容哈希并缓存；当前无此表，同图重复摄取会重新调 Vision LLM（但同一次 transform 内已按 image_id 缓存）。 |

---

## 三、小结

- **实现与 DEV_SPEC 在主线流程上一致**：Integrity → Load → 登记图片 → Split → Transform（Refiner + Enricher + ImageCaptioner）→ Encode（Dense + Sparse）→ Store（Chroma + BM25），以及 trace、on_progress、失败降级、DocumentManager 等。
- **主要差异**：Loader 用 pypdf 而非 MarkItDown；chunk 的 images 是整文档继承，通过 ImageCaptioner 的「占位符过滤 + 同图缓存」避免重复调用；未做 Embedding 差量、未做图片描述的内容哈希缓存；BM25 为单次全量覆盖索引；图片描述只写 metadata 未注入正文；chunk_id 公式与 spec 文字略有不同但意图一致（幂等、去重友好）。

若需要，我可以再根据某一条差异给出具体改造建议（例如 BM25 增量、或 caption 注入正文）。
