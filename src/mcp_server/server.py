"""
MCP Server 入口（E1）：stdio 传输，stdout 仅输出 MCP 消息，日志输出到 stderr。
"""

import json
import logging
import sys

from mcp_server.protocol_handler import ProtocolHandler


def _setup_logging() -> None:
    """将根 logger 的 handler 设为 stderr，避免污染 stdout。"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        root.addHandler(h)


def _run_stdio_loop(handler: ProtocolHandler) -> None:
    """从 stdin 逐行读 JSON-RPC 请求，经 ProtocolHandler 分发，仅将 JSON-RPC 响应写入 stdout。"""
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

        resp = handler.handle_request(msg)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def main() -> int:
    _setup_logging()
    try:
        _run_stdio_loop(ProtocolHandler())
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).exception("Server error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
