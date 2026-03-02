"""
结构化日志（A3 占位，F2 增强）：get_logger、JSONFormatter、get_trace_logger、write_trace。
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

_TRACES_DEFAULT_PATH = "logs/traces.jsonl"


class JSONFormatter(logging.Formatter):
    """输出单行 JSON，便于 JSON Lines 解析。"""

    def format(self, record: logging.LogRecord) -> str:
        obj: Dict[str, Any] = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """
    返回名为 name 的 Logger，配置为 stderr 输出。

    Args:
        name: 通常为 __name__。

    Returns:
        已配置的 Logger 实例。
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def get_trace_logger(name: str = "trace") -> logging.Logger:
    """获取配置了 JSON Lines 输出的 logger（JSONFormatter + stderr）。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(JSONFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


def write_trace(trace_dict: Dict[str, Any], path: Optional[str] = None) -> None:
    """将 trace 字典追加写入 logs/traces.jsonl（一行合法 JSON）。"""
    file_path = path or os.environ.get("TRACES_PATH", _TRACES_DEFAULT_PATH)
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace_dict, ensure_ascii=False) + "\n")
