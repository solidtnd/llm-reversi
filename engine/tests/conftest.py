"""テスト共通の設定。

`tests/fakes.py` をサブディレクトリのテスト(`tests/adapters/` など)からも
`import fakes` で読めるように、tests ディレクトリを sys.path に追加する。
"""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
