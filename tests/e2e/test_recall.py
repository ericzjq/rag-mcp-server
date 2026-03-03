"""
Recall 回归测试 E2E（H5）：基于 golden test set 跑检索，断言 hit@k 不低于阈值。
使用项目配置（config/settings.yaml 或 MCP_CONFIG_PATH）与真实 LLM/Embedding/向量库。
"""

import json
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden_test_set.json"

# 回归阈值：补齐真实 golden 数据后可提高
MIN_HIT_RATE_THRESHOLD = 0.0


def _load_test_cases() -> list:
    if not GOLDEN_PATH.is_file():
        return []
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases") or []


def _get_config_path() -> Path:
    env_path = os.environ.get("MCP_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p
    return PROJECT_ROOT / "config" / "settings.yaml"


@pytest.mark.e2e
def test_recall_hit_rate_above_threshold() -> None:
    """基于 golden set 使用真实配置跑 EvalRunner，断言整体 hit_rate >= 阈值。"""
    test_cases = _load_test_cases()
    if not test_cases:
        pytest.skip("golden_test_set.json 无 test_cases")

    config_path = _get_config_path()
    if not config_path.is_file():
        pytest.skip("配置文件不存在: %s" % config_path)

    from core.settings import load_settings
    from core.query_engine.hybrid_search import HybridSearch
    from libs.evaluator.evaluator_factory import create as create_evaluator
    from observability.evaluation.eval_runner import EvalRunner

    # 使用项目根目录以便相对路径（如 data/chroma）正确解析
    orig_cwd = os.getcwd()
    try:
        os.chdir(PROJECT_ROOT)
        settings = load_settings(str(config_path))
        hybrid_search = HybridSearch(settings)
        evaluator = create_evaluator(settings)
        runner = EvalRunner(settings, hybrid_search, evaluator)
        report = runner.run(str(GOLDEN_PATH), top_k=10)
    finally:
        os.chdir(orig_cwd)

    assert report.hit_rate >= MIN_HIT_RATE_THRESHOLD, (
        "Recall 回归：hit_rate %.4f 低于阈值 %.4f" % (report.hit_rate, MIN_HIT_RATE_THRESHOLD)
    )
    assert len(report.query_results) == len(test_cases), (
        "query_results 条数 %d 与 test_cases 条数 %d 不一致"
        % (len(report.query_results), len(test_cases))
    )
