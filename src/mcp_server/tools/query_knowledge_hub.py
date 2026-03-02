"""
query_knowledge_hub Tool（E3）：混合检索 + Reranker，返回 Markdown + structured citations。
"""

import os
from typing import Any, Dict, Optional

from core.settings import load_settings
from core.query_engine.hybrid_search import HybridSearch
from core.query_engine.reranker import Reranker
from core.response.response_builder import build as build_response
from core.response.multimodal_assembler import assemble as assemble_images


def query_knowledge_hub(
    query: str,
    top_k: int = 10,
    collection: str = "",
    *,
    config_path: Optional[str] = None,
    work_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tool 入口：执行 HybridSearch + Reranker，构建带引用的 MCP 响应。
    config_path / work_dir 用于测试或覆盖默认；默认从 MCP_CONFIG_PATH 与 cwd 读取。
    """
    base = work_dir or os.getcwd()
    path = config_path or os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml")
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    if not os.path.exists(path):
        return build_response([], query)

    settings = load_settings(path)
    hybrid = HybridSearch(settings)
    reranker = Reranker(settings)

    filters = None
    if collection:
        filters = {"collection": collection}

    results = hybrid.search(query, top_k=top_k, filters=filters)
    if results:
        results = reranker.rerank(query, results)
    response = build_response(results, query)
    image_items = assemble_images(results, work_dir=base)
    if image_items:
        response["content"].extend(image_items)
    return response


# 供 ProtocolHandler 注册用的 schema
QUERY_KNOWLEDGE_HUB_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "查询文本"},
        "top_k": {"type": "integer", "description": "返回条数", "default": 10},
        "collection": {"type": "string", "description": "限定检索集合", "default": ""},
    },
    "required": ["query"],
}
