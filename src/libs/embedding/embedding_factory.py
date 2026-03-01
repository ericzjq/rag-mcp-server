"""
Embedding 工厂：根据配置选择 provider，创建对应 BaseEmbedding 实例。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.embedding.base_embedding import BaseEmbedding

# Provider 名称 -> 实现类（B7.3/B7.4 补齐 openai/azure/ollama，测试中可注册 Fake）
_PROVIDERS: Dict[str, Type[BaseEmbedding]] = {}


def register_embedding_provider(name: str, impl: Type[BaseEmbedding]) -> None:
    """注册 Embedding provider，供实现模块或测试使用。"""
    _PROVIDERS[name] = impl


def create(settings: Settings) -> BaseEmbedding:
    """
    根据 settings.embedding.provider 创建 Embedding 实例。

    Args:
        settings: 主配置，含 settings.embedding.provider 与 settings.embedding.model。

    Returns:
        配置对应的 BaseEmbedding 实例。

    Raises:
        ValueError: 未知 provider 时，错误信息包含 provider 名称。
    """
    provider = settings.embedding.provider.strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown Embedding provider: {provider}")
    return _PROVIDERS[provider](settings)


class EmbeddingFactory:
    """Embedding 工厂：按配置创建 BaseEmbedding 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseEmbedding:
        """根据 settings.embedding.provider 创建并返回对应 Embedding 实例。"""
        return create(settings)
