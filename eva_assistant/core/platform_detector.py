"""
Модуль для автоматического определения платформы
Поддержка Windows x64 и macOS
"""

import platform
import sys
import logging
from enum import Enum
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SupportedPlatform(Enum):
    """Поддерживаемые платформы"""
    WINDOWS_X64 = "windows_x64"
    MACOS = "macos"
    LINUX = "linux"
    UNSUPPORTED = "unsupported"


class PlatformDetector:
    """Класс для определения текущей платформы и её характеристик"""
    
    def __init__(self):
        self.current_platform = self._detect_platform()
        self.platform_config = self._get_platform_config()
        logger.info(f"Detected platform: {self.current_platform.value}")
    
    def _detect_platform(self) -> SupportedPlatform:
        """Определить текущую платформу"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "windows":
            if machine in ["amd64", "x86_64"]:
                return SupportedPlatform.WINDOWS_X64
            else:
                logger.warning(f"Unsupported Windows architecture: {machine}")
                return SupportedPlatform.UNSUPPORTED
        
        elif system == "darwin":
            return SupportedPlatform.MACOS
        
        elif system == "linux":
            logger.info("Linux detected - partial support")
            return SupportedPlatform.LINUX
        
        else:
            logger.error(f"Unsupported platform: {system}")
            return SupportedPlatform.UNSUPPORTED
    
    def _get_platform_config(self) -> Dict[str, Any]:
        """Получить конфигурацию для текущей платформы"""
        configs = {
            SupportedPlatform.WINDOWS_X64: {
                "input_module": "pydirectinput",
                "process_module": "psutil",
                "audio_backend": "wasapi",
                "hotkey_module": "keyboard",
                "file_separator": "\\",
                "config_dir": "AppData/Roaming/EVA_Assistant",
                "supports_global_hotkeys": True,
                "supports_process_injection": True
            },
            SupportedPlatform.MACOS: {
                "input_module": "pynput",
                "process_module": "psutil", 
                "audio_backend": "coreaudio",
                "hotkey_module": "pynput",
                "file_separator": "/",
                "config_dir": "~/Library/Application Support/EVA_Assistant",
                "supports_global_hotkeys": True,
                "supports_process_injection": False
            },
            SupportedPlatform.LINUX: {
                "input_module": "pynput",
                "process_module": "psutil",
                "audio_backend": "pulse",
                "hotkey_module": "keyboard",
                "file_separator": "/",
                "config_dir": "~/.config/eva_assistant",
                "supports_global_hotkeys": True,
                "supports_process_injection": False
            },
            SupportedPlatform.UNSUPPORTED: {
                "input_module": None,
                "process_module": None,
                "audio_backend": None,
                "hotkey_module": None,
                "file_separator": "/",
                "config_dir": "~/.eva_assistant",
                "supports_global_hotkeys": False,
                "supports_process_injection": False
            }
        }
        
        return configs.get(self.current_platform, configs[SupportedPlatform.UNSUPPORTED])
    
    def is_supported(self) -> bool:
        """Проверить, поддерживается ли текущая платформа"""
        return self.current_platform != SupportedPlatform.UNSUPPORTED
    
    def get_platform_info(self) -> Dict[str, str]:
        """Получить информацию о платформе"""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "detected_platform": self.current_platform.value
        }
    
    def get_config_value(self, key: str, default=None):
        """Получить значение конфигурации для текущей платформы"""
        return self.platform_config.get(key, default)
    
    def supports_feature(self, feature: str) -> bool:
        """Проверить поддержку функции на текущей платформе"""
        feature_key = f"supports_{feature}"
        return self.platform_config.get(feature_key, False)