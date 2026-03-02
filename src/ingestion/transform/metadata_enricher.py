"""
MetadataEnricher（C6）：规则增强 title/summary/tags + 可选 LLM 增强；LLM 失败回退规则，不阻塞。
"""

import json
import logging
import re
from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk

from ingestion.transform.base_transform import BaseTransform

logger = logging.getLogger(__name__)

# 规则兜底：title/summary/tags 至少非空
TITLE_MAX = 80
SUMMARY_MAX = 200


def _rule_title(text: str) -> str:
    """规则 title：首行或前 N 字。"""
    s = (text or "").strip()
    if not s:
        return "(no title)"
    first_line = s.split("\n")[0].strip()
    if len(first_line) > TITLE_MAX:
        return first_line[: TITLE_MAX - 1] + "…"
    return first_line or "(no title)"


def _rule_summary(text: str) -> str:
    """规则 summary：前 SUMMARY_MAX 字。"""
    s = (text or "").strip().replace("\n", " ")
    if not s:
        return "(no summary)"
    if len(s) > SUMMARY_MAX:
        return s[: SUMMARY_MAX - 1] + "…"
    return s


def _rule_tags(text: str) -> List[str]:
    """规则 tags：简单启发式（如首行 # 或空列表）。"""
    s = (text or "").strip()
    if not s:
        return []
    # 可选：提取 #tag 或首行关键词，此处返回空列表作为兜底
    tags: List[str] = []
    for m in re.finditer(r"#(\w+)", s):
        tags.append(m.group(1))
        if len(tags) >= 5:
            break
    return tags if tags else ["chunk"]


class MetadataEnricher(BaseTransform):
    """为 Chunk 补充 metadata：title、summary、tags；规则兜底 + 可选 LLM 增强，失败不阻塞。"""

    def __init__(
        self,
        settings: Settings,
        *,
        use_llm: bool = False,
        llm_client: Optional[Any] = None,
    ) -> None:
        self._settings = settings
        self._use_llm = use_llm
        self._llm = llm_client

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from libs.llm.llm_factory import create as create_llm
        return create_llm(self._settings)

    def _llm_enrich(self, text: str, trace: Optional[Any] = None) -> Optional[dict]:
        """调用 LLM 生成 title/summary/tags；失败返回 None。期望 JSON：{title, summary, tags[]}。"""
        if not (text or "").strip():
            return None
        try:
            prompt = (
                "Based on the following text chunk, output a JSON object with exactly three keys: "
                '"title" (string, short), "summary" (string, 1-2 sentences), "tags" (array of strings). '
                "Output only the JSON, no markdown.\n\n" + (text or "")[:3000]
            )
            llm = self._get_llm()
            out = llm.chat([{"role": "user", "content": prompt}])
            raw = (out or "").strip()
            # 允许被 markdown 代码块包裹
            if "```" in raw:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
                if m:
                    raw = m.group(1).strip()
            data = json.loads(raw)
            title = str(data.get("title", "")).strip() or _rule_title(text)
            summary = str(data.get("summary", "")).strip() or _rule_summary(text)
            tags = data.get("tags")
            if not isinstance(tags, list):
                tags = _rule_tags(text)
            tags = [str(t).strip() for t in tags if str(t).strip()][:10]
            return {"title": title, "summary": summary, "tags": tags}
        except Exception as e:
            logger.warning("MetadataEnricher LLM 调用失败: %s", e)
            return None

    def transform(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[Chunk]:
        result: List[Chunk] = []
        for c in chunks:
            try:
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                title = _rule_title(c.text)
                summary = _rule_summary(c.text)
                tags = _rule_tags(c.text)
                if self._use_llm:
                    llm_out = self._llm_enrich(c.text, trace)
                    if llm_out is not None:
                        title = llm_out.get("title", title)
                        summary = llm_out.get("summary", summary)
                        tags = llm_out.get("tags", tags)
                        meta["enriched_by"] = "llm"
                    else:
                        meta["enriched_by"] = "rule"
                        meta["enrichment_fallback"] = "llm_failed"
                else:
                    meta["enriched_by"] = "rule"
                meta["title"] = title
                meta["summary"] = summary
                meta["tags"] = tags
                result.append(
                    Chunk(
                        id=c.id,
                        text=c.text,
                        metadata=meta,
                        start_offset=c.start_offset,
                        end_offset=c.end_offset,
                        source_ref=c.source_ref,
                    )
                )
            except Exception as e:
                logger.warning("MetadataEnricher 单条异常，保留原文: id=%s %s", c.id, e)
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                meta["title"] = _rule_title(c.text)
                meta["summary"] = _rule_summary(c.text)
                meta["tags"] = _rule_tags(c.text)
                meta["enriched_by"] = "rule"
                meta["enrichment_fallback"] = str(e)
                result.append(
                    Chunk(
                        id=c.id,
                        text=c.text,
                        metadata=meta,
                        start_offset=c.start_offset,
                        end_offset=c.end_offset,
                        source_ref=c.source_ref,
                    )
                )
        return result
