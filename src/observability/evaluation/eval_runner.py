"""
EvalRunner（H3）：读取 golden test set JSON，跑 retrieval，产出 EvalReport（hit_rate、mrr、各 query 详情）。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.query_engine.hybrid_search import HybridSearch
from core.settings import Settings

from libs.evaluator.base_evaluator import BaseEvaluator


def _hit_rate_one(retrieved_ids: List[str], golden_ids: List[str]) -> float:
    """单条：是否命中任一 golden。"""
    if not golden_ids:
        return 0.0
    return 1.0 if any(rid in golden_ids for rid in retrieved_ids) else 0.0


def _mrr_one(retrieved_ids: List[str], golden_ids: List[str]) -> float:
    """单条：首位命中的倒数排名。"""
    if not golden_ids:
        return 0.0
    for i, rid in enumerate(retrieved_ids):
        if rid in golden_ids:
            return 1.0 / (i + 1)
    return 0.0


@dataclass
class EvalReport:
    """评估报告：汇总 hit_rate、mrr 与各 query 结果详情。"""
    hit_rate: float
    mrr: float
    query_results: List[Dict[str, Any]] = field(default_factory=list)


class EvalRunner:
    """读取 golden test set，对每条 query 执行 retrieval + evaluator，汇总为 EvalReport。"""

    def __init__(
        self,
        settings: Settings,
        hybrid_search: HybridSearch,
        evaluator: BaseEvaluator,
    ) -> None:
        self._settings = settings
        self._hybrid_search = hybrid_search
        self._evaluator = evaluator

    def run(self, test_set_path: str, top_k: int = 10) -> EvalReport:
        """
        加载 test_set_path（JSON），对每个 test_case 执行检索与评估，返回 EvalReport。

        Args:
            test_set_path: 指向含 test_cases 的 JSON 文件路径。
            top_k: 每条 query 检索条数。

        Returns:
            EvalReport，含 hit_rate、mrr（均值）与 query_results 详情。
        """
        path = Path(test_set_path)
        if not path.is_file():
            raise FileNotFoundError("Golden test set 不存在: %s" % test_set_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        test_cases = data.get("test_cases") or []
        if not test_cases:
            return EvalReport(hit_rate=0.0, mrr=0.0, query_results=[])

        query_results: List[Dict[str, Any]] = []
        hit_rates: List[float] = []
        mrrs: List[float] = []

        for case in test_cases:
            query = (case.get("query") or "").strip()
            expected_chunk_ids = list(case.get("expected_chunk_ids") or [])
            expected_sources = case.get("expected_sources") or []

            if not query:
                continue
            results = self._hybrid_search.search(query, top_k=top_k, filters=None, trace=None)
            retrieved_ids = [r.chunk_id for r in results]
            hit = _hit_rate_one(retrieved_ids, expected_chunk_ids)
            mrr = _mrr_one(retrieved_ids, expected_chunk_ids)
            hit_rates.append(hit)
            mrrs.append(mrr)
            try:
                metrics = self._evaluator.evaluate(
                    query, retrieved_ids, expected_chunk_ids, trace=None
                )
            except Exception:
                metrics = {}
            query_results.append({
                "query": query,
                "retrieved_ids": retrieved_ids,
                "expected_chunk_ids": expected_chunk_ids,
                "expected_sources": expected_sources,
                "hit_rate": hit,
                "mrr": mrr,
                "metrics": metrics,
            })

        n = len(hit_rates)
        hit_rate = sum(hit_rates) / n if n else 0.0
        mrr = sum(mrrs) / n if n else 0.0
        return EvalReport(hit_rate=hit_rate, mrr=mrr, query_results=query_results)


def save_report(report: EvalReport, path: str) -> None:
    """将 EvalReport 序列化为 JSON 写入文件，供 Dashboard RAGAS 结果页等加载。"""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(path_obj, "w", encoding="utf-8") as f:
        json.dump(
            {"hit_rate": report.hit_rate, "mrr": report.mrr, "query_results": report.query_results},
            f,
            ensure_ascii=False,
            indent=2,
        )


def load_report(path: str) -> EvalReport:
    """从 JSON 文件加载 EvalReport。"""
    path_obj = Path(path)
    if not path_obj.is_file():
        raise FileNotFoundError("评估报告文件不存在: %s" % path)
    with open(path_obj, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalReport(
        hit_rate=float(data.get("hit_rate", 0)),
        mrr=float(data.get("mrr", 0)),
        query_results=list(data.get("query_results") or []),
    )
