"""
TraceContext（C5 占位，Phase F 完善）：trace_id、record_stage，用于链路追踪。
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TraceContext:
    """最小实现：生成 trace_id，可记录阶段数据。"""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _stages: Dict[str, Any] = field(default_factory=dict)

    def record_stage(self, stage: str, data: Any = None) -> None:
        """记录某阶段数据（如 transform、refine）。"""
        self._stages[stage] = data

    def get_stage(self, stage: str) -> Optional[Any]:
        """获取已记录的阶段数据。"""
        return self._stages.get(stage)
