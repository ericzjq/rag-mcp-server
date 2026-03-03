"""
RAGAS 评估结果页面（G8）：加载某次评估报告文件，展示 hit_rate、mrr 及 RAGAS 指标（含 per-query 明细）。
"""

import os
import streamlit as st

from observability.dashboard.services.config_service import ConfigService
from observability.evaluation.eval_runner import load_report

DEFAULT_REPORT_PATH = "logs/eval_report_latest.json"


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("RAGAS 评估结果")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    wd = work_dir or getattr(config, "_work_dir", None) or os.getcwd()
    default_path = os.path.join(wd, DEFAULT_REPORT_PATH.replace("/", os.sep))

    report_path = st.text_input(
        "评估报告文件路径（JSON，如运行「评估」页后自动保存的路径）",
        value=default_path,
        key="ragas_report_path",
    )
    if st.button("加载报告", key="ragas_load"):
        if not report_path or not report_path.strip():
            st.warning("请填写报告路径。")
        else:
            path = report_path.strip()
            if not os.path.isabs(path):
                path = os.path.join(wd, path)
            try:
                report = load_report(path)
                st.success("已加载报告")

                st.subheader("汇总指标")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Hit Rate", "%.4f" % report.hit_rate)
                with col2:
                    st.metric("MRR", "%.4f" % report.mrr)

                st.subheader("各 Query 的 RAGAS 指标")
                st.caption("若评估后端为 ragas，每条 query 会包含 faithfulness、answer_relevancy、context_precision 等。")
                for i, qr in enumerate(report.query_results):
                    metrics = qr.get("metrics") or {}
                    ragas_keys = [k for k in metrics if isinstance(metrics.get(k), (int, float))]
                    title = "Query %d: %s" % (i + 1, (qr.get("query") or "")[:60])
                    if len((qr.get("query") or "")) > 60:
                        title += "…"
                    with st.expander(title):
                        st.text("query: %s" % qr.get("query", ""))
                        st.text("hit_rate: %.4f | mrr: %.4f" % (qr.get("hit_rate", 0), qr.get("mrr", 0)))
                        if ragas_keys:
                            cols = st.columns(min(len(ragas_keys), 4))
                            for j, k in enumerate(ragas_keys):
                                with cols[j % len(cols)]:
                                    st.metric(k, "%.4f" % metrics[k] if isinstance(metrics[k], (int, float)) else str(metrics[k]))
                        if not ragas_keys and metrics:
                            st.json(metrics)
            except FileNotFoundError as e:
                st.error("文件不存在: %s。请先在「评估」页运行评估并保存报告。" % e)
            except Exception as e:
                st.error("加载失败: %s" % e)
    else:
        st.info("请填写报告路径并点击「加载报告」。默认可填 logs/eval_report_latest.json（在「评估」页运行评估后会自动保存）。")
