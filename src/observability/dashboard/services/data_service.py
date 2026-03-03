"""
DataService（G3）：封装 DocumentManager，为 Dashboard 数据浏览器提供文档列表与详情。
从 ConfigService 加载 Settings 并构建 ChromaStore、BM25Indexer、ImageStorage、FileIntegrity，委托 DocumentManager。
"""

import os
from typing import List, Optional

from ingestion.document_manager import DocumentManager, DocumentInfo, DocumentDetail, DeleteResult
from libs.loader.file_integrity import SQLiteIntegrityChecker
from libs.vector_store.chroma_store import ChromaStore

from observability.dashboard.services.config_service import ConfigService

from ingestion.storage.bm25_indexer import BM25Indexer
from ingestion.storage.image_storage import ImageStorage


# 与 Pipeline / 默认路径一致
DEFAULT_BM25_INDEX_DIR = "data/db/bm25"
DEFAULT_INGESTION_DB = "data/db/ingestion_history.db"
DEFAULT_IMAGE_DB = "data/db/image_index.db"
DEFAULT_IMAGES_BASE = "data/images"


class DataService:
    """基于配置构建 DocumentManager，提供 list_documents、get_document_detail、list_collections。"""

    def __init__(self, config_path: Optional[str] = None, work_dir: Optional[str] = None) -> None:
        self._config = ConfigService(config_path=config_path, work_dir=work_dir or os.getcwd())
        self._manager: Optional[DocumentManager] = None
        self._image_storage: Optional[ImageStorage] = None

    def _get_manager(self) -> Optional[DocumentManager]:
        if self._manager is not None:
            return self._manager
        settings = self._config.get_settings()
        if settings is None:
            return None
        try:
            chroma = ChromaStore(settings)
            work_dir = self._config._work_dir
            bm25_dir = os.path.join(work_dir, DEFAULT_BM25_INDEX_DIR)
            ingestion_db = os.path.join(work_dir, DEFAULT_INGESTION_DB)
            image_db = os.path.join(work_dir, DEFAULT_IMAGE_DB)
            images_base = os.path.join(work_dir, DEFAULT_IMAGES_BASE)
            bm25 = BM25Indexer(index_dir=bm25_dir)
            image_storage = ImageStorage(db_path=image_db, images_base=images_base)
            self._image_storage = image_storage
            integrity = SQLiteIntegrityChecker(db_path=ingestion_db)
            self._manager = DocumentManager(chroma, bm25, image_storage, integrity)
            return self._manager
        except Exception:
            return None

    def list_documents(self, collection: Optional[str] = None) -> List[DocumentInfo]:
        """列出已摄入文档；collection 为 None 时返回全部。"""
        mgr = self._get_manager()
        if mgr is None:
            return []
        return mgr.list_documents(collection=collection)

    def get_document_detail(self, doc_id: str) -> Optional[DocumentDetail]:
        """获取单文档详情（chunks + images）。"""
        mgr = self._get_manager()
        if mgr is None:
            return None
        return mgr.get_document_detail(doc_id)

    def list_collections(self) -> List[str]:
        """返回可用于筛选的 collection 名称列表（来自 ImageStorage）；无数据时为空。"""
        if self._image_storage is None:
            self._get_manager()
        if self._image_storage is None:
            return []
        return self._image_storage.list_collection_names()

    def delete_document(self, source_path: str, collection: str = "") -> Optional[DeleteResult]:
        """删除指定文档（协调 Chroma/BM25/ImageStorage/FileIntegrity）；失败返回 None。"""
        mgr = self._get_manager()
        if mgr is None:
            return None
        return mgr.delete_document(source_path, collection=collection)
