"""OpenAI API の共通設定（.env で上書き可）。"""

from __future__ import annotations

import os


def openai_chat_model() -> str:
    """Chat Completions で使うモデル ID。例: gpt-4o-mini, gpt-4o, o4-mini 等（公式の利用可能モデルに従う）。"""
    m = os.environ.get("FARM_AGENT_OPENAI_MODEL", "gpt-4o-mini").strip()
    return m or "gpt-4o-mini"
