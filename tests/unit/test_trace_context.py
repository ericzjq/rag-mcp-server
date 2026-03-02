"""
TraceContext / TraceCollector 单元测试（F1）：finish、elapsed_ms、to_dict、collect。
"""

import json
import time
from unittest.mock import Mock

import pytest

from core.trace.trace_context import TraceContext
from core.trace.trace_collector import TraceCollector


def test_trace_context_has_trace_id_and_type() -> None:
    ctx = TraceContext(trace_type="query")
    assert ctx.trace_id
    assert ctx.trace_type == "query"

    ctx2 = TraceContext(trace_type="ingestion")
    assert ctx2.trace_type == "ingestion"


def test_record_stage_appends_stage_data() -> None:
    ctx = TraceContext()
    ctx.record_stage("load", {"document_id": "doc1"})
    ctx.record_stage("split", {"chunks_count": 3})
    assert ctx.get_stage("load") == {"document_id": "doc1"}
    assert ctx.get_stage("split") == {"chunks_count": 3}


def test_finish_sets_total_elapsed_ms() -> None:
    ctx = TraceContext()
    time.sleep(0.01)
    ctx.finish()
    assert ctx.elapsed_ms() >= 1.0
    ctx.finish()  # idempotent
    assert ctx.elapsed_ms() >= 1.0


def test_elapsed_ms_stage_returns_from_stage_data() -> None:
    ctx = TraceContext()
    ctx.record_stage("dense", {"elapsed_ms": 12.5})
    assert ctx.elapsed_ms("dense") == 12.5
    assert ctx.elapsed_ms("missing") == 0.0


def test_to_dict_contains_required_fields() -> None:
    ctx = TraceContext(trace_type="query")
    ctx.record_stage("a", {"x": 1})
    ctx.finish()
    d = ctx.to_dict()
    assert "trace_id" in d
    assert d["trace_type"] == "query"
    assert "started_at" in d
    assert "finished_at" in d
    assert "total_elapsed_ms" in d
    assert d["stages"] == {"a": {"x": 1}}
    json.dumps(d)


def test_to_dict_before_finish_has_finished_at_none() -> None:
    ctx = TraceContext()
    d = ctx.to_dict()
    assert d["finished_at"] is None
    assert d["total_elapsed_ms"] == 0.0


def test_trace_collector_calls_writer_on_collect() -> None:
    writer = Mock()
    collector = TraceCollector(writer=writer)
    ctx = TraceContext(trace_type="ingestion")
    ctx.record_stage("load", {})
    ctx.finish()
    collector.collect(ctx)
    writer.assert_called_once()
    payload = writer.call_args[0][0]
    assert payload["trace_type"] == "ingestion"
    assert "trace_id" in payload
