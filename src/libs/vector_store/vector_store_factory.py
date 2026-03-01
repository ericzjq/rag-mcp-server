"""
VectorStore 工厂：根据配置选择 provider，创建对应 BaseVectorStore 实例。
B4 先定义契约，不接真实 DB；B7.6 补齐 Chroma 实现。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.vector_store.base_vector_store import BaseVectorStore
from libs.vector_store.chroma_store import ChromaStore

# Provider 名称 -> 实现类（B7.6 chroma，测试中可注册 Fake）
_PROVIDERS: Dict[str, Type[BaseVectorStore]] = {
    "chroma": ChromaStore,
}


def register_vector_store_provider(name: str, impl: Type[BaseVectorStore]) -> None:
    """注册 VectorStore provider，供实现模块或测试使用。"""
    _PROVIDERS[name] = impl


def create(settings: Settings) -> BaseVectorStore:
    """
    根据 settings.vector_store.provider 创建 VectorStore 实例。

    Args:
        settings: 主配置，含 settings.vector_store.provider、persist_directory。

    Returns:
        配置对应的 BaseVectorStore 实例。

    Raises:
        ValueError: 未知 provider 时，错误信息包含 provider 名称。
    """
    provider = settings.vector_store.provider.strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown VectorStore provider: {provider}")
    return _PROVIDERS[provider](settings)


class VectorStoreFactory:
    """VectorStore 工厂：按配置创建 BaseVectorStore 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseVectorStore:
        """根据 settings.vector_store.provider 创建并返回对应 VectorStore 实例。"""
        return create(settings)
