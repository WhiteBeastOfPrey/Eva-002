"""
Основные модули EVA Assistant
"""

from .eva_core import EVACore
from .platform_detector import PlatformDetector
from .speech_engine import SpeechEngine
from .wake_word_detector import WakeWordDetector
from .command_processor import CommandProcessor

__all__ = [
    'EVACore',
    'PlatformDetector', 
    'SpeechEngine',
    'WakeWordDetector',
    'CommandProcessor'
]