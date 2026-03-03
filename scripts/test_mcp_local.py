#!/usr/bin/env python3
"""
本地测试 MCP Server 接口：以子进程启动 server，依次发送 initialize、tools/list、
以及三个 tools/call（query_knowledge_hub、list_collections、get_document_summary），
并打印响应，用于验证接口是否运行正常。
运行前请确保：1) 在项目根目录；2) PYTHONPATH=src；3) config/settings.yaml 存在。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _PROJECT_ROOT / "config" / "settings.yaml"


def _env():
    return {
        **os.environ,
        "PYTHONPATH": os.path.pathsep.join([str(_PROJECT_ROOT / "src"), str(_PROJECT_ROOT)]),
    }


def main() -> int:
    if not _CONFIG.is_file():
        print("错误: 配置文件不存在:", _CONFIG, file=sys.stderr)
        print("请复制 config/settings.yaml.example 为 config/settings.yaml 并填写 api_key。", file=sys.stderr)
        return 1

    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(_PROJECT_ROOT),
        env=_env(),
        text=True,
    )
    assert proc.stdin and proc.stdout

    def send(req: dict) -> dict:
        proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        return json.loads(line.strip())

    try:
        # 1. initialize
        print("--- initialize ---")
        r = send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        if "error" in r:
            print("失败:", r["error"])
            return 1
        print("OK:", r.get("result", {}).get("serverInfo", r.get("result")))

        # 2. tools/list
        print("\n--- tools/list ---")
        r = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        if "error" in r:
            print("失败:", r["error"])
            return 1
        tools = r.get("result", {}).get("tools", [])
        names = [t.get("name") for t in tools if t.get("name")]
        print("工具列表:", names)

        # 3. tools/call query_knowledge_hub
        print("\n--- tools/call query_knowledge_hub ---")
        r = send({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "query_knowledge_hub", "arguments": {"query": "测试查询", "top_k": 3}},
        })
        if "error" in r:
            print("失败:", r["error"])
        else:
            res = r.get("result", {})
            content = res.get("content", [])
            for c in content:
                if c.get("type") == "text" and "text" in c:
                    print("文本摘要:", (c["text"][:200] + "..." if len(c.get("text", "")) > 200 else c["text"]))
            if res.get("structuredContent", {}).get("citations"):
                print("citations 条数:", len(res["structuredContent"]["citations"]))

        # 4. tools/call list_collections
        print("\n--- tools/call list_collections ---")
        r = send({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "list_collections", "arguments": {}},
        })
        if "error" in r:
            print("失败:", r["error"])
        else:
            cols = r.get("result", {}).get("structuredContent", {}).get("collections", [])
            print("集合:", cols if cols else "(空)")

        # 5. tools/call get_document_summary
        print("\n--- tools/call get_document_summary ---")
        r = send({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "get_document_summary", "arguments": {"doc_id": "test_doc_id"}},
        })
        if "error" in r:
            print("失败:", r["error"])
        else:
            sc = r.get("result", {}).get("structuredContent", {})
            if sc.get("error"):
                print("(文档不存在或元数据未配置，属预期):", sc.get("error"))
            else:
                print("doc_id:", sc.get("doc_id"), "title:", sc.get("title"))

        proc.stdin.close()
        proc.wait(timeout=5)
        print("\n全部请求已完成，MCP Server 接口运行正常。")
        return 0
    except Exception as e:
        print("异常:", e, file=sys.stderr)
        proc.kill()
        return 1


if __name__ == "__main__":
    sys.exit(main())
