"""
评估面板页面（H4）：选择 golden test set、运行评估、展示 hit_rate、mrr、各 query 明细。
"""

import os
import streamlit as st

from core.query_engine.hybrid_search import HybridSearch
from libs.evaluator.evaluator_factory import create as create_evaluator

from observability.dashboard.services.config_service import ConfigService
from observability.evaluation.eval_runner import EvalRunner, save_report

DEFAULT_GOLDEN_PATH = "tests/fixtures/golden_test_set.json"


def run(config_path: str = None, work_dir: str = None) -> None:
    st.title("评估")
    config = ConfigService(config_path=config_path, work_dir=work_dir)
    settings = config.get_settings()
    if settings is None:
        st.warning("未找到配置文件（config/settings.yaml），无法运行评估。")
        return

    wd = work_dir or getattr(config, "_work_dir", None) or os.getcwd()
    default_path = os.path.join(wd, DEFAULT_GOLDEN_PATH.replace("/", os.sep))

    st.subheader("运行评估")
    st.caption("评估后端使用当前配置：evaluation.provider = %s" % getattr(settings.evaluation, "provider", "custom"))
    test_set_path = st.text_input(
        "Golden test set 路径（相对项目根或绝对路径）",
        value=default_path,
        key="eval_test_set_path",
    )
    top_k = st.number_input("每条 query 检索条数 (top_k)", min_value=1, value=10, key="eval_top_k")

    if st.button("运行评估", key="eval_run"):
        if not test_set_path or not test_set_path.strip():
            st.warning("请填写 golden test set 路径。")
        else:
            path = test_set_path.strip()
            if not os.path.isabs(path):
                path = os.path.join(wd, path)
            try:
                hybrid_search = HybridSearch(settings)
                evaluator = create_evaluator(settings)
                runner = EvalRunner(settings, hybrid_search, evaluator)
                with st.spinner("评估中…"):
                    report = runner.run(path, top_k=top_k)
                st.success("评估完成")
                latest_path = os.path.join(wd, "logs", "eval_report_latest.json")
                try:
                    save_report(report, latest_path)
                    st.caption("报告已保存至 %s，可在「RAGAS 评估结果」页查看。" % latest_path)
                except Exception:
                    pass
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Hit Rate", "%.4f" % report.hit_rate)
                with col2:
                    st.metric("MRR", "%.4f" % report.mrr)
                st.caption("共 %d 条 query" % len(report.query_results))
                for i, qr in enumerate(report.query_results):
                    with st.expander("Query %d: %s" % (i + 1, (qr.get("query") or "")[:50])):
                        st.text("query: %s" % qr.get("query", ""))
                        st.text("hit_rate: %.4f | mrr: %.4f" % (qr.get("hit_rate", 0), qr.get("mrr", 0)))
                        st.text("retrieved_ids: %s" % (qr.get("retrieved_ids") or []))
                        st.text("expected_chunk_ids: %s" % (qr.get("expected_chunk_ids") or []))
                        if qr.get("metrics"):
                            st.json(qr["metrics"])
            except FileNotFoundError as e:
                st.error("文件不存在: %s" % e)
            except Exception as e:
                st.error("评估失败: %s" % e)
