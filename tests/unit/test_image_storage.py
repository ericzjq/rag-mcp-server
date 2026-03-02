"""
ImageStorage 单元测试（C13）：保存后文件存在；查找 image_id 返回正确路径；映射持久化；按 collection 查询。
"""

import tempfile
from pathlib import Path

import pytest

from ingestion.storage.image_storage import ImageStorage


def test_save_then_file_exists() -> None:
    """保存后文件存在。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "db" / "image_index.db"
        images = Path(tmp) / "images"
        storage = ImageStorage(db_path=str(db), images_base=str(images))
        content = b"\x89PNG\r\n\x1a\n"
        path = storage.save("img1.png", content, collection="doc1")
        assert Path(path).exists()
        assert Path(path).read_bytes() == content


def test_get_path_returns_correct_path() -> None:
    """查找 image_id 返回正确路径。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "image_index.db"
        storage = ImageStorage(db_path=str(db), images_base=str(Path(tmp) / "imgs"))
        storage.save("my_id.png", b"x", collection="c1")
        found = storage.get_path("my_id.png")
        assert found is not None
        assert "my_id.png" in found
        assert Path(found).exists()
        assert storage.get_path("nonexistent") is None


def test_mapping_persisted_in_db() -> None:
    """映射关系持久化在 DB；新实例 load 同库可查到。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "image_index.db"
        base = Path(tmp) / "imgs"
        s1 = ImageStorage(db_path=str(db), images_base=str(base))
        s1.save("id1", b"content1", collection="col")
        s2 = ImageStorage(db_path=str(db), images_base=str(base))
        path = s2.get_path("id1")
        assert path is not None
        assert Path(path).read_bytes() == b"content1"


def test_list_by_collection() -> None:
    """按 collection 批量查询。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "idx.db"
        storage = ImageStorage(db_path=str(db), images_base=str(Path(tmp) / "imgs"))
        storage.save("a.png", b"1", collection="X")
        storage.save("b.png", b"2", collection="X")
        storage.save("c.png", b"3", collection="Y")
        list_x = storage.list_by_collection("X")
        assert len(list_x) == 2
        ids = {r["image_id"] for r in list_x}
        assert ids == {"a.png", "b.png"}
        assert all("file_path" in r for r in list_x)
        list_y = storage.list_by_collection("Y")
        assert len(list_y) == 1
        assert list_y[0]["image_id"] == "c.png"


def test_save_rejects_empty_image_id() -> None:
    """image_id 为空时抛出 ValueError。"""
    with tempfile.TemporaryDirectory() as tmp:
        storage = ImageStorage(db_path=str(Path(tmp) / "db"), images_base=str(Path(tmp) / "imgs"))
        with pytest.raises(ValueError, match="不能为空"):
            storage.save("", b"x")
