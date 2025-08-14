"""
Система логирования для EVA Assistant
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Настройка системы логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Имя файла лога (по умолчанию eva_YYYYMMDD.log)
        log_dir: Директория для логов
        max_file_size: Максимальный размер файла лога в байтах
        backup_count: Количество резервных файлов
        console_output: Выводить ли логи в консоль
        log_format: Формат логирования
    
    Returns:
        Настроенный logger
    """
    
    # Создаем директорию для логов
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Определяем имя файла лога
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = f"eva_{timestamp}.log"
    
    log_filepath = log_path / log_file
    
    # Определяем формат логирования
    if log_format is None:
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        )
    
    # Создаем форматтер
    formatter = logging.Formatter(log_format)
    
    # Получаем root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Настройка файлового handler с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        log_filepath,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(file_handler)
    
    # Настройка консольного handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        logger.addHandler(console_handler)
    
    # Логируем информацию о настройке
    logger.info(f"Logging initialized - Level: {log_level}, File: {log_filepath}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить logger для модуля
    
    Args:
        name: Имя модуля
    
    Returns:
        Logger для модуля
    """
    return logging.getLogger(name)


class EVALogFilter(logging.Filter):
    """Фильтр для логов EVA Assistant"""
    
    def __init__(self, component: str = None):
        super().__init__()
        self.component = component
    
    def filter(self, record):
        """Фильтрация записей лога"""
        # Добавляем информацию о компоненте
        if self.component:
            record.component = self.component
        
        # Фильтруем чувствительную информацию
        if hasattr(record, 'msg'):
            # Скрываем потенциально чувствительные данные
            sensitive_patterns = ['password', 'token', 'key', 'secret']
            msg = str(record.msg).lower()
            
            for pattern in sensitive_patterns:
                if pattern in msg:
                    record.msg = record.msg.replace(
                        record.msg[msg.find(pattern):msg.find(pattern) + 20],
                        f"{pattern}=***HIDDEN***"
                    )
        
        return True


class PerformanceLogger:
    """Logger для отслеживания производительности"""
    
    def __init__(self, name: str):
        self.logger = get_logger(f"performance.{name}")
        self.start_times: Dict[str, float] = {}
    
    def start_timer(self, operation: str):
        """Начать отслеживание времени операции"""
        import time
        self.start_times[operation] = time.time()
        self.logger.debug(f"Started: {operation}")
    
    def end_timer(self, operation: str, details: str = ""):
        """Завершить отслеживание времени операции"""
        import time
        if operation in self.start_times:
            duration = time.time() - self.start_times[operation]
            self.logger.info(f"Completed: {operation} in {duration:.3f}s {details}")
            del self.start_times[operation]
        else:
            self.logger.warning(f"Timer for '{operation}' was not started")
    
    def log_metric(self, metric_name: str, value: Any, unit: str = ""):
        """Логировать метрику"""
        self.logger.info(f"Metric: {metric_name}={value} {unit}".strip())


class StructuredLogger:
    """Структурированный logger для JSON логов"""
    
    def __init__(self, name: str):
        self.logger = get_logger(f"structured.{name}")
    
    def log_event(self, event_type: str, data: Dict[str, Any], level: str = "INFO"):
        """Логировать структурированное событие"""
        import json
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        
        log_level = getattr(logging, level.upper())
        self.logger.log(log_level, json.dumps(log_entry, ensure_ascii=False))
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Логировать ошибку со структурированными данными"""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
        
        self.log_event("error", error_data, "ERROR")
    
    def log_performance(self, operation: str, duration: float, details: Dict[str, Any] = None):
        """Логировать информацию о производительности"""
        perf_data = {
            "operation": operation,
            "duration_seconds": duration,
            "details": details or {}
        }
        
        self.log_event("performance", perf_data, "INFO")


def setup_component_logger(
    component_name: str,
    log_level: str = "INFO",
    enable_performance: bool = False,
    enable_structured: bool = False
) -> Dict[str, Any]:
    """
    Настройка логгера для компонента EVA
    
    Args:
        component_name: Имя компонента
        log_level: Уровень логирования
        enable_performance: Включить performance logging
        enable_structured: Включить structured logging
    
    Returns:
        Словарь с логгерами
    """
    
    loggers = {
        "main": get_logger(component_name)
    }
    
    # Устанавливаем уровень логирования
    loggers["main"].setLevel(getattr(logging, log_level.upper()))
    
    # Добавляем фильтр компонента
    component_filter = EVALogFilter(component_name)
    loggers["main"].addFilter(component_filter)
    
    # Performance logger
    if enable_performance:
        loggers["performance"] = PerformanceLogger(component_name)
    
    # Structured logger
    if enable_structured:
        loggers["structured"] = StructuredLogger(component_name)
    
    return loggers


def log_system_info():
    """Логировать информацию о системе"""
    import platform
    import sys
    
    logger = get_logger("system")
    
    system_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "architecture": platform.architecture(),
        "processor": platform.processor(),
        "hostname": platform.node()
    }
    
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")


def configure_third_party_loggers():
    """Настройка логгеров сторонних библиотек"""
    
    # Уменьшаем уровень логирования для шумных библиотек
    noisy_loggers = [
        'urllib3.connectionpool',
        'requests.packages.urllib3',
        'asyncio',
        'concurrent.futures',
        'sounddevice'
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)


def create_debug_logger(name: str) -> logging.Logger:
    """Создать debug logger с детальным выводом"""
    
    logger = logging.getLogger(f"debug.{name}")
    logger.setLevel(logging.DEBUG)
    
    # Создаем отдельный handler для debug логов
    debug_handler = logging.StreamHandler(sys.stderr)
    debug_formatter = logging.Formatter(
        "DEBUG - %(asctime)s - %(name)s - [%(filename)s:%(lineno)d:%(funcName)s] - %(message)s"
    )
    debug_handler.setFormatter(debug_formatter)
    logger.addHandler(debug_handler)
    
    return logger


# Функции для быстрого логирования
def log_function_call(func):
    """Декоратор для логирования вызовов функций"""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper


def log_async_function_call(func):
    """Декоратор для логирования асинхронных вызовов функций"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")
        
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Async {func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"Async {func.__name__} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper