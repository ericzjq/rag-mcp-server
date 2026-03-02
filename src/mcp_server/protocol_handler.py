"""
Protocol Handler（E2）：JSON-RPC 2.0 协议解析，initialize、tools/list、tools/call，规范错误码。
"""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# JSON-RPC 2.0 错误码
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ProtocolHandler:
    """封装 MCP 核心方法：initialize、tools/list、tools/call，错误转换为 JSON-RPC error。"""

    def __init__(
        self,
        *,
        server_name: str = "mcp-server",
        server_version: str = "0.1.0",
        protocol_version: str = "2024-11-05",
    ) -> None:
        self._server_name = server_name
        self._server_version = server_version
        self._protocol_version = protocol_version
        self._tools: List[Dict[str, Any]] = []
        self._tool_handlers: Dict[str, Callable[..., Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """注册一个 tool：schema 用于 tools/list，handler 用于 tools/call。"""
        self._tools.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        })
        self._tool_handlers[name] = handler

    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 initialize：返回 serverInfo 与 capabilities（声明 capabilities.tools）。"""
        return {
            "protocolVersion": self._protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": self._server_name,
                "version": self._server_version,
            },
        }

    def handle_tools_list(self) -> Dict[str, Any]:
        """返回已注册 tools 的 schema 列表。"""
        return {"tools": list(self._tools)}

    def handle_tools_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """路由到已注册的 tool 执行；异常转换为规范错误，不泄露堆栈。"""
        if name not in self._tool_handlers:
            raise ProtocolError(METHOD_NOT_FOUND, "Tool not found")
        try:
            result = self._tool_handlers[name](**arguments)
            if isinstance(result, dict) and "content" in result:
                return result
            return {"content": result if isinstance(result, list) else [result]}
        except TypeError as e:
            raise ProtocolError(INVALID_PARAMS, str(e))
        except Exception as e:
            logger.exception("Tool %s failed", name)
            raise ProtocolError(INTERNAL_ERROR, "Internal error")

    def handle_request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据 method 分发到 initialize / tools/list / tools/call，返回 JSON-RPC 响应体（含 id/result 或 id/error）。
        无效方法、参数错误、内部异常均转为规范 error，不泄露堆栈。
        """
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if not isinstance(msg.get("jsonrpc"), str) or msg.get("jsonrpc") != "2.0":
            return _error_response(req_id, INVALID_REQUEST, "Invalid Request")

        if method == "initialize":
            result = self.handle_initialize(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        if method == "tools/list":
            result = self.handle_tools_list()
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        if method == "tools/call":
            name = params.get("name") if isinstance(params, dict) else None
            arguments = params.get("arguments") if isinstance(params, dict) else {}
            if not name or not isinstance(name, str):
                return _error_response(req_id, INVALID_PARAMS, "Invalid params: name required")
            if not isinstance(arguments, dict):
                return _error_response(req_id, INVALID_PARAMS, "Invalid params: arguments must be object")
            try:
                result = self.handle_tools_call(name, arguments)
                return {"jsonrpc": "2.0", "id": req_id, "result": result}
            except ProtocolError as e:
                return _error_response(req_id, e.code, e.message)
        return _error_response(req_id, METHOD_NOT_FOUND, "Method not found")


class ProtocolError(Exception):
    """协议层错误，携带 JSON-RPC 错误码与消息。"""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
