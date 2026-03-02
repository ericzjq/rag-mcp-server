"""
MCP Server 集成测试（E1）：子进程启动 server，发送 initialize，校验 stdout 仅含 MCP 响应、stderr 有日志。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"


def test_mcp_server_initialize_returns_server_info_and_capabilities() -> None:
    """启动 server 能完成 initialize；stdout 仅一条 JSON-RPC 响应，含 serverInfo 与 capabilities。"""
    env = {**os.environ, "PYTHONPATH": os.path.pathsep.join([str(SRC), str(PROJECT_ROOT)])}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    req = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
    proc.stdin.write(req)
    proc.stdin.flush()
    proc.stdin.close()
    out_line = proc.stdout.readline()
    stderr_content = proc.stderr.read()
    proc.wait(timeout=5)

    assert out_line.endswith("\n")
    payload = json.loads(out_line.strip())
    assert payload.get("jsonrpc") == "2.0"
    assert payload.get("id") == 1
    result = payload.get("result")
    assert result is not None, payload
    assert "serverInfo" in result
    assert result["serverInfo"].get("name") == "mcp-server"
    assert "capabilities" in result
    assert "tools" in result["capabilities"]
    # stderr 有日志，stdout 不污染
    assert len(stderr_content) > 0, "stderr should contain log output"
    assert "MCP server started" in stderr_content or "started" in stderr_content.lower()


def test_query_knowledge_hub_returns_markdown_and_citations() -> None:
    """tools/call query_knowledge_hub 返回 content[0] 为 Markdown、structuredContent.citations 为列表。"""
    env = {**os.environ, "PYTHONPATH": os.path.pathsep.join([str(SRC), str(PROJECT_ROOT)])}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None
    # initialize
    proc.stdin.write('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
    proc.stdin.flush()
    _ = proc.stdout.readline()
    # tools/call query_knowledge_hub
    proc.stdin.write(
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"query_knowledge_hub","arguments":{"query":"测试查询"}}}\n'
    )
    proc.stdin.flush()
    proc.stdin.close()
    out_line = proc.stdout.readline()
    proc.wait(timeout=10)

    payload = json.loads(out_line.strip())
    assert payload.get("id") == 2
    assert "result" in payload, payload
    result = payload["result"]
    assert "content" in result
    assert len(result["content"]) >= 1
    assert result["content"][0].get("type") == "text"
    assert "text" in result["content"][0]
    assert "structuredContent" in result
    assert "citations" in result["structuredContent"]
    assert isinstance(result["structuredContent"]["citations"], list)


def test_image_content_in_tool_result(tmp_path: Path) -> None:
    """当检索结果含 image_refs 时，content 中包含 image type、mimeType 正确、data 为 base64。"""
    import base64

    from core.response.multimodal_assembler import assemble
    from core.response.response_builder import build
    from core.types import RetrievalResult

    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    img_dir = tmp_path / "data" / "images" / "coll"
    img_dir.mkdir(parents=True)
    (img_dir / "ref.png").write_bytes(png_bytes)

    results = [
        RetrievalResult(
            "c1",
            0.9,
            "Snippet.",
            {"images": [{"id": "i1", "path": "data/images/coll/ref.png"}]},
        ),
    ]
    response = build(results, "q")
    image_items = assemble(results, work_dir=str(tmp_path))
    response["content"].extend(image_items)

    assert any(c.get("type") == "image" for c in response["content"])
    img = next(c for c in response["content"] if c.get("type") == "image")
    assert img.get("mimeType") == "image/png"
    assert isinstance(img.get("data"), str)
    base64.b64decode(img["data"])
