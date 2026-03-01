"""
Azure OpenAI 的 LLM 实现（OpenAI-compatible 接口，Azure 端点）。
"""

from typing import Any, Dict, List

from core.settings import Settings

from libs.llm.base_llm import BaseLLM

PROVIDER_NAME = "azure"


def _validate_messages(messages: List[Dict[str, Any]]) -> None:
    if not messages:
        raise ValueError(f"{PROVIDER_NAME}: messages 不能为空")
    if not isinstance(messages, list):
        raise ValueError(f"{PROVIDER_NAME}: messages 必须为 list，当前为 {type(messages).__name__}")
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError(f"{PROVIDER_NAME}: messages[{i}] 必须为 dict")
        if "content" not in m and "role" not in m:
            raise ValueError(f"{PROVIDER_NAME}: messages[{i}] 需含 role 与 content")


class AzureLLM(BaseLLM):
    """Azure OpenAI 的 LLM 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.llm.model
        self._api_key = (settings.llm.api_key or "").strip() or None
        self._base_url = (settings.llm.azure_endpoint or "").strip()
        if self._base_url and not self._base_url.endswith("/"):
            self._base_url = self._base_url.rstrip("/")
        # Azure 格式: https://xxx.openai.azure.com/openai/deployments/DEPLOYMENT_NAME
        self._api_version = (settings.llm.api_version or "2024-02-15-preview").strip()
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AzureOpenAI
            except ImportError as e:
                raise RuntimeError(f"{PROVIDER_NAME}: 需要 openai 包") from e
            self._client = AzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._base_url or None,
                api_version=self._api_version,
            )
        return self._client

    def chat(self, messages: List[Dict[str, Any]]) -> str:
        _validate_messages(messages)
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            choice = resp.choices[0] if resp.choices else None
            if not choice or not getattr(choice, "message", None):
                return ""
            return (choice.message.content or "").strip()
        except Exception as e:
            err_msg = str(e).replace(self._api_key or "", "***") if self._api_key else str(e)
            raise ValueError(f"{PROVIDER_NAME}: {type(e).__name__} — {err_msg}") from e
