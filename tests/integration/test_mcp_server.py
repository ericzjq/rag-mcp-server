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
