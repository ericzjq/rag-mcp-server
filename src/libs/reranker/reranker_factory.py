"""
Reranker 工厂：根据配置选择 provider，创建对应 BaseReranker 实例。
提供 NoneReranker 作为默认回退。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.reranker.base_reranker import BaseReranker
from libs.reranker.none_reranker import NoneReranker
from libs.reranker.llm_reranker import LLMReranker
from libs.reranker.cross_encoder_reranker import CrossEncoderReranker

# Provider 名称 -> 实现类（B7.7 llm，B7.8 cross_encoder，none 为默认回退）
_PROVIDERS: Dict[str, Type[BaseReranker]] = {
    "none": NoneReranker,
    "llm": LLMReranker,
    "cross_encoder": CrossEncoderReranker,
}


def register_reranker_provider(name: str, impl: Type[BaseReranker]) -> None:
    """注册 Reranker provider，供实现模块或测试使用。"""
    _PROVIDERS[name.lower()] = impl


def create(settings: Settings) -> BaseReranker:
    """
    根据 settings.rerank.provider 创建 Reranker 实例。

    Args:
        settings: 主配置，含 settings.rerank.provider。

    Returns:
        配置对应的 BaseReranker 实例。provider=none 时返回 NoneReranker（保持原序）。

    Raises:
        ValueError: 未知 provider 时，错误信息包含 provider 名称。
    """
    provider = settings.rerank.provider.strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown Reranker provider: {provider}")
    return _PROVIDERS[provider](settings)


class RerankerFactory:
    """Reranker 工厂：按配置创建 BaseReranker 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseReranker:
        """根据 settings.rerank.provider 创建并返回对应 Reranker 实例。"""
        return create(settings)
