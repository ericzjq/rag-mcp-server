#!/usr/bin/env python3
"""
查询脚本入口（D7）：HybridSearch + Reranker，输出格式化的 Top-K 检索结果。
"""

import argparse
import logging
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
_SRC = os.path.join(_ROOT, "src")
for _p in (_SRC, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.settings import load_settings
from core.query_engine.hybrid_search import HybridSearch
from core.query_engine.reranker import Reranker


def main() -> int:
    parser = argparse.ArgumentParser(description="混合检索：HybridSearch + 可选 Reranker")
    parser.add_argument("--query", required=True, help="查询文本")
    parser.add_argument("--top-k", type=int, default=10, help="返回条数（默认 10）")
    parser.add_argument("--collection", default="", help="限定检索集合（metadata 过滤）")
    parser.add_argument("--verbose", action="store_true", help="显示各阶段信息")
    parser.add_argument("--no-rerank", action="store_true", help="跳过 Reranker 精排")
    parser.add_argument(
        "--config",
        default=os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml"),
        help="配置文件路径",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="工作目录（data/db、chroma 等相对此目录）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    work_dir = args.work_dir or _ROOT
    os.chdir(work_dir)

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(work_dir, config_path)
    if not os.path.exists(config_path):
        logger.error("配置文件不存在: %s", config_path)
        return 1

    settings = load_settings(config_path)
    hybrid = HybridSearch(settings)
    reranker = Reranker(settings)

    filters = None
    if args.collection:
        filters = {"collection": args.collection}

    try:
        results = hybrid.search(args.query, top_k=args.top_k, filters=filters)
    except Exception as e:
        logger.exception("检索失败: %s", e)
        return 1

    if not results:
        print("未找到相关文档，请先运行 ingest.py 摄取数据。")
        return 0

    if not args.no_rerank:
        if args.verbose:
            logger.info("精排前候选数: %d", len(results))
        try:
            results = reranker.rerank(args.query, results)
        except Exception as e:
            logger.warning("Reranker 异常，使用融合结果: %s", e)
        if args.verbose:
            logger.info("精排后结果数: %d", len(results))

    print(f"共 {len(results)} 条结果：\n")
    for i, r in enumerate(results, 1):
        source = r.metadata.get("source_path", "")
        page = r.metadata.get("page", r.metadata.get("page_num", ""))
        summary = (r.text or "")[:200] + ("..." if len(r.text or "") > 200 else "")
        fallback = " [rerank_fallback]" if r.metadata.get("rerank_fallback") else ""
        print(f"  {i}. score={r.score:.4f}{fallback}")
        print(f"     {summary}")
        if source or page != "":
            print(f"     来源: {source}" + (f" 页码: {page}" if page != "" else ""))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
