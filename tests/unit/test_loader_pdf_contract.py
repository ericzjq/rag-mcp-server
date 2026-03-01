"""
Loader / PDF 契约测试（C3）：BaseLoader.load、PdfLoader 产出 Document，metadata.source_path；
纯文本与带图片（占位符 + metadata.images）行为；图片失败降级。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.types import Document
from libs.loader.base_loader import BaseLoader
from libs.loader.pdf_loader import PdfLoader, _doc_id_from_path


def test_doc_id_from_path_stable() -> None:
    """同一路径生成稳定 doc_id。"""
    a = _doc_id_from_path("/foo/bar.pdf")
    b = _doc_id_from_path("/foo/bar.pdf")
    assert a == b and len(a) == 16


def test_pdf_loader_load_returns_document_with_source_path(tmp_path: Path) -> None:
    """对 sample PDF 能产出 Document，metadata 至少含 source_path。"""
    # 使用 pypdf 写出一个空白页 PDF
    from pypdf import PdfReader, PdfWriter
    pdf_path = tmp_path / "sample.pdf"
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(pdf_path, "wb") as f:
        w.write(f)
    loader = PdfLoader(images_base_dir=str(tmp_path / "images"))
    doc = loader.load(str(pdf_path))
    assert isinstance(doc, Document)
    assert doc.metadata.get("source_path") == str(pdf_path)
    assert doc.id
    assert isinstance(doc.text, str)


def test_pdf_loader_text_only_mock(tmp_path: Path) -> None:
    """纯文本 PDF（mock）：无 images，metadata 无 images 或为空。"""
    fake_pdf = tmp_path / "simple.pdf"
    fake_pdf.write_bytes(b"dummy")
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello world"
    mock_page.images = []
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        loader = PdfLoader(images_base_dir=str(tmp_path / "img"))
        doc = loader.load(str(fake_pdf))
    assert doc.text.strip() == "Hello world"
    assert doc.metadata.get("source_path") == str(fake_pdf)
    assert doc.metadata.get("images", []) == []


def test_pdf_loader_with_images_mock(tmp_path: Path) -> None:
    """带图片 PDF（mock）：占位符 [IMAGE: id] 与 metadata.images。"""
    fake_pdf = tmp_path / "with_images.pdf"
    fake_pdf.write_bytes(b"dummy")
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page with image"
    mock_img = MagicMock()
    mock_img.data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # minimal PNG magic
    mock_page.images = [mock_img]
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        loader = PdfLoader(images_base_dir=str(tmp_path / "images"))
        doc = loader.load(str(fake_pdf))
    assert "[IMAGE:" in doc.text
    assert doc.metadata.get("images")
    img_list = doc.metadata["images"]
    assert len(img_list) == 1
    assert "id" in img_list[0] and "path" in img_list[0]
    assert img_list[0]["id"] in doc.text


def test_pdf_loader_file_not_found_raises() -> None:
    """路径不存在时抛出 FileNotFoundError。"""
    loader = PdfLoader()
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load("/nonexistent/file.pdf")
    assert "不存在" in str(exc_info.value) or "nonexistent" in str(exc_info.value).lower()


def test_base_loader_subclass_must_implement_load() -> None:
    """BaseLoader 子类必须实现 load。"""
    class IncompleteLoader(BaseLoader):
        pass
    with pytest.raises(TypeError):
        IncompleteLoader().load("/x.pdf")
