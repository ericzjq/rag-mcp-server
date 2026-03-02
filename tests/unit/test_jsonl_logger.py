"""
JSON Lines logger 单元测试（F2）：JSONFormatter、write_trace 持久化、一行合法 JSON 含 trace_type。
"""

import json
from pathlib import Path

import pytest

from observability.logger import JSONFormatter, get_trace_logger, write_trace


def test_json_formatter_outputs_valid_json() -> None:
    import logging
    fmt = JSONFormatter()
    record = logging.LogRecord("x", 20, "", 0, "hello", (), None)
    line = fmt.format(record)
    parsed = json.loads(line)
    assert parsed["message"] == "hello"
    assert "level" in parsed
    assert "name" in parsed


def test_write_trace_appends_one_json_line_with_trace_type(tmp_path: Path) -> None:
    path = str(tmp_path / "traces.jsonl")
    trace_dict = {"trace_id": "t1", "trace_type": "query", "total_elapsed_ms": 10.5}
    write_trace(trace_dict, path=path)
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline()
    parsed = json.loads(line)
    assert parsed["trace_type"] == "query"
    assert parsed["trace_id"] == "t1"

    write_trace({"trace_type": "ingestion", "trace_id": "t2"}, path=path)
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["trace_type"] == "ingestion"


def test_get_trace_logger_returns_logger_with_json_format() -> None:
    logger = get_trace_logger("test.trace.f2")
    assert logger.name == "test.trace.f2"
    assert any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers)
