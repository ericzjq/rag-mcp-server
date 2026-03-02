"""
MCP Server 入口（E1）：stdio 传输，stdout 仅输出 MCP 消息，日志输出到 stderr。
"""

import json
import logging
import sys


def _setup_logging() -> None:
    """将根 logger 的 handler 设为 stderr，避免污染 stdout。"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        root.addHandler(h)


def _handle_initialize(params: dict) -> dict:
    """处理 initialize：返回 serverInfo 与 capabilities（E2 将迁至 ProtocolHandler）。"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "mcp-server",
            "version": "0.1.0",
        },
    }


def _run_stdio_loop() -> None:
    """从 stdin 逐行读 JSON-RPC 请求，仅将 JSON-RPC 响应写入 stdout。"""
    logger = logging.getLogger(__name__)
    logger.info("MCP server started (stdio)")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON: %s", e)
            err = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
            continue

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if method == "initialize":
            result = _handle_initialize(params)
            resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"},
            }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def main() -> int:
    _setup_logging()
    try:
        _run_stdio_loop()
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).exception("Server error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
