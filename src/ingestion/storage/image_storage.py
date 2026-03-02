"""
ImageStorage（C13）：保存图片到 data/images/{collection}/，SQLite 记录 image_id→path 映射。
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = "data/db/image_index.db"
_DEFAULT_IMAGES_BASE = "data/images"


class ImageStorage:
    """图片文件存储 + SQLite 索引（image_id→path）；WAL 模式；支持按 collection 批量查询。"""

    def __init__(
        self,
        db_path: str = _DEFAULT_DB,
        images_base: str = _DEFAULT_IMAGES_BASE,
    ) -> None:
        self._db_path = db_path
        self._images_base = Path(images_base)
        self._ensure_db()

    def _ensure_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS image_index (
                    image_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    collection TEXT,
                    doc_hash TEXT,
                    page_num INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_collection ON image_index(collection)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON image_index(doc_hash)")
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save(
        self,
        image_id: str,
        content: bytes,
        collection: str = "",
        doc_hash: Optional[str] = None,
        page_num: Optional[int] = None,
    ) -> str:
        """
        将图片内容写入 data/images/{collection}/{filename}，并在 SQLite 中记录映射。

        使用 image_id 的文件名部分作为存储文件名，避免路径穿越。

        Returns:
            写入的绝对路径（或规范路径）。
        """
        if not image_id.strip():
            raise ValueError("image_id 不能为空")
        safe_name = Path(image_id).name or image_id
        collection_dir = self._images_base / (collection.strip() or "_default")
        collection_dir.mkdir(parents=True, exist_ok=True)
        file_path = collection_dir / safe_name
        file_path.write_bytes(content)
        path_str = str(file_path)

        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO image_index (image_id, file_path, collection, doc_hash, page_num)
                   VALUES (?, ?, ?, ?, ?)""",
                (image_id, path_str, collection.strip() or None, doc_hash, page_num),
            )
            conn.commit()
        return path_str

    def register(
        self,
        image_id: str,
        file_path: str,
        collection: str = "",
        doc_hash: Optional[str] = None,
        page_num: Optional[int] = None,
    ) -> None:
        """仅将已有文件的映射写入索引（不复制文件）；用于 Loader 已写入文件后的登记。"""
        if not image_id.strip():
            raise ValueError("image_id 不能为空")
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO image_index (image_id, file_path, collection, doc_hash, page_num)
                   VALUES (?, ?, ?, ?, ?)""",
                (image_id, file_path, collection.strip() or None, doc_hash, page_num),
            )
            conn.commit()

    def get_path(self, image_id: str) -> Optional[str]:
        """根据 image_id 查找已存储的文件路径；不存在返回 None。"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT file_path FROM image_index WHERE image_id = ?",
                (image_id,),
            ).fetchone()
        return row[0] if row else None

    def list_by_collection(self, collection: str) -> List[Dict[str, Any]]:
        """按 collection 批量查询，返回含 image_id、file_path、doc_hash、page_num 等字段的字典列表。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT image_id, file_path, collection, doc_hash, page_num, created_at FROM image_index WHERE collection = ? ORDER BY image_id",
                (collection.strip(),),
            )
            rows = cursor.fetchall()
        return [
            {
                "image_id": r[0],
                "file_path": r[1],
                "collection": r[2],
                "doc_hash": r[3],
                "page_num": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]
