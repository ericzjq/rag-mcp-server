"""
DeepSeek API 的 LLM 实现（OpenAI-compatible）。
"""

from typing import Any, Dict, List

from core.settings import Settings

from libs.llm.base_llm import BaseLLM

PROVIDER_NAME = "deepseek"

DEFAULT_BASE_URL = "https://api.deepseek.com"


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


class DeepSeekLLM(BaseLLM):
    """DeepSeek API（OpenAI-compatible）的 LLM 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.llm.model
        self._api_key = (settings.llm.api_key or "").strip() or None
        self._base_url = (settings.llm.base_url or "").strip() or DEFAULT_BASE_URL
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(f"{PROVIDER_NAME}: 需要 openai 包") from e
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
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
