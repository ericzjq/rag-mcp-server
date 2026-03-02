"""
Protocol Handler 单元测试（E2）：initialize、tools/list、tools/call、错误码规范。
"""

import pytest

from mcp_server.protocol_handler import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    ProtocolError,
    ProtocolHandler,
)


def test_handle_initialize_returns_server_info_and_capabilities() -> None:
    h = ProtocolHandler()
    out = h.handle_initialize({})
    assert out["protocolVersion"] == "2024-11-05"
    assert "capabilities" in out
    assert out["capabilities"].get("tools") is not None
    assert out["serverInfo"]["name"] == "mcp-server"
    assert out["serverInfo"]["version"] == "0.1.0"


def test_handle_tools_list_empty_when_no_tools() -> None:
    h = ProtocolHandler()
    out = h.handle_tools_list()
    assert out["tools"] == []


def test_handle_tools_list_returns_registered_schemas() -> None:
    h = ProtocolHandler()
    h.register_tool(
        "echo",
        "Echo back input",
        {"type": "object", "properties": {"x": {"type": "string"}}},
        lambda x: x,
    )
    out = h.handle_tools_list()
    assert len(out["tools"]) == 1
    assert out["tools"][0]["name"] == "echo"
    assert out["tools"][0]["description"] == "Echo back input"
    assert out["tools"][0]["inputSchema"]["type"] == "object"


def test_handle_tools_call_invokes_handler() -> None:
    h = ProtocolHandler()
    h.register_tool("add", "Add two numbers", {"type": "object"}, lambda a, b: a + b)
    out = h.handle_tools_call("add", {"a": 1, "b": 2})
    assert out["content"] == [3]


def test_handle_tools_call_unknown_tool_raises_method_not_found() -> None:
    h = ProtocolHandler()
    with pytest.raises(ProtocolError) as exc_info:
        h.handle_tools_call("nonexistent", {})
    assert exc_info.value.code == METHOD_NOT_FOUND


def test_handle_tools_call_type_error_raises_invalid_params() -> None:
    h = ProtocolHandler()
    h.register_tool("add", "Add", {"type": "object"}, lambda a, b: a + b)
    with pytest.raises(ProtocolError) as exc_info:
        h.handle_tools_call("add", {"a": 1})  # missing b
    assert exc_info.value.code == INVALID_PARAMS


def test_handle_tools_call_internal_exception_raises_internal_error() -> None:
    h = ProtocolHandler()

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret detail")

    h.register_tool("fail", "Fails", {"type": "object"}, fail)
    with pytest.raises(ProtocolError) as exc_info:
        h.handle_tools_call("fail", {})
    assert exc_info.value.code == INTERNAL_ERROR
    assert "Internal error" in exc_info.value.message
    assert "secret" not in exc_info.value.message


def test_handle_request_initialize() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "mcp-server"


def test_handle_request_tools_list() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert resp["id"] == 2
    assert resp["result"]["tools"] == []


def test_handle_request_tools_call_success() -> None:
    h = ProtocolHandler()
    h.register_tool("id", "Identity", {"type": "object"}, lambda x: x)
    resp = h.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "id", "arguments": {"x": "hello"}},
    })
    assert resp["result"]["content"] == ["hello"]


def test_handle_request_tools_call_missing_name_returns_invalid_params() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"arguments": {}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == INVALID_PARAMS


def test_handle_request_tools_call_arguments_not_object_returns_invalid_params() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "x", "arguments": "not-a-dict"},
    })
    assert resp["error"]["code"] == INVALID_PARAMS


def test_handle_request_method_not_found() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({"jsonrpc": "2.0", "id": 6, "method": "unknown/method", "params": {}})
    assert resp["error"]["code"] == METHOD_NOT_FOUND


def test_handle_request_invalid_request_no_jsonrpc() -> None:
    h = ProtocolHandler()
    resp = h.handle_request({"id": 7, "method": "initialize", "params": {}})
    assert resp["error"]["code"] == INVALID_REQUEST
