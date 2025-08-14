#!/usr/bin/env python3
"""
EVA Assistant - Голосовой ассистент с wake-word детекцией
Главный файл для запуска приложения
"""

import sys
import asyncio
import logging
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from eva_assistant.modules.logger_config import setup_logging, log_system_info, configure_third_party_loggers
from eva_assistant.gui.main_window import main as gui_main


def main():
    """Главная функция"""
    try:
        # Настройка логирования
        setup_logging(
            log_level="INFO",
            log_dir="logs",
            console_output=True
        )
        
        # Настройка логгеров сторонних библиотек
        configure_third_party_loggers()
        
        # Логируем информацию о системе
        log_system_info()
        
        logger = logging.getLogger(__name__)
        logger.info("Starting EVA Assistant...")
        
        # Запуск GUI
        exit_code = gui_main()
        
        logger.info(f"EVA Assistant finished with exit code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        print("\nПрерывание пользователем")
        return 0
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        logging.exception("Critical error in main")
        return 1


if __name__ == "__main__":
    sys.exit(main())