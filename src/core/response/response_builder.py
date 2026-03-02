"""
ResponseBuilder（E3）：从检索结果构建 MCP 格式响应（Markdown + structuredContent.citations）。
"""

from typing import Any, Dict, List

from core.types import RetrievalResult

from core.response.citation_generator import generate as generate_citations


def build(retrieval_results: List[RetrievalResult], query: str) -> Dict[str, Any]:
    """
    构建 MCP 格式响应：content[0] 为可读 Markdown（含 [1]、[2] 等引用），structuredContent.citations 为引用列表。
    无结果时 content[0] 为友好提示，citations 为空。
    """
    citations = generate_citations(retrieval_results)
    if not retrieval_results:
        return {
            "content": [
                {"type": "text", "text": "未找到相关文档，请先运行 ingest 摄取数据或调整查询。"},
            ],
            "structuredContent": {"citations": []},
        }
    parts = []
    for i, r in enumerate(retrieval_results, 1):
        snippet = (r.text or "").strip()[:300]
        if len((r.text or "").strip()) > 300:
            snippet += "..."
        parts.append(f"[{i}] {snippet}")
    markdown = "\n\n".join(parts)
    return {
        "content": [
            {"type": "text", "text": markdown},
        ],
        "structuredContent": {"citations": citations},
    }
