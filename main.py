#!/usr/bin/env python3
"""
MCP Server 启动入口。

启动时加载 config/settings.yaml，缺字段则 fail-fast 退出。
"""

import sys
from pathlib import Path

# 确保项目根在 path 中（便于以 python main.py 或 python -m 方式运行）
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.settings import load_settings, validate_settings


def main() -> None:
    """入口：加载配置并校验，后续将启动 MCP Server。"""
    config_path = _root / "config" / "settings.yaml"
    try:
        settings = load_settings(str(config_path))
        validate_settings(settings)
    except FileNotFoundError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Config validation error: {e}", file=sys.stderr)
        sys.exit(1)
    # 当前仅占位：配置已就绪，后续阶段在此启动 Server
    print("MCP Server config loaded successfully.")


if __name__ == "__main__":
    main()
