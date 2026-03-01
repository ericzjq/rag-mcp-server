"""
Splitter 工厂：根据配置选择 provider，创建对应 BaseSplitter 实例。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.splitter.base_splitter import BaseSplitter
from libs.splitter.recursive_splitter import RecursiveSplitter

# Provider 名称 -> 实现类（B7.5 recursive，测试中可注册 Fake）
_PROVIDERS: Dict[str, Type[BaseSplitter]] = {
    "recursive": RecursiveSplitter,
}


def register_splitter_provider(name: str, impl: Type[BaseSplitter]) -> None:
    """注册 Splitter provider，供实现模块或测试使用。"""
    _PROVIDERS[name] = impl


def create(settings: Settings) -> BaseSplitter:
    """
    根据 settings.splitter.provider 创建 Splitter 实例。

    Args:
        settings: 主配置，含 settings.splitter.provider、chunk_size、chunk_overlap。

    Returns:
        配置对应的 BaseSplitter 实例。

    Raises:
        ValueError: 未知 provider 时，错误信息包含 provider 名称。
    """
    provider = settings.splitter.provider.strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown Splitter provider: {provider}")
    return _PROVIDERS[provider](settings)


class SplitterFactory:
    """Splitter 工厂：按配置创建 BaseSplitter 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseSplitter:
        """根据 settings.splitter.provider 创建并返回对应 Splitter 实例。"""
        return create(settings)
