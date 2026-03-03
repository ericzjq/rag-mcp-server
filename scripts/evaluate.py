#!/usr/bin/env python3
"""
评估脚本入口（H3）：读取 golden test set，跑 retrieval + evaluator，输出 metrics。
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.chdir(_ROOT)

# 确保 src 在 path 中
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.settings import load_settings
from core.query_engine.hybrid_search import HybridSearch
from libs.evaluator.evaluator_factory import create as create_evaluator
from observability.evaluation.eval_runner import EvalRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 golden test set 评估，输出 hit_rate、mrr 等")
    parser.add_argument(
        "--test-set",
        default=os.path.join(_ROOT, "tests", "fixtures", "golden_test_set.json"),
        help="Golden test set JSON 路径",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml"),
        help="配置文件路径",
    )
    parser.add_argument("--top-k", type=int, default=10, help="每条 query 检索条数")
    args = parser.parse_args()

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(_ROOT, config_path)
    if not os.path.isfile(config_path):
        print("ERROR: 配置文件不存在: %s" % config_path, file=sys.stderr)
        return 1

    settings = load_settings(config_path)
    hybrid_search = HybridSearch(settings)
    evaluator = create_evaluator(settings)
    runner = EvalRunner(settings, hybrid_search, evaluator)

    try:
        report = runner.run(args.test_set, top_k=args.top_k)
    except FileNotFoundError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    except Exception as e:
        print("ERROR: 评估失败: %s" % e, file=sys.stderr)
        return 1

    out = {
        "hit_rate": round(report.hit_rate, 4),
        "mrr": round(report.mrr, 4),
        "num_queries": len(report.query_results),
        "query_results": report.query_results,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
