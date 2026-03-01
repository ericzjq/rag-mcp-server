"""
冒烟测试：校验关键顶层包可导入。

对应 DEV_SPEC A2 验收标准，作为 pytest 基座的首个用例。
"""

import pytest


def test_import_mcp_server() -> None:
    """mcp_server 包可导入。"""
    import mcp_server  # noqa: F401
    assert mcp_server is not None


def test_import_core() -> None:
    """core 包可导入。"""
    import core  # noqa: F401
    assert core is not None


def test_import_ingestion() -> None:
    """ingestion 包可导入。"""
    import ingestion  # noqa: F401
    assert ingestion is not None


def test_import_libs() -> None:
    """libs 包可导入。"""
    import libs  # noqa: F401
    assert libs is not None


def test_import_observability() -> None:
    """observability 包可导入。"""
    import observability  # noqa: F401
    assert observability is not None


@pytest.mark.unit
def test_all_key_packages_importable() -> None:
    """一次性校验五大关键包均可导入（与 A1 验收一致）。"""
    import mcp_server
    import core
    import ingestion
    import libs
    import observability
    for pkg in (mcp_server, core, ingestion, libs, observability):
        assert pkg is not None
