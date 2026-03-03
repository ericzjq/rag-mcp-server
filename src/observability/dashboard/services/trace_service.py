"""
TraceService（G5）：读取 logs/traces.jsonl，解析为 Trace 列表，供 Ingestion/Query 追踪页使用。
"""

import json
import os
from typing import Any, Dict, List, Optional


class TraceService:
    """从 JSONL 文件读取 trace 记录，支持按 trace_type 筛选、按时间倒序。"""

    def __init__(self, traces_path: Optional[str] = None, work_dir: Optional[str] = None) -> None:
        """
        Args:
            traces_path: 完整路径或相对 work_dir 的路径；为 None 时使用默认 logs/traces.jsonl。
            work_dir: 当 traces_path 为相对路径时的基准目录；为 None 时使用当前工作目录。
        """
        self._path = traces_path or "logs/traces.jsonl"
        self._work_dir = work_dir or os.getcwd()
        if not os.path.isabs(self._path):
            self._path = os.path.join(self._work_dir, self._path)

    def _read_lines(self) -> List[Dict[str, Any]]:
        """读取文件，每行解析为 JSON，返回字典列表；文件不存在或为空返回空列表。"""
        if not os.path.isfile(self._path):
            return []
        records: List[Dict[str, Any]] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def list_traces(
        self,
        trace_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        返回 trace 列表，按 started_at 倒序（最新在前）。
        若指定 trace_type，仅返回该类型的记录。
        """
        records = self._read_lines()
        if trace_type is not None:
            records = [r for r in records if r.get("trace_type") == trace_type]
        records.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
        if limit is not None:
            records = records[:limit]
        return records

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """根据 trace_id 返回单条 trace；不存在返回 None。"""
        for r in self._read_lines():
            if r.get("trace_id") == trace_id:
                return r
        return None
