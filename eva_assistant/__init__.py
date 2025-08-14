"""
EVA Voice Assistant - Голосовой ассистент с поддержкой wake-word
Модульная архитектура для Windows x64 и macOS
"""

__version__ = "1.0.0"
__author__ = "EVA Assistant Team"

from .core import EVACore
from .gui import EVAMainWindow

__all__ = ['EVACore', 'EVAMainWindow']