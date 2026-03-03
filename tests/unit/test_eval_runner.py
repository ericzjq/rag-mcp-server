"""
EvalRunner 单元测试（H3）：mock hybrid_search 与 evaluator，验证 run 产出 EvalReport。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.settings import Settings
from observability.evaluation.eval_runner import EvalRunner, EvalReport


def test_eval_runner_run_returns_report_with_hit_rate_mrr(tmp_path: Path) -> None:
    """run 读取 golden JSON，调用 hybrid_search + evaluator，返回含 hit_rate、mrr、query_results 的 EvalReport。"""
    golden = tmp_path / "golden.json"
    golden.write_text(
        json.dumps({
            "test_cases": [
                {"query": "q1", "expected_chunk_ids": ["a", "b"], "expected_sources": []},
                {"query": "q2", "expected_chunk_ids": ["c"], "expected_sources": []},
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    # Mock: search 返回固定 chunk_id 列表
    mock_result = MagicMock()
    mock_result.chunk_id = "a"
    hybrid_search = MagicMock()
    hybrid_search.search.return_value = [mock_result]
    evaluator = MagicMock()
    evaluator.evaluate.return_value = {"hit_rate": 1.0, "mrr": 1.0}

    settings = MagicMock(spec=Settings)
    runner = EvalRunner(settings, hybrid_search, evaluator)
    report = runner.run(str(golden), top_k=5)

    assert isinstance(report, EvalReport)
    assert report.hit_rate >= 0.0 and report.mrr >= 0.0
    assert len(report.query_results) == 2
    assert report.query_results[0]["query"] == "q1"
    assert "retrieved_ids" in report.query_results[0]
    assert "expected_chunk_ids" in report.query_results[0]
    assert "hit_rate" in report.query_results[0]
    assert "mrr" in report.query_results[0]


def test_eval_runner_run_missing_file_raises() -> None:
    """test_set_path 不存在时 run 抛出 FileNotFoundError。"""
    settings = MagicMock(spec=Settings)
    runner = EvalRunner(settings, MagicMock(), MagicMock())
    with pytest.raises(FileNotFoundError) as exc_info:
        runner.run("/nonexistent/golden.json")
    assert "不存在" in str(exc_info.value) or "golden" in str(exc_info.value).lower()


def test_eval_runner_run_empty_test_cases_returns_zero_report(tmp_path: Path) -> None:
    """test_cases 为空时返回 hit_rate=0, mrr=0, query_results=[]。"""
    golden = tmp_path / "empty.json"
    golden.write_text(json.dumps({"test_cases": []}, ensure_ascii=False), encoding="utf-8")
    settings = MagicMock(spec=Settings)
    runner = EvalRunner(settings, MagicMock(), MagicMock())
    report = runner.run(str(golden))
    assert report.hit_rate == 0.0
    assert report.mrr == 0.0
    assert report.query_results == []
