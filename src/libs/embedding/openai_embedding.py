"""
OpenAI 官方 API 的 Embedding 实现。

支持 text-embedding-3-small/large 等模型，批量 embed(texts)。
空输入抛出 ValueError，异常信息包含 provider。
"""

from typing import Any, List, Optional

from core.settings import Settings

from libs.embedding.base_embedding import BaseEmbedding

PROVIDER_NAME = "openai"


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


class OpenAIEmbedding(BaseEmbedding):
    """OpenAI 官方 API 的 Embedding 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.embedding.model
        self._api_key = (settings.embedding.api_key or "").strip() or None
        self._base_url = (settings.embedding.base_url or "").strip() or None
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(
                    f"{PROVIDER_NAME}: 需要 openai 包，请 pip install openai"
                ) from e
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url or None,
            )
        return self._client

    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
    ) -> List[List[float]]:
        _validate_texts(texts)
        try:
            client = self._get_client()
            resp = client.embeddings.create(model=self._model, input=texts)
            # 按 index 排序以与输入顺序一致
            items = sorted(resp.data, key=lambda x: getattr(x, "index", 0))
            out = [list(item.embedding) for item in items]
            if len(out) != len(texts):
                raise ValueError(
                    f"{PROVIDER_NAME}: 返回向量数 {len(out)} 与输入文本数 {len(texts)} 不一致"
                )
            return out
        except Exception as e:
            err_msg = str(e).replace(self._api_key or "", "***") if self._api_key else str(e)
            raise ValueError(f"{PROVIDER_NAME}: {type(e).__name__} — {err_msg}") from e
