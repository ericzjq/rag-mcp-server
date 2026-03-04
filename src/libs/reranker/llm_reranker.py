"""
LLM Reranker：使用 LLM 对候选进行精排，输出严格为 ranked ids；失败时回退为原序。
"""

import json
import re
import time
from pathlib import Path
from typing import Any, List, Optional

from core.settings import Settings

from libs.reranker.base_reranker import BaseReranker, RerankCandidate

DEFAULT_PROMPT_PATH = "config/prompts/rerank.txt"


def _default_prompt_path(settings: Settings) -> Path:
    """默认 prompt 路径（相对于项目根，调用方需保证 cwd 或传绝对路径）。"""
    return Path(DEFAULT_PROMPT_PATH)


def _load_prompt(path: Path) -> str:
    """读取 prompt 模板内容。"""
    if not path.exists():
        raise FileNotFoundError(f"Rerank prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _format_prompt(template: str, query: str, candidates: List[RerankCandidate]) -> str:
    """将 query 与 candidates 填入模板。占位符：{{query}}、{{candidates}}。"""
    # 候选列表格式化为 "id: text" 行
    lines = []
    for c in candidates:
        cid = c.get("id", "")
        text = (c.get("text") or c.get("metadata", {}).get("text") or "")[:500]
        lines.append(f"{cid}: {text}")
    candidates_blob = "\n".join(lines)
    return (
        template.replace("{{query}}", query)
        .replace("{{candidates}}", candidates_blob)
    )


def _parse_ranked_ids(response: str) -> List[str]:
    """从 LLM 响应中解析 ranked id 列表（JSON array）。不满足 schema 时抛出 ValueError。"""
    response = response.strip()
    # 允许响应中包含 markdown 代码块或前后文字，提取 [...] 或 JSON
    match = re.search(r"\[[\s\S]*?\]", response)
    if match:
        try:
            ids = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM Reranker: 响应非合法 JSON 数组 — {e}") from e
    else:
        try:
            ids = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM Reranker: 未找到 ranked ids 数组，且整体非 JSON — {e}") from e
    if not isinstance(ids, list):
        raise ValueError("LLM Reranker: 输出必须为 JSON 数组，当前为 " + type(ids).__name__)
    for i, x in enumerate(ids):
        if not isinstance(x, str):
            raise ValueError(f"LLM Reranker: 数组元素必须为 str，第 {i} 项为 {type(x).__name__}")
    return ids


class LLMReranker(BaseReranker):
    """使用 LLM 对候选精排，输出严格为 ranked ids；解析失败抛可读错误，LLM 异常时回退原序。"""

    def __init__(
        self,
        settings: Settings,
        *,
        prompt_path: Optional[Path] = None,
        prompt_text: Optional[str] = None,
        llm_client: Optional[Any] = None,
    ) -> None:
        self._settings = settings
        self._prompt_path = prompt_path
        self._prompt_text = prompt_text
        self._llm = llm_client
        self._resolved_prompt: Optional[str] = None

    def _get_prompt_template(self) -> str:
        if self._prompt_text is not None:
            return self._prompt_text
        if self._resolved_prompt is not None:
            return self._resolved_prompt
        path = self._prompt_path or _default_prompt_path(self._settings)
        self._resolved_prompt = _load_prompt(path)
        return self._resolved_prompt

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from libs.llm.llm_factory import create as create_llm
        return create_llm(self._settings)

    def rerank(
        self,
        query: str,
        candidates: List[RerankCandidate],
        trace: Optional[Any] = None,
    ) -> List[RerankCandidate]:
        if not candidates:
            return []
        try:
            t0 = time.perf_counter()
            template = self._get_prompt_template()
            prompt = _format_prompt(template, query, candidates)
            t1 = time.perf_counter()
            llm = self._get_llm()
            response = llm.chat([{"role": "user", "content": prompt}])
            t2 = time.perf_counter()
            if trace is not None:
                trace.record_stage("rerank_breakdown", {
                    "prompt_ms": round((t1 - t0) * 1000, 2),
                    "llm_call_ms": round((t2 - t1) * 1000, 2),
                })
            ranked_ids = _parse_ranked_ids(response)
        except (FileNotFoundError, ValueError):
            raise
        except Exception:
            # 可回退：LLM 异常时返回原序
            return list(candidates)
        # 按 ranked_ids 重排，仅保留在 candidates 中存在的 id；未出现在 ranked_ids 的候选追加到末尾
        id_to_candidate = {c["id"]: c for c in candidates}
        ordered: List[RerankCandidate] = []
        seen = set()
        for cid in ranked_ids:
            if cid in id_to_candidate and cid not in seen:
                ordered.append(id_to_candidate[cid])
                seen.add(cid)
        for c in candidates:
            if c["id"] not in seen:
                ordered.append(c)
        return ordered
