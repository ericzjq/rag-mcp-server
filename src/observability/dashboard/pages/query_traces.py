"""
Query 追踪页面（G6）：查询历史、按关键词筛选、耗时瀑布图、Dense vs Sparse 对比、Rerank 阶段。
"""

import json
import os
from datetime import datetime

import streamlit as st

from observability.dashboard.services.config_service import ConfigService
from observability.dashboard.services.trace_service import TraceService

# 与 F3 打点阶段名一致
QUERY_STAGES = ["query_processing", "dense_retrieval", "sparse_retrieval", "fusion", "rerank"]


def _stage_elapsed_ms(trace: dict, stage: str) -> float:
    """从 trace 的 stages 中取出该阶段的 elapsed_ms。"""
    stages = trace.get("stages") or {}
    data = stages.get(stage)
    if isinstance(data, dict) and "elapsed_ms" in data:
        return float(data["elapsed_ms"])
    return 0.0


def _trace_matches_keyword(trace: dict, keyword: str) -> bool:
    """若 keyword 在 trace_id 或任意 stage 的字符串表示中出现则返回 True。"""
    if not (keyword or "").strip():
        return True
    k = keyword.strip().lower()
    if k in (trace.get("trace_id") or "").lower():
        return True
    for _name, data in (trace.get("stages") or {}).items():
        if k in json.dumps(data, ensure_ascii=False).lower():
            return True
    return False


def _render_query_detail(trace: dict) -> None:
    """耗时瀑布图 + Dense vs Sparse 并列 + Rerank 阶段。"""
    stages = trace.get("stages") or {}

    # 1) 阶段耗时条形图
    rows = []
    for stage in QUERY_STAGES:
        ms = _stage_elapsed_ms(trace, stage)
        rows.append({"stage": stage, "elapsed_ms": ms})
    if any(r["elapsed_ms"] for r in rows):
        import pandas as pd
        df = pd.DataFrame(rows)
        st.subheader("阶段耗时")
        st.bar_chart(df.set_index("stage"))

    # 2) Dense vs Sparse 并列对比
    st.subheader("Dense vs Sparse 检索")
    col_dense, col_sparse = st.columns(2)
    with col_dense:
        d = stages.get("dense_retrieval")
        if isinstance(d, dict):
            st.metric("Dense 检索", "%.0f ms" % d.get("elapsed_ms", 0))
            st.caption("method: %s" % d.get("method", "-"))
        else:
            st.caption("无 Dense 阶段数据")
    with col_sparse:
        s = stages.get("sparse_retrieval")
        if isinstance(s, dict):
            st.metric("Sparse 检索", "%.0f ms" % s.get("elapsed_ms", 0))
            st.caption("method: %s" % s.get("method", "-"))
        else:
            st.caption("无 Sparse 阶段数据")

    # 3) Rerank 阶段
    st.subheader("Rerank")
    r = stages.get("rerank")
    if isinstance(r, dict):
        st.metric("Rerank 耗时", "%.0f ms" % r.get("elapsed_ms", 0))
        st.caption("method: %s" % r.get("method", "-"))
    else:
        st.caption("无 Rerank 阶段数据（或未启用 Reranker）")


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("Query 追踪")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    wd = work_dir or getattr(config, "_work_dir", None) or os.getcwd()
    traces_path = getattr(settings.observability, "traces_path", "logs/traces.jsonl") if settings else "logs/traces.jsonl"
    trace_svc = TraceService(traces_path=traces_path, work_dir=wd)

    traces = trace_svc.list_traces(trace_type="query")
    keyword = st.text_input("按关键词筛选（trace_id 或阶段内容）", value="", key="query_traces_keyword")
    if keyword:
        traces = [t for t in traces if _trace_matches_keyword(t, keyword)]

    if not traces:
        st.info("暂无 Query 追踪记录。请先通过 MCP 或脚本执行 query（会写入 trace）后再查看。")
        return

    st.caption("RAGAS（faithfulness / answer_relevancy / context_precision）来自离线评估脚本，本页仅展示检索阶段耗时。")

    st.caption("共 %d 条查询记录（按时间倒序）" % len(traces))
    for t in traces:
        trace_id = t.get("trace_id", "")
        started = t.get("started_at")
        time_str = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S") if started else "-"
        total_ms = t.get("total_elapsed_ms") or 0
        query_text = ""
        qp = (t.get("stages") or {}).get("query_processing")
        if isinstance(qp, dict) and "query" in qp:
            query_text = qp.get("query", "")

        with st.expander("%s | %s | 总耗时 %.0f ms" % (time_str, (query_text[:30] + "…" if len(query_text) > 30 else query_text) or trace_id[:8], total_ms)):
            st.text("trace_id: %s" % trace_id)
            if query_text:
                st.text("query: %s" % query_text)
            _render_query_detail(t)
