"""
文件完整性检查（C2）：计算 SHA256，判定是否跳过摄取；默认 SQLite 存储，支持后续替换。
"""

import hashlib
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple


class FileIntegrityChecker(ABC):
    """抽象接口：计算 hash、是否跳过、标记成功/失败。"""

    @abstractmethod
    def compute_sha256(self, path: str) -> str:
        """计算文件 SHA256，返回十六进制字符串。"""
        ...

    @abstractmethod
    def should_skip(self, file_hash: str) -> bool:
        """若该 hash 已标记为成功则返回 True（可跳过摄取）。"""
        ...

    @abstractmethod
    def mark_success(self, file_hash: str, file_path: str, **kwargs: object) -> None:
        """标记该 hash 对应文件摄取成功。"""
        ...

    @abstractmethod
    def mark_failed(self, file_hash: str, error_msg: str) -> None:
        """标记该 hash 对应文件摄取失败。"""
        ...

    def list_processed(self) -> List[Tuple[str, str]]:
        """返回已成功摄取的 (file_path, file_hash) 列表；默认实现可被子类覆盖。"""
        return []

    def remove_record(self, file_hash: str) -> bool:
        """移除指定 file_hash 的摄取记录；若不存在返回 False。默认实现可被子类覆盖。"""
        return False

    def remove_record_by_path(self, file_path: str) -> bool:
        """按 file_path 移除摄取记录（用于文件已删除的场景，如 Dashboard 上传的临时文件）。默认返回 False。"""
        return False

    def clear_all(self) -> int:
        """清空全部已摄取文件记录，返回删除条数。默认实现可被子类覆盖。"""
        return 0


def _sha256_of_file(path: str) -> str:
    """计算文件 SHA256（十六进制）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class SQLiteIntegrityChecker(FileIntegrityChecker):
    """使用 SQLite 存储摄取历史；数据库位于 data/db/ingestion_history.db，WAL 模式支持并发。"""

    def __init__(self, db_path: str = "data/db/ingestion_history.db") -> None:
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS ingestion_history (
                    file_hash TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_msg TEXT,
                    updated_at TEXT
                )"""
            )
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def compute_sha256(self, path: str) -> str:
        return _sha256_of_file(path)

    def should_skip(self, file_hash: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM ingestion_history WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
        return row is not None and row[0] == "success"

    def mark_success(self, file_hash: str, file_path: str, **kwargs: object) -> None:
        import datetime
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ingestion_history (file_hash, file_path, status, error_msg, updated_at)
                   VALUES (?, ?, 'success', NULL, ?)""",
                (file_hash, file_path, now),
            )
            conn.commit()

    def mark_failed(self, file_hash: str, error_msg: str) -> None:
        import datetime
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ingestion_history (file_hash, file_path, status, error_msg, updated_at)
                   VALUES (?, '', 'failed', ?, ?)""",
                (file_hash, error_msg, now),
            )
            conn.commit()

    def list_processed(self) -> List[Tuple[str, str]]:
        """返回已成功摄取的 (file_path, file_hash) 列表。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT file_path, file_hash FROM ingestion_history WHERE status = 'success' ORDER BY file_path"
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def remove_record(self, file_hash: str) -> bool:
        """移除指定 file_hash 的摄取记录；若不存在返回 False。"""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM ingestion_history WHERE file_hash = ?", (file_hash,))
            conn.commit()
            return cur.rowcount > 0

    def remove_record_by_path(self, file_path: str) -> bool:
        """按 file_path 移除摄取记录（文件已不存在时使用，如 Dashboard 上传后已删除的临时文件）。"""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM ingestion_history WHERE file_path = ?", (file_path,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> int:
        """清空全部已摄取文件记录，返回删除条数。"""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM ingestion_history")
            conn.commit()
            return cur.rowcount
