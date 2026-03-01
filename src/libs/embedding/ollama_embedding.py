"""
Ollama 本地 HTTP API 的 Embedding 实现。

支持默认 base_url（http://localhost:11434）与可配置 model；
批量 embed(texts) 通过 /api/embed，连接失败/超时抛出可读错误且不泄露敏感配置。
"""

import json
import urllib.error
import urllib.request
from typing import Any, List, Optional

from core.settings import Settings

from libs.embedding.base_embedding import BaseEmbedding

PROVIDER_NAME = "ollama"
DEFAULT_BASE_URL = "http://localhost:11434"


def _validate_texts(texts: List[str]) -> None:
    """校验 texts 非空且为字符串列表，不合格则抛出 ValueError。"""
    if not texts:
        raise ValueError(f"{PROVIDER_NAME}: texts 不能为空")
    if not isinstance(texts, list):
        raise ValueError(
            f"{PROVIDER_NAME}: texts 必须为 list，当前为 {type(texts).__name__}"
        )
    for i, t in enumerate(texts):
        if not isinstance(t, str):
            raise ValueError(
                f"{PROVIDER_NAME}: texts[{i}] 必须为 str，当前为 {type(t).__name__}"
            )


def _readable_error(exc: Exception) -> str:
    """将连接/超时等异常转为可读信息，不包含 URL 或敏感配置。"""
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if reason is not None:
            err_str = str(reason)
            if "timed out" in err_str.lower() or "timeout" in err_str.lower():
                return "连接超时"
            if "connection refused" in err_str.lower() or "refused" in err_str.lower():
                return "连接被拒绝（请确认 Ollama 服务已启动）"
        return "网络请求失败"
    if isinstance(exc, TimeoutError):
        return "连接超时"
    return type(exc).__name__ + (" — " + str(exc) if str(exc) else "")


class OllamaEmbedding(BaseEmbedding):
    """Ollama 本地 HTTP API 的 Embedding 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.embedding.model
        base = (settings.embedding.base_url or "").strip()
        self._base_url = base if base else DEFAULT_BASE_URL
        self._base_url = self._base_url.rstrip("/")

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        _validate_texts(texts)
        url = f"{self._base_url}/api/embed"
        body = json.dumps(
            {"model": self._model, "input": texts},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            readable = _readable_error(e)
            raise ValueError(f"{PROVIDER_NAME}: {readable}") from e
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(
                f"{PROVIDER_NAME}: 响应解析失败 — {type(e).__name__}"
            ) from e
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError(
                f"{PROVIDER_NAME}: 返回向量数与输入文本数不一致"
            )
        return [list(v) if isinstance(v, list) else [] for v in embeddings]
