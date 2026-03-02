"""
TraceContext（C5 占位，F1 增强）：trace_id、trace_type、record_stage、finish、elapsed_ms、to_dict。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TraceContext:
    """链路追踪上下文：trace_id、trace_type（query/ingestion）、阶段数据、耗时、可序列化。"""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_type: str = "query"
    _stages: Dict[str, Any] = field(default_factory=dict)
    _started_at: float = field(default_factory=time.time)
    _finished_at: Optional[float] = field(default=None)
    _total_elapsed_ms: float = 0.0

    def record_stage(self, stage: str, data: Any = None) -> None:
        """记录某阶段数据（如 transform、refine）。"""
        self._stages[stage] = data

    def get_stage(self, stage: str) -> Optional[Any]:
        """获取已记录的阶段数据。"""
        return self._stages.get(stage)

    def finish(self) -> None:
        """标记 trace 结束，计算总耗时。"""
        if self._finished_at is None:
            self._finished_at = time.time()
            self._total_elapsed_ms = (self._finished_at - self._started_at) * 1000.0

    def elapsed_ms(self, stage_name: Optional[str] = None) -> float:
        """获取指定阶段的 elapsed_ms（从阶段 data 中取），或总耗时（需先 finish）。"""
        if stage_name is not None:
            stage_data = self._stages.get(stage_name)
            if isinstance(stage_data, dict) and "elapsed_ms" in stage_data:
                return float(stage_data["elapsed_ms"])
            return 0.0
        return self._total_elapsed_ms

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 输出的字典（含 trace_id、trace_type、started_at、finished_at、total_elapsed_ms、stages）。"""
        return {
            "trace_id": self.trace_id,
            "trace_type": self.trace_type,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "total_elapsed_ms": round(self._total_elapsed_ms, 2),
            "stages": dict(self._stages),
        }
