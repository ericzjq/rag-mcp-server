"""
ConfigService（G1）：封装 Settings 读取，格式化组件配置信息供 Dashboard 展示。
"""

import os
from typing import Any, Dict, List, Optional

from core.settings import Settings, load_settings


def get_config_display(settings: Settings) -> List[Dict[str, Any]]:
    """
    将 Settings 转为可展示的组件卡片列表，每项含 title 与 items (key, value)。
    敏感字段（api_key）以掩码显示。
    """
    def _mask(s: str) -> str:
        if not s or len(s) < 4:
            return "***" if s else "-"
        return s[:2] + "***" + s[-2:] if len(s) > 4 else "***"

    cards: List[Dict[str, Any]] = []

    cards.append({
        "title": "LLM",
        "items": [
            ("provider", settings.llm.provider),
            ("model", settings.llm.model),
            ("api_key", _mask(settings.llm.api_key)),
        ],
    })
    cards.append({
        "title": "Embedding",
        "items": [
            ("provider", settings.embedding.provider),
            ("model", settings.embedding.model),
            ("api_key", _mask(settings.embedding.api_key)),
        ],
    })
    cards.append({
        "title": "VectorStore",
        "items": [
            ("provider", settings.vector_store.provider),
            ("persist_directory", settings.vector_store.persist_directory),
        ],
    })
    cards.append({
        "title": "Retrieval",
        "items": [
            ("top_k", str(settings.retrieval.top_k)),
            ("rerank_top_m", str(settings.retrieval.rerank_top_m)),
        ],
    })
    cards.append({
        "title": "Reranker",
        "items": [("provider", settings.rerank.provider)],
    })
    cards.append({
        "title": "Splitter",
        "items": [
            ("provider", settings.splitter.provider),
            ("chunk_size", str(settings.splitter.chunk_size)),
            ("chunk_overlap", str(settings.splitter.chunk_overlap)),
        ],
    })
    cards.append({
        "title": "Observability",
        "items": [
            ("log_level", settings.observability.log_level),
            ("traces_path", settings.observability.traces_path),
        ],
    })
    return cards


class ConfigService:
    """配置读取服务：从默认或指定路径加载 Settings，提供展示用结构。"""

    def __init__(self, config_path: Optional[str] = None, work_dir: Optional[str] = None) -> None:
        self._config_path = config_path or os.environ.get("MCP_CONFIG_PATH", "config/settings.yaml")
        self._work_dir = work_dir or os.getcwd()
        self._settings: Optional[Settings] = None

    def load(self) -> Optional[Settings]:
        """加载配置；失败返回 None。"""
        path = self._config_path
        if not os.path.isabs(path):
            path = os.path.join(self._work_dir, path)
        if not os.path.isfile(path):
            return None
        try:
            self._settings = load_settings(path)
            return self._settings
        except Exception:
            return None

    def get_settings(self) -> Optional[Settings]:
        """返回已加载的 Settings；未加载则先 load。"""
        if self._settings is None:
            self.load()
        return self._settings

    def get_component_cards(self) -> List[Dict[str, Any]]:
        """返回组件配置卡片列表，供总览页展示。未加载配置时返回空列表。"""
        s = self.get_settings()
        if s is None:
            return []
        return get_config_display(s)
