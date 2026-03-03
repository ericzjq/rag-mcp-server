# Cursor 调用本 MCP Server 配置指南

本文说明如何在 Cursor IDE 中配置并调用本仓库提供的 MCP Server（工具名：**mcp_rag_tool**），在对话中使用「查询知识库」「列举集合」「获取文档摘要」等能力。

**无需在本地单独启动 MCP 进程**：配置好 `.cursor/mcp.json` 或设置中的 MCP 后，Cursor 会在需要时**自动**用配置里的 `command` 启动本 Server 子进程，无需你手动运行 `python -m mcp_server.server`。若出现 Error，多半是 Cursor 启动该进程时失败（如工作目录、Python 路径不对），可按文末常见问题排查。

---

## 按 Cursor 官方说明加载本 MCP

Cursor 官方支持两种加载方式（[Model Context Protocol | Cursor 文档](https://docs.cursor.com/context/mcp)）：**设置界面** 与 **JSON 配置文件**。任选其一即可。

### 方式 A：通过设置界面（官方推荐）

1. **打开 Cursor 设置**  
   - macOS：`Cmd + ,`  
   - Windows / Linux：`Ctrl + ,`

2. **进入 MCP 配置**  
   在左侧找到 **「Tools」** 或 **「Features」**，进入 **「MCP」**（或 **「Tools & MCP」**）页面。

3. **添加 MCP Server**  
   点击 **「Add new MCP server」**（或「添加新的 MCP 服务器」）。

4. **填写本 Server 的配置**  
   - **Name（名称）**：`mcp_rag_tool`（或任意你喜欢的名称，用于在 Cursor 中识别）  
   - **Type（类型）**：选择 **`command`**（本 Server 通过 stdio 启动，非 HTTP）  
   - **Command（命令）**：`.venv/bin/python`（推荐，确保已安装 PyYAML 等依赖；Windows 填 `.venv\\Scripts\\python.exe`。若未建 venv 可暂填 `python3`，但可能报 PyYAML 错误）  
   - **Arguments（参数）**：`-m mcp_server.server`（若界面是「一个输入框」，可填：`-m mcp_server.server`；若为「多参数列表」，则填一项：`-m`，再填一项：`mcp_server.server`）  
   - **Env / 环境变量**（若有该选项）：添加一条  
     - 名称：`PYTHONPATH`  
     - 值：`src`（当 Cursor 以**本仓库根目录**为工作区时）；若界面只支持「当前工作区路径」，可填 `${workspaceFolder}/src` 或等效占位符（视 Cursor 版本而定）

5. **保存并重启**  
   保存后**完全退出 Cursor 再重新打开**（MCP 仅在启动时加载）。

> **注意**：通过 UI 添加时，Cursor 通常以**当前打开的工作区根目录**作为 MCP 进程的 cwd。因此请先**用 Cursor 打开本仓库根目录**（包含 `config/`、`src/` 的目录），再按上述步骤添加，这样 `PYTHONPATH=src` 和 `config/settings.yaml` 才能被正确找到。

### 方式 B：通过 JSON 配置文件（官方支持）

在**本仓库根目录**下创建或编辑 **`.cursor/mcp.json`**（项目级配置），内容如下：

```json
{
  "mcpServers": {
    "mcp_rag_tool": {
      "command": ".venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      }
    }
  }
}
```

- **项目级**：放在本仓库根目录的 `.cursor/mcp.json`，仅当打开该仓库时生效。  
- **全局**：放在用户目录下的 `~/.cursor/mcp.json`（macOS/Linux）或 `%APPDATA%\Cursor\mcp.json`（Windows），对所有工作区生效（此时如需指定本仓库，通常要在 `env` 或 `cwd` 中写本仓库的绝对路径）。

保存后**完全退出 Cursor 再重新打开**。

本仓库已自带上述 `.cursor/mcp.json`，用 Cursor 打开本仓库根目录即可使用，无需再手动添加。

---

## 前置条件

| 条件 | 说明 |
|------|------|
| **用 Cursor 打开本仓库根目录** | 即打开包含 `config/`、`scripts/`、`src/` 的目录，确保 MCP 进程的工作目录为项目根。 |
| **已安装依赖** | 在项目根执行 `python3 -m venv .venv && .venv/bin/pip install -e .`（或使用已有虚拟环境）。MCP 配置使用 `.venv/bin/python`，否则会因缺 PyYAML 等依赖报错。 |
| **已准备配置文件** | 存在 `config/settings.yaml`（可复制 `config/settings.yaml.example` 并填写 api_key 等）。 |
| **（可选）已摄入文档** | 若希望检索有结果，需先执行 `scripts/ingest.py --path <PDF路径>` 摄入文档。 |

---

## 方式一：使用仓库自带的 MCP 配置（推荐）

本仓库已包含 **`.cursor/mcp.json`**，将本 Server 注册为 **mcp_rag_tool**：

```json
{
  "mcpServers": {
    "mcp_rag_tool": {
      "command": ".venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      }
    }
  }
}
```

（使用项目虚拟环境 `.venv/bin/python` 确保已安装 PyYAML 等依赖；`cwd` 与 `PYTHONPATH` 使用 `${workspaceFolder}` 确保以本仓库根目录启动。）

**操作步骤：**

1. 用 Cursor 打开**本仓库根目录**（不要只打开子目录）。
2. 确认 `.cursor/mcp.json` 存在且内容如上（一般 clone 后即有）。
3. **完全退出 Cursor 后重新打开**（或按 Cursor 要求重载 MCP），使配置生效。
4. 在 Cursor 的 AI 对话中即可使用本 Server 提供的工具（如让 AI「用知识库查一下 xxx」）。

无需修改配置即可使用；若 Cursor 未识别，请检查是否在项目根打开、是否已重启。

---

## 方式二：在其他项目中挂载本 Server

若你是在「其他项目」的 workspace 中打开 Cursor，但希望调用本仓库的 MCP Server，需在该项目的 `.cursor/mcp.json` 中写**绝对路径**。

1. 在**当前打开的项目**根目录下创建或编辑 `.cursor/mcp.json`。
2. 将下面的 `/path/to/mcp_server` 替换为本仓库在你机器上的**绝对路径**（例如 `/Users/xxx/mcp_server`）：

```json
{
  "mcpServers": {
    "mcp_rag_tool": {
      "command": "/path/to/mcp_server/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/mcp_server",
      "env": {
        "PYTHONPATH": "/path/to/mcp_server/src"
      }
    }
  }
}
```

（将 `/path/to/mcp_server` 替换为本仓库在你机器上的绝对路径；使用该仓库下的 `.venv/bin/python` 确保依赖已安装。）

3. 保存后**完全重启 Cursor**。

---

## 提供的工具（mcp_rag_tool）

| 工具名 | 说明 |
|--------|------|
| **query_knowledge_hub** | 混合检索 + 精排，返回带引用的 Top-K 片段（Markdown + citations）。 |
| **list_collections** | 列举知识库中的文档集合（data/documents 下子目录名）。 |
| **get_document_summary** | 按 doc_id 获取文档摘要与元信息（title/summary/tags）。 |

在 Cursor 中可通过自然语言让 AI 调用这些工具，例如：「用知识库查一下 RAG 相关的内容」「当前有哪些文档集合？」。

---

## 常见问题

- **"PyYAML is required for load_settings"**  
  MCP 进程用的 Python 未安装项目依赖。请确保使用**项目虚拟环境**：`.cursor/mcp.json` 中 `"command"` 为 **`.venv/bin/python`**（Windows 用 `.venv\\Scripts\\python.exe`），并在项目根执行 `python3 -m venv .venv && .venv/bin/pip install -e .`。若未建 venv，Cursor 会用系统 `python3`，缺 PyYAML 等会报此错。

- **"spawn python ENOENT" / "No server info found"**  
  系统找不到 `python` 命令（常见于 macOS）。配置已使用 `.venv/bin/python`；若未创建虚拟环境：先执行 `python3 -m venv .venv && .venv/bin/pip install -e .`。若仍报错：把 `cwd` 和 `PYTHONPATH` 中的 `${workspaceFolder}` 换成你本机仓库的**绝对路径**，或把 `"command"` 改为本机 Python 的绝对路径。

- **Cursor 里看不到 mcp_rag_tool / 工具调用失败**  
  确认：1）用 Cursor 打开的是**本仓库根目录**；2）已**完全退出并重新打开** Cursor；3）`config/settings.yaml` 存在且可读。

- **query_knowledge_hub 返回「未找到相关文档」**  
  需先执行 `scripts/ingest.py` 摄入至少一份文档，并确保配置文件中的 embedding/vector_store 正确。

- **ModuleNotFoundError: No module named 'mcp_server'**  
  说明 MCP 进程的 PYTHONPATH 未包含 `src`。若使用方式一，请确保在**本仓库根目录**打开；若使用方式二，请检查 `cwd` 与 `PYTHONPATH` 的绝对路径是否正确。
