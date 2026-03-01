"""
LLM 工厂：根据配置选择 provider，创建对应 BaseLLM 实例。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.llm.base_llm import BaseLLM
from libs.llm.openai_llm import OpenAILLM
from libs.llm.azure_llm import AzureLLM
from libs.llm.deepseek_llm import DeepSeekLLM
from libs.llm.ollama_llm import OllamaLLM

# Provider 名称 -> 实现类（B7.1 openai/azure/deepseek，B7.2 ollama）
_PROVIDERS: Dict[str, Type[BaseLLM]] = {
    "openai": OpenAILLM,
    "azure": AzureLLM,
    "deepseek": DeepSeekLLM,
    "ollama": OllamaLLM,
}


def register_llm_provider(name: str, impl: Type[BaseLLM]) -> None:
    """注册 LLM provider，供实现模块或测试使用。"""
    _PROVIDERS[name] = impl


def create(settings: Settings) -> BaseLLM:
    """
    根据 settings.llm.provider 创建 LLM 实例。

    Args:
        settings: 主配置，含 settings.llm.provider 与 settings.llm.model。

    Returns:
        配置对应的 BaseLLM 实例。

    Raises:
        ValueError: 未知 provider 时，错误信息包含 provider 名称。
    """
    provider = settings.llm.provider.strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return _PROVIDERS[provider](settings)


class LLMFactory:
    """LLM 工厂：按配置创建 BaseLLM 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseLLM:
        """根据 settings.llm.provider 创建并返回对应 LLM 实例。"""
        return create(settings)
