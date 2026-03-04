#!/usr/bin/env python3
"""
清空 Chroma 与 BM25 中的全部 chunk（chunk_id 生成逻辑变更后，需清空旧数据再重新摄取）。
"""

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
_SRC = os.path.join(_ROOT, "src")
for _p in (_SRC, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.chdir(_ROOT)


def main() -> int:
    config_path = os.path.join(_ROOT, "config", "settings.yaml")
    if not os.path.isfile(config_path):
        print("ERROR: config/settings.yaml 不存在", file=sys.stderr)
        return 1

    from core.settings import load_settings
    from libs.vector_store.vector_store_factory import create as create_vector_store
    from libs.loader.file_integrity import SQLiteIntegrityChecker
    from ingestion.storage.bm25_indexer import BM25Indexer

    settings = load_settings(config_path)
    work_dir = _ROOT
    chroma = create_vector_store(settings)
    bm25_dir = os.path.join(work_dir, "data/db/bm25")
    integrity_db = os.path.join(work_dir, "data/db/ingestion_history.db")
    integrity = SQLiteIntegrityChecker(db_path=integrity_db)

    # 1. Chroma: 删除全部 chunk
    if hasattr(chroma, "get_all") and hasattr(chroma, "delete_ids"):
        all_records = chroma.get_all(limit=100000)
        ids = [r["id"] for r in all_records]
        if ids:
            n = chroma.delete_ids(ids)
            print("Chroma: 已删除 %d 条 chunk" % n)
        else:
            print("Chroma: 当前无 chunk")
    else:
        print("Chroma: 当前实现不支持 get_all/delete_ids，跳过")

    # 2. BM25: 清空索引（写入空索引）
    indexer = BM25Indexer(index_dir=bm25_dir)
    indexer.build([]).save()
    print("BM25: 已清空索引 (%s)" % os.path.join(bm25_dir, "index.json"))

    # 3. 已摄取文件记录（integrity）清空
    n_integrity = integrity.clear_all()
    print("已摄取文件记录: 已删除 %d 条" % n_integrity)

    print("完成。请重新运行 ingest 摄取文档。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
