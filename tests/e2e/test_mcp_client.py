"""
E2E：MCP Client 侧调用模拟（I1）。以子进程启动 server，模拟 tools/list + tools/call，
完整走通 query_knowledge_hub 并校验返回 citations。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def _env() -> dict:
    return {
        **os.environ,
        "PYTHONPATH": os.path.pathsep.join([str(SRC), str(PROJECT_ROOT)]),
    }


@pytest.mark.e2e
def test_mcp_client_tools_list_and_query_knowledge_hub_returns_citations() -> None:
    """子进程启动 server → initialize → tools/list → tools/call query_knowledge_hub，断言返回 citations。"""
    if not CONFIG_PATH.is_file():
        pytest.skip("配置文件不存在: %s" % CONFIG_PATH)

    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
        env=_env(),
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None

    # initialize
    proc.stdin.write('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
    proc.stdin.flush()
    init_line = proc.stdout.readline()
    init_payload = json.loads(init_line.strip())
    assert init_payload.get("result") is not None, init_payload
    assert "serverInfo" in init_payload["result"]

    # tools/list
    proc.stdin.write('{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n')
    proc.stdin.flush()
    list_line = proc.stdout.readline()
    list_payload = json.loads(list_line.strip())
    assert list_payload.get("result") is not None, list_payload
    tools = list_payload["result"].get("tools") or []
    names = [t.get("name") for t in tools if t.get("name")]
    assert "query_knowledge_hub" in names

    # tools/call query_knowledge_hub
    proc.stdin.write(
        '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":'
        '{"name":"query_knowledge_hub","arguments":{"query":"测试查询"}}}\n'
    )
    proc.stdin.flush()
    proc.stdin.close()

    call_line = proc.stdout.readline()
    proc.wait(timeout=30)

    payload = json.loads(call_line.strip())
    assert payload.get("id") == 3
    if "error" in payload:
        pytest.fail("tools/call 返回错误: %s" % payload["error"])
    assert "result" in payload, payload
    result = payload["result"]
    assert "content" in result
    assert len(result["content"]) >= 1
    assert result["content"][0].get("type") == "text"
    assert "text" in result["content"][0]
    assert "structuredContent" in result
    assert "citations" in result["structuredContent"]
    assert isinstance(result["structuredContent"]["citations"], list), "citations 应为列表"
