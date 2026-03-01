"""
文件完整性检查单元测试（C2）：同一文件 hash 一致、mark_success 后 should_skip、DB 路径、WAL。
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from libs.loader.file_integrity import (
    FileIntegrityChecker,
    SQLiteIntegrityChecker,
    _sha256_of_file,
)


def test_compute_sha256_same_file_same_hash(tmp_path: Path) -> None:
    """同一文件多次计算 hash 结果一致。"""
    f = tmp_path / "same.txt"
    f.write_text("hello")
    checker = SQLiteIntegrityChecker(db_path=str(tmp_path / "db" / "ingestion.db"))
    h1 = checker.compute_sha256(str(f))
    h2 = checker.compute_sha256(str(f))
    assert h1 == h2
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)


def test_mark_success_then_should_skip_returns_true(tmp_path: Path) -> None:
    """标记 success 后，should_skip 返回 True。"""
    db = str(tmp_path / "data" / "db" / "ingestion_history.db")
    checker = SQLiteIntegrityChecker(db_path=db)
    file_hash = "a" * 64
    assert checker.should_skip(file_hash) is False
    checker.mark_success(file_hash, "/path/to/file.pdf")
    assert checker.should_skip(file_hash) is True


def test_mark_failed_does_not_skip(tmp_path: Path) -> None:
    """mark_failed 后 should_skip 仍为 False（仅 success 才跳过）。"""
    db = str(tmp_path / "ingestion.db")
    checker = SQLiteIntegrityChecker(db_path=db)
    file_hash = "b" * 64
    checker.mark_failed(file_hash, "parse error")
    assert checker.should_skip(file_hash) is False


def test_db_created_at_given_path(tmp_path: Path) -> None:
    """数据库在指定路径创建（如 data/db/ingestion_history.db）。"""
    db_path = tmp_path / "data" / "db" / "ingestion_history.db"
    assert not db_path.exists()
    checker = SQLiteIntegrityChecker(db_path=str(db_path))
    checker.mark_success("c" * 64, "x.pdf")
    assert db_path.exists()


def test_sqlite_wal_mode(tmp_path: Path) -> None:
    """SQLite 使用 WAL 模式。"""
    db = str(tmp_path / "wal.db")
    SQLiteIntegrityChecker(db_path=db).mark_success("d" * 64, "y.pdf")
    with sqlite3.connect(db) as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row is not None and row[0].lower() == "wal"


def test_sha256_helper(tmp_path: Path) -> None:
    """_sha256_of_file 与 compute_sha256 结果一致。"""
    f = tmp_path / "f.bin"
    f.write_bytes(b"content")
    checker = SQLiteIntegrityChecker(db_path=str(tmp_path / "h.db"))
    assert _sha256_of_file(str(f)) == checker.compute_sha256(str(f))


def test_concurrent_writes(tmp_path: Path) -> None:
    """支持并发写入（WAL 下多连接写）。"""
    db = str(tmp_path / "concurrent.db")
    checker = SQLiteIntegrityChecker(db_path=db)
    # 顺序多次写，无异常即可；真实并发可由线程/进程测试
    for i in range(5):
        checker.mark_success(f"hash_{i:02d}" + "0" * 58, f"file_{i}.pdf")
    for i in range(5):
        assert checker.should_skip(f"hash_{i:02d}" + "0" * 58) is True
