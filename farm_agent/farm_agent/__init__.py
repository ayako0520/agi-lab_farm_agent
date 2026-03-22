"""圃場向けデータ取得・HTML レポート・任意で LLM ツール自律モード。"""

from pathlib import Path

from dotenv import load_dotenv

# リポジトリ直下（requirements.txt と同じ階層）の .env を読み込む。
# `python -m farm_agent.cli` 以外から import した場合も OPENAI_API_KEY 等が使えるようにする。
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

__version__ = "0.1.0"
