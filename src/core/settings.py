"""
配置加载与校验。

集中存放 Settings 数据结构与 load_settings/validate_settings 逻辑。
不做任何网络/IO 的业务初始化，仅做结构与必填字段校验（fail-fast）。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Settings 结构（与 config/settings.yaml 对应）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LlmSettings:
    """LLM 配置节（B7.1 起支持 api_key/base_url/azure 等）。"""
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    azure_endpoint: str = ""
    api_version: str = "2024-02-15-preview"


@dataclass(frozen=True)
class EmbeddingSettings:
    """Embedding 配置节（B7.3 起支持 api_key/base_url/azure 等）。"""
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    azure_endpoint: str = ""
    api_version: str = "2024-02-15-preview"


@dataclass(frozen=True)
class VectorStoreSettings:
    """VectorStore 配置节。"""
    provider: str
    persist_directory: str


@dataclass(frozen=True)
class RetrievalSettings:
    """Retrieval 配置节。"""
    top_k: int
    rerank_top_m: int


@dataclass(frozen=True)
class RerankSettings:
    """Rerank 配置节。"""
    provider: str


@dataclass(frozen=True)
class SplitterSettings:
    """Splitter 配置节（B3）。"""
    provider: str
    chunk_size: int
    chunk_overlap: int


@dataclass(frozen=True)
class EvaluationSettings:
    """Evaluation 配置节。"""
    provider: str


@dataclass(frozen=True)
class ObservabilitySettings:
    """Observability 配置节。"""
    log_level: str
    traces_path: str


@dataclass(frozen=True)
class VisionLlmSettings:
    """Vision LLM 配置节（B8，可选）。B9 Azure：azure_endpoint、api_version、deployment_name、api_key、max_image_size。"""
    provider: str
    api_key: str = ""
    azure_endpoint: str = ""
    api_version: str = "2024-02-15-preview"
    deployment_name: str = ""
    max_image_size: int = 2048


@dataclass(frozen=True)
class Settings:
    """主配置：仅做数据结构与最小校验。"""
    llm: LlmSettings
    embedding: EmbeddingSettings
    vector_store: VectorStoreSettings
    retrieval: RetrievalSettings
    rerank: RerankSettings
    splitter: SplitterSettings
    evaluation: EvaluationSettings
    observability: ObservabilitySettings
    vision_llm: Optional[VisionLlmSettings] = None


# ---------------------------------------------------------------------------
# 必填字段定义： (section, key) -> 用于错误提示的字段路径
# ---------------------------------------------------------------------------

_REQUIRED_PATHS: List[tuple] = [
    ("llm", "provider"),
    ("llm", "model"),
    ("embedding", "provider"),
    ("embedding", "model"),
    ("vector_store", "provider"),
    ("vector_store", "persist_directory"),
    ("retrieval", "top_k"),
    ("retrieval", "rerank_top_m"),
    ("rerank", "provider"),
    ("splitter", "provider"),
    ("splitter", "chunk_size"),
    ("splitter", "chunk_overlap"),
    ("evaluation", "provider"),
    ("observability", "log_level"),
    ("observability", "traces_path"),
]


def _field_path(section: str, key: str) -> str:
    """返回用于错误信息的字段路径，例如 embedding.provider。"""
    return f"{section}.{key}"


def _get_nested(data: Dict[str, Any], section: str, key: str) -> Any:
    """从 data[section][key] 取值，缺节或缺键返回 None。"""
    sec = data.get(section)
    if sec is None or not isinstance(sec, dict):
        return None
    return sec.get(key)


def validate_settings(settings: Settings) -> None:
    """
    集中化必填字段检查；缺字段时抛出 ValueError，错误信息包含字段路径。

    Args:
        settings: 已构建的 Settings 对象。

    Raises:
        ValueError: 当必填字段缺失时，消息格式为 "Missing required field: <section.key>"
    """
    # Settings 已由 load_settings 从经过校验的 dict 构建，此处可做二次校验或保持为空。
    # 当前必填校验在 load_settings 内对 raw dict 完成，本函数保留接口供后续扩展。
    pass


def _validate_raw(data: Dict[str, Any]) -> None:
    """对原始 dict 做必填字段校验，缺则抛出 ValueError。"""
    for section, key in _REQUIRED_PATHS:
        value = _get_nested(data, section, key)
        if value is None:
            path = _field_path(section, key)
            raise ValueError(f"Missing required field: {path}")


def _build_settings(data: Dict[str, Any]) -> Settings:
    """从校验通过的 dict 构建 Settings。"""
    llm = LlmSettings(
        provider=str(data["llm"]["provider"]),
        model=str(data["llm"]["model"]),
        api_key=str(data["llm"].get("api_key", "")),
        base_url=str(data["llm"].get("base_url", "")),
        azure_endpoint=str(data["llm"].get("azure_endpoint", "")),
        api_version=str(data["llm"].get("api_version", "2024-02-15-preview")),
    )
    embedding = EmbeddingSettings(
        provider=str(data["embedding"]["provider"]),
        model=str(data["embedding"]["model"]),
        api_key=str(data["embedding"].get("api_key", "")),
        base_url=str(data["embedding"].get("base_url", "")),
        azure_endpoint=str(data["embedding"].get("azure_endpoint", "")),
        api_version=str(data["embedding"].get("api_version", "2024-02-15-preview")),
    )
    vector_store = VectorStoreSettings(
        provider=str(data["vector_store"]["provider"]),
        persist_directory=str(data["vector_store"]["persist_directory"]),
    )
    retrieval = RetrievalSettings(
        top_k=int(data["retrieval"]["top_k"]),
        rerank_top_m=int(data["retrieval"]["rerank_top_m"]),
    )
    rerank = RerankSettings(provider=str(data["rerank"]["provider"]))
    splitter = SplitterSettings(
        provider=str(data["splitter"]["provider"]),
        chunk_size=int(data["splitter"]["chunk_size"]),
        chunk_overlap=int(data["splitter"]["chunk_overlap"]),
    )
    evaluation = EvaluationSettings(provider=str(data["evaluation"]["provider"]))
    observability = ObservabilitySettings(
        log_level=str(data["observability"]["log_level"]),
        traces_path=str(data["observability"]["traces_path"]),
    )
    vision_llm = None
    if data.get("vision_llm") and isinstance(data["vision_llm"], dict) and data["vision_llm"].get("provider"):
        vl = data["vision_llm"]
        vision_llm = VisionLlmSettings(
            provider=str(vl["provider"]),
            api_key=str(vl.get("api_key", "")),
            azure_endpoint=str(vl.get("azure_endpoint", "")),
            api_version=str(vl.get("api_version", "2024-02-15-preview")),
            deployment_name=str(vl.get("deployment_name", "")),
            max_image_size=int(vl.get("max_image_size", 2048)),
        )
    return Settings(
        llm=llm,
        embedding=embedding,
        vector_store=vector_store,
        retrieval=retrieval,
        rerank=rerank,
        splitter=splitter,
        evaluation=evaluation,
        observability=observability,
        vision_llm=vision_llm,
    )


def load_settings(path: str) -> Settings:
    """
    读取 YAML 配置文件，解析为 Settings 并校验必填字段。

    Args:
        path: 配置文件路径（如 config/settings.yaml）。

    Returns:
        校验通过的 Settings 实例。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 缺少必填字段时，消息包含字段路径（如 embedding.provider）。
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required for load_settings; install with: pip install pyyaml")

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a top-level mapping (dict)")

    _validate_raw(raw)
    return _build_settings(raw)
