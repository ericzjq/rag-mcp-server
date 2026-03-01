"""
Azure OpenAI 的 Embedding 实现。

支持 endpoint、api-version、api-key 配置，部署名通过 model 指定（如 text-embedding-ada-002）。
批量 embed(texts)，空输入抛出 ValueError，行为与 OpenAI 实现一致。
"""

from typing import Any, List, Optional

from core.settings import Settings

from libs.embedding.base_embedding import BaseEmbedding

PROVIDER_NAME = "azure"


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


class AzureEmbedding(BaseEmbedding):
    """Azure OpenAI 的 Embedding 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.embedding.model  # Azure 部署名
        self._api_key = (settings.embedding.api_key or "").strip() or None
        endpoint = (settings.embedding.azure_endpoint or "").strip()
        if endpoint and not endpoint.endswith("/"):
            endpoint = endpoint.rstrip("/")
        self._azure_endpoint = endpoint or None
        self._api_version = (
            (settings.embedding.api_version or "2024-02-15-preview").strip()
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AzureOpenAI
            except ImportError as e:
                raise RuntimeError(
                    f"{PROVIDER_NAME}: 需要 openai 包，请 pip install openai"
                ) from e
            self._client = AzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._azure_endpoint,
                api_version=self._api_version,
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
