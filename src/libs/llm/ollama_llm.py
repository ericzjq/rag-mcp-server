"""
Ollama 本地 HTTP API 的 LLM 实现。

支持默认 base_url（http://localhost:11434）与可配置 model；
连接失败/超时等场景抛出可读错误且不泄露敏感配置。
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

from core.settings import Settings

from libs.llm.base_llm import BaseLLM

PROVIDER_NAME = "ollama"
DEFAULT_BASE_URL = "http://localhost:11434"


def _validate_messages(messages: List[Dict[str, Any]]) -> None:
    """校验 messages 形状，不合格则抛出 ValueError。"""
    if not messages:
        raise ValueError(f"{PROVIDER_NAME}: messages 不能为空")
    if not isinstance(messages, list):
        raise ValueError(
            f"{PROVIDER_NAME}: messages 必须为 list，当前为 {type(messages).__name__}"
        )
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError(
                f"{PROVIDER_NAME}: messages[{i}] 必须为 dict，当前为 {type(m).__name__}"
            )
        if "content" not in m and "role" not in m:
            raise ValueError(f"{PROVIDER_NAME}: messages[{i}] 需含 role 与 content")


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


class OllamaLLM(BaseLLM):
    """Ollama 本地 HTTP API 的 LLM 实现。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.llm.model
        base = (settings.llm.base_url or "").strip()
        self._base_url = base if base else DEFAULT_BASE_URL
        self._base_url = self._base_url.rstrip("/")

    def chat(self, messages: List[Dict[str, Any]]) -> str:
        _validate_messages(messages)
        url = f"{self._base_url}/api/chat"
        body = json.dumps(
            {"model": self._model, "messages": messages, "stream": False},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            readable = _readable_error(e)
            raise ValueError(f"{PROVIDER_NAME}: {readable}") from e
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"{PROVIDER_NAME}: 响应解析失败 — {type(e).__name__}") from e
        msg = data.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        return (content or "").strip()
