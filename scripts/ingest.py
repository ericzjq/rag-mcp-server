#!/usr/bin/env python3
"""
摄取脚本入口（C15）：支持 --collection、--path、--force，调用 IngestionPipeline。
离线可用；重复运行在未变更时跳过（依赖 integrity 检查）。
"""

import argparse
import logging
import os
import sys

# 确保项目根在 path 中（脚本可能从 scripts/ 或项目根执行）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.settings import load_settings
from core.trace.trace_context import TraceContext
from ingestion.pipeline import IngestionPipeline
from ingestion.transform.chunk_refiner import ChunkRefiner
from ingestion.transform.image_captioner import ImageCaptioner
from ingestion.transform.metadata_enricher import MetadataEnricher
from libs.loader.file_integrity import SQLiteIntegrityChecker
from observability.logger import write_trace


def main() -> int:
    parser = argparse.ArgumentParser(description="摄取文档到向量索引与 BM25 索引（离线可用）")
    parser.add_argument("--path", required=True, help="文档路径（如 PDF）")
    parser.add_argument("--collection", default="", help="集合名（用于图片登记等），默认空")
    parser.add_argument("--force", action="store_true", help="强制重新摄取，跳过 integrity 检查")
    parser.add_argument(
        "--config",
        default=os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml"),
        help="配置文件路径（默认 config/settings.yaml 或 MCP_CONFIG_PATH）",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="工作目录（data/db、data/images 等相对此目录）；默认用脚本所在项目根",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    parser.add_argument(
        "--skip-image-caption",
        action="store_true",
        help="跳过图片 caption（Transform 阶段不调 Vision LLM），大 PDF 含图多时建议使用以免卡住",
    )
    parser.add_argument(
        "--max-image-captions",
        type=int,
        default=None,
        metavar="N",
        help="Transform 阶段最多对 N 张图调用 Vision LLM（默认不限制）。例如 --max-image-captions 1 仅对第一张图做图转文",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    work_dir = args.work_dir or _ROOT
    os.chdir(work_dir)

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(work_dir, config_path)
    if not os.path.exists(config_path):
        logger.error("配置文件不存在: %s", config_path)
        return 1

    settings = load_settings(config_path)
    integrity = SQLiteIntegrityChecker(db_path=os.path.join(work_dir, "data/db/ingestion_history.db"))
    transforms = None
    if args.skip_image_caption:
        transforms = [
            ChunkRefiner(settings, use_llm=False),
            MetadataEnricher(settings),
        ]
        logger.info("已启用 --skip-image-caption，Transform 阶段将不调用 Vision LLM")
    elif args.max_image_captions is not None:
        transforms = [
            ChunkRefiner(settings, use_llm=False),
            MetadataEnricher(settings),
            ImageCaptioner(settings, max_images=args.max_image_captions),
        ]
        logger.info("已启用 --max-image-captions %d，Transform 阶段仅对前 %d 张图做 caption", args.max_image_captions, args.max_image_captions)
    pipeline = IngestionPipeline(settings, integrity_checker=integrity, transforms=transforms)

    path = args.path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    if not os.path.exists(path):
        logger.error("文档不存在: %s", path)
        return 1

    traces_path = getattr(settings.observability, "traces_path", "logs/traces.jsonl")
    if not os.path.isabs(traces_path):
        traces_path = os.path.join(work_dir, traces_path)
    trace = TraceContext(trace_type="ingestion")
    try:
        result = pipeline.run(
            path,
            collection=args.collection or "",
            force=args.force,
            trace=trace,
        )
    except Exception as e:
        logger.exception("摄取失败: %s", e)
        return 1

    if not result.get("skipped"):
        try:
            write_trace(trace.to_dict(), path=traces_path)
        except Exception as e:
            logger.warning("写入 ingestion trace 失败: %s", e)

    if result.get("skipped"):
        logger.info("已跳过（此前已成功摄取）: %s", path)
        return 0
    logger.info(
        "摄取完成: document_id=%s, chunks=%s, records=%s",
        result.get("document_id"),
        result.get("chunks_count", 0),
        result.get("records_count", 0),
    )
    # 打印各阶段耗时
    stages = trace.to_dict().get("stages") or {}
    total_ms = trace.to_dict().get("total_elapsed_ms") or 0
    logger.info("摄取链路耗时: 总 %.0f ms", total_ms)
    for name in ("load", "split", "transform", "embed", "upsert"):
        data = stages.get(name)
        if isinstance(data, dict) and "elapsed_ms" in data:
            logger.info("  %s: %.0f ms", name, data["elapsed_ms"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
