"""
结构化日志占位。

A3 占位：提供 get_logger，stderr 输出。后续阶段补充 JSON Formatter、JSON Lines 等。
"""

import logging
import sys


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
