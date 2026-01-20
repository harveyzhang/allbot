"""bot_core 模块 - 重构后的模块化版本

向后兼容：保持 `from bot_core import bot_core` 可用
"""
from bot_core.orchestrator import bot_core

__all__ = ["bot_core"]
