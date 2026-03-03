"""
Ingestion 追踪页面（G5）：摄取历史列表、阶段耗时瀑布图。
"""

import os
from datetime import datetime

import streamlit as st

from observability.dashboard.services.config_service import ConfigService
from observability.dashboard.services.trace_service import TraceService

# 与 F4 打点阶段名一致
INGESTION_STAGES = ["load", "split", "transform", "embed", "upsert"]


def _stage_elapsed_ms(trace: dict, stage: str) -> float:
    """从 trace 的 stages 中取出该阶段的 elapsed_ms。"""
    stages = trace.get("stages") or {}
    data = stages.get(stage)
    if isinstance(data, dict) and "elapsed_ms" in data:
        return float(data["elapsed_ms"])
    return 0.0


def _render_stage_bars(trace: dict) -> None:
    """绘制 load/split/transform/embed/upsert 耗时条形图（竖向柱状图）。"""
    rows = []
    for stage in INGESTION_STAGES:
        ms = _stage_elapsed_ms(trace, stage)
        rows.append({"stage": stage, "elapsed_ms": ms})
    if not any(r["elapsed_ms"] for r in rows):
        st.caption("无阶段耗时数据")
        return
    import pandas as pd
    df = pd.DataFrame(rows)
    st.bar_chart(df.set_index("stage"))


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("Ingestion 追踪")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    wd = work_dir or getattr(config, "_work_dir", None) or os.getcwd()
    traces_path = getattr(settings.observability, "traces_path", "logs/traces.jsonl") if settings else "logs/traces.jsonl"
    trace_svc = TraceService(traces_path=traces_path, work_dir=wd)

    traces = trace_svc.list_traces(trace_type="ingestion")
    if not traces:
        st.info("暂无 Ingestion 追踪记录。请先执行 ingest 后再查看。")
        return

    st.caption("共 %d 条摄取记录（按时间倒序）" % len(traces))
    for t in traces:
        trace_id = t.get("trace_id", "")
        started = t.get("started_at")
        time_str = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S") if started else "-"
        total_ms = t.get("total_elapsed_ms") or 0
        stages = t.get("stages") or {}
        doc_id = stages.get("load", {}).get("document_id", "") if isinstance(stages.get("load"), dict) else ""

        with st.expander("%s | %s | 总耗时 %.0f ms" % (time_str, doc_id or trace_id[:8], total_ms)):
            st.text("trace_id: %s" % trace_id)
            st.text("document_id: %s" % doc_id)
            st.subheader("阶段耗时")
            _render_stage_bars(t)
