"""
ChunkRefiner（C5）：规则去噪 + 可选 LLM 增强；LLM 失败时回退到规则结果，不阻塞。
"""

import logging
import re
from pathlib import Path
from typing import Any, List, Optional

from core.settings import Settings
from core.types import Chunk

from ingestion.transform.base_transform import BaseTransform

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = "config/prompts/chunk_refinement.txt"


def _rule_based_refine(text: str) -> str:
    """规则去噪：多余空白、页眉页脚模式、HTML 注释、常见分隔线；保留代码块与 Markdown 结构。"""
    if not text or not text.strip():
        return text
    s = text.strip()
    # 连续空白归一为单个空格（保留换行：先归一换行再空格）
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    # 常见页眉页脚： "— 1 —"、 "Page 1"、 "1/10"
    s = re.sub(r"—\s*\d+\s*—", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bPage\s+\d+\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d+\s*/\s*\d+\s*", "", s)
    # HTML 注释
    s = re.sub(r"<!--[\s\S]*?-->", "", s)
    # 仅由重复符号组成的行（分隔线）
    s = re.sub(r"(?m)^[-*_#=\s]{2,}\s*$", "", s)
    return s.strip() or text.strip()


def _load_prompt(prompt_path: Optional[Path] = None) -> str:
    """加载 prompt 模板，支持默认路径；缺省返回含 {text} 的占位模板。"""
    path = prompt_path or Path(DEFAULT_PROMPT_PATH)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "Refine the following chunk, preserve meaning and remove noise.\n\n{text}"


class ChunkRefiner(BaseTransform):
    """先规则去噪，再可选 LLM 增强；LLM 异常时回退规则结果并标记 metadata。"""

    def __init__(
        self,
        settings: Settings,
        *,
        use_llm: bool = True,
        llm_client: Optional[Any] = None,
        prompt_path: Optional[Path] = None,
    ) -> None:
        self._settings = settings
        self._use_llm = use_llm
        self._llm = llm_client
        self._prompt_path = prompt_path
        self._prompt_template: Optional[str] = None

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from libs.llm.llm_factory import create as create_llm
        return create_llm(self._settings)

    def _get_prompt_template(self) -> str:
        if self._prompt_template is None:
            self._prompt_template = _load_prompt(self._prompt_path)
        return self._prompt_template

    def _llm_refine(self, text: str, trace: Optional[Any] = None) -> Optional[str]:
        """可选 LLM 重写；失败返回 None。"""
        if not text.strip():
            return text
        try:
            template = self._get_prompt_template()
            prompt = template.replace("{text}", text)
            llm = self._get_llm()
            out = llm.chat([{"role": "user", "content": prompt}])
            return (out or "").strip() or None
        except Exception as e:
            logger.warning("ChunkRefiner LLM 调用失败，将回退规则结果: %s", e)
            return None

    def transform(
        self,
        chunks: List[Chunk],
        trace: Optional[Any] = None,
    ) -> List[Chunk]:
        result: List[Chunk] = []
        for c in chunks:
            try:
                rule_text = _rule_based_refine(c.text)
                refined_by = "rule"
                fallback_reason: Optional[str] = None
                if self._use_llm:
                    llm_text = self._llm_refine(rule_text, trace)
                    if llm_text is not None:
                        final_text = llm_text
                        refined_by = "llm"
                    else:
                        final_text = rule_text
                        fallback_reason = "llm_failed"
                else:
                    final_text = rule_text
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                meta["refined_by"] = refined_by
                if fallback_reason:
                    meta["refinement_fallback"] = fallback_reason
                result.append(
                    Chunk(
                        id=c.id,
                        text=final_text,
                        metadata=meta,
                        start_offset=c.start_offset,
                        end_offset=c.end_offset,
                        source_ref=c.source_ref,
                    )
                )
            except Exception as e:
                logger.warning("ChunkRefiner 单条处理异常，保留原文: id=%s %s", c.id, e)
                meta = dict(c.metadata) if isinstance(c.metadata, dict) else {}
                meta["refined_by"] = "rule"
                meta["refinement_fallback"] = str(e)
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
