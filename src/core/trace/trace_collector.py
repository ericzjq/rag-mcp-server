"""
TraceCollector（F1）：收集 TraceContext 并触发持久化。
"""

import logging
from typing import Any, Callable, Optional

from core.trace.trace_context import TraceContext

logger = logging.getLogger(__name__)


class TraceCollector:
    """收集 trace 并调用注入的 writer 持久化（如写入 logs/traces.jsonl）。"""

    def __init__(self, writer: Optional[Callable[[dict], None]] = None) -> None:
        self._writer = writer

    def collect(self, trace: TraceContext) -> None:
        """收集 trace，序列化后调用 writer（若已配置）。"""
        try:
            payload = trace.to_dict()
            if self._writer is not None:
                self._writer(payload)
        except Exception as e:
            logger.warning("TraceCollector 持久化失败: %s", e)
