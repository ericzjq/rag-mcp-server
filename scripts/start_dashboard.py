#!/usr/bin/env python3
"""
Dashboard 启动脚本（G1）：从项目根目录启动 Streamlit，确保 config/settings.yaml 可读。
"""

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
os.chdir(_ROOT)
app_path = _ROOT / "src" / "observability" / "dashboard" / "app.py"

def main() -> int:
    r = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless", "true"],
        cwd=str(_ROOT),
    )
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
