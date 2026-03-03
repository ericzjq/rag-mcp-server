"""
Evaluator 工厂：根据配置选择 provider，创建对应 BaseEvaluator 实例。
"""

from typing import Dict, Type

from core.settings import Settings

from libs.evaluator.base_evaluator import BaseEvaluator
from libs.evaluator.custom_evaluator import CustomEvaluator

# Provider 名称 -> 实现类（H1 补齐 ragas）
_PROVIDERS: Dict[str, Type[BaseEvaluator]] = {
    "custom": CustomEvaluator,
}


def _register_ragas() -> None:
    """延迟注册 ragas，避免未安装时顶层导入失败。"""
    if "ragas" in _PROVIDERS:
        return
    try:
        from observability.evaluation.ragas_evaluator import RagasEvaluator
        _PROVIDERS["ragas"] = RagasEvaluator
    except ImportError:
        pass


def register_evaluator_provider(name: str, impl: Type[BaseEvaluator]) -> None:
    """注册 Evaluator provider。"""
    _PROVIDERS[name.lower()] = impl


def create(settings: Settings) -> BaseEvaluator:
    """
    根据 settings.evaluation.provider 创建 Evaluator 实例。

    Args:
        settings: 主配置，含 settings.evaluation.provider。

    Returns:
        配置对应的 BaseEvaluator 实例。

    Raises:
        ValueError: 未知或未实现的 provider 时，错误信息包含 provider 名称。
    """
    _register_ragas()
    provider = settings.evaluation.provider.strip().lower()
    if provider not in _PROVIDERS or _PROVIDERS[provider] is None:
        raise ValueError(f"Unknown or unimplemented Evaluator provider: {provider}")
    return _PROVIDERS[provider](settings)


class EvaluatorFactory:
    """Evaluator 工厂：按配置创建 BaseEvaluator 实例。"""

    @staticmethod
    def create(settings: Settings) -> BaseEvaluator:
        """根据 settings.evaluation.provider 创建并返回对应 Evaluator 实例。"""
        return create(settings)
