"""
Основной модуль EVA Assistant - координирует работу всех компонентов
"""

import asyncio
import logging
import signal
import sys
from typing import Optional, Callable, Dict, Any
from enum import Enum

from .platform_detector import PlatformDetector
from .wake_word_detector import WakeWordDetector
from .speech_engine import SpeechEngine, RecognitionMode
from .command_processor import CommandProcessor
from ..modules.input_controller import InputController

logger = logging.getLogger(__name__)


class EVAState(Enum):
    """Состояния EVA Assistant"""
    STOPPED = "stopped"
    INITIALIZING = "initializing"
    LISTENING_WAKE_WORD = "listening_wake_word"
    LISTENING_COMMAND = "listening_command"
    PROCESSING_COMMAND = "processing_command"
    EXECUTING_COMMAND = "executing_command"
    ERROR = "error"


class EVACore:
    """Основной класс EVA Assistant"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.state = EVAState.STOPPED
        
        # Компоненты
        self.platform_detector: Optional[PlatformDetector] = None
        self.wake_word_detector: Optional[WakeWordDetector] = None
        self.speech_engine: Optional[SpeechEngine] = None
        self.command_processor: Optional[CommandProcessor] = None
        self.input_controller: Optional[InputController] = None
        
        # Настройки
        self.is_online_mode = self.config.get('online_mode', True)
        self.wake_word_threshold = self.config.get('wake_word_threshold', 65)
        self.command_threshold = self.config.get('command_threshold', 65)
        self.command_timeout = self.config.get('command_timeout', 5.0)
        
        # Callbacks для GUI
        self.on_state_changed: Optional[Callable] = None
        self.on_wake_word_detected: Optional[Callable] = None
        self.on_speech_recognized: Optional[Callable] = None
        self.on_command_executed: Optional[Callable] = None
        self.on_audio_level: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Статистика
        self.stats = {
            'wake_words_detected': 0,
            'commands_recognized': 0,
            'commands_executed': 0,
            'commands_failed': 0,
            'uptime': 0
        }
        
        logger.info("EVA Core initialized")
    
    async def initialize(self) -> bool:
        """Инициализация всех компонентов"""
        try:
            self._set_state(EVAState.INITIALIZING)
            
            # Проверка платформы
            self.platform_detector = PlatformDetector()
            if not self.platform_detector.is_supported():
                raise Exception(f"Unsupported platform: {self.platform_detector.current_platform.value}")
            
            logger.info(f"Platform detected: {self.platform_detector.current_platform.value}")
            
            # Инициализация контроллера ввода
            self.input_controller = InputController()
            if not self.input_controller.is_available():
                logger.warning("Input controller not available")
            
            # Инициализация движка речи
            mode = RecognitionMode.ONLINE if self.is_online_mode else RecognitionMode.OFFLINE
            self.speech_engine = SpeechEngine(mode)
            self.speech_engine.set_callbacks(
                on_speech_start=self._on_speech_start,
                on_speech_end=self._on_speech_end,
                on_text_recognized=self._on_text_recognized,
                on_audio_level=self._on_audio_level_callback
            )
            
            # Инициализация процессора команд
            commands_file = self.config.get('commands_file', 'commands.json')
            self.command_processor = CommandProcessor(commands_file, self.command_threshold)
            self.command_processor.set_callbacks(
                on_command_executed=self._on_command_executed,
                on_command_not_found=self._on_command_not_found
            )
            
            # Инициализация детектора wake-word
            wake_words = self.config.get('wake_words', ['ева', 'eva', 'эва'])
            self.wake_word_detector = WakeWordDetector(wake_words, self.wake_word_threshold)
            self.wake_word_detector.set_callback(self._on_wake_word_detected)
            
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize EVA Core: {e}")
            self._set_state(EVAState.ERROR)
            if self.on_error:
                await self._call_callback(self.on_error, f"Initialization failed: {e}")
            return False
    
    async def start(self) -> bool:
        """Запуск EVA Assistant"""
        try:
            if self.state != EVAState.STOPPED:
                logger.warning("EVA is already running")
                return False
            
            if not await self.initialize():
                return False
            
            # Запуск детектора wake-word
            await self.wake_word_detector.start_listening()
            self._set_state(EVAState.LISTENING_WAKE_WORD)
            
            logger.info("EVA Assistant started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start EVA: {e}")
            self._set_state(EVAState.ERROR)
            if self.on_error:
                await self._call_callback(self.on_error, f"Start failed: {e}")
            return False
    
    async def stop(self) -> bool:
        """Остановка EVA Assistant"""
        try:
            logger.info("Stopping EVA Assistant...")
            
            # Остановка всех компонентов
            if self.wake_word_detector:
                await self.wake_word_detector.stop_listening()
            
            if self.speech_engine:
                await self.speech_engine.stop_listening()
            
            self._set_state(EVAState.STOPPED)
            
            logger.info("EVA Assistant stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop EVA: {e}")
            return False
    
    async def force_stop(self) -> bool:
        """Принудительная остановка EVA Assistant"""
        logger.info("Force stopping EVA Assistant...")
        
        try:
            # Принудительная остановка всех компонентов
            if self.wake_word_detector:
                self.wake_word_detector.is_listening = False
            
            if self.speech_engine:
                self.speech_engine.is_listening = False
            
            self._set_state(EVAState.STOPPED)
            return True
            
        except Exception as e:
            logger.error(f"Failed to force stop EVA: {e}")
            return False
    
    async def _on_wake_word_detected(self, detected_text: str):
        """Обработка обнаружения wake-word"""
        try:
            logger.info(f"Wake word detected: {detected_text}")
            self.stats['wake_words_detected'] += 1
            
            if self.on_wake_word_detected:
                await self._call_callback(self.on_wake_word_detected, detected_text)
            
            # Переходим к прослушиванию команды
            self._set_state(EVAState.LISTENING_COMMAND)
            
            # Запускаем распознавание команды
            command_text = await self.speech_engine.recognize_once(self.command_timeout)
            
            if command_text:
                await self._process_command(command_text)
            else:
                logger.info("No command recognized, returning to wake word listening")
                self._set_state(EVAState.LISTENING_WAKE_WORD)
            
        except Exception as e:
            logger.error(f"Error processing wake word: {e}")
            self._set_state(EVAState.LISTENING_WAKE_WORD)
    
    async def _process_command(self, command_text: str):
        """Обработка распознанной команды"""
        try:
            self._set_state(EVAState.PROCESSING_COMMAND)
            logger.info(f"Processing command: {command_text}")
            
            self.stats['commands_recognized'] += 1
            
            # Ищем подходящую команду
            command = await self.command_processor.process_text(command_text)
            
            if command:
                # Выполняем команду
                self._set_state(EVAState.EXECUTING_COMMAND)
                success = await self.command_processor.execute_command(command)
                
                if success:
                    self.stats['commands_executed'] += 1
                    logger.info(f"Command '{command.name}' executed successfully")
                else:
                    self.stats['commands_failed'] += 1
                    logger.warning(f"Failed to execute command '{command.name}'")
            else:
                self.stats['commands_failed'] += 1
                logger.info(f"No matching command found for: {command_text}")
            
            # Возвращаемся к прослушиванию wake-word
            self._set_state(EVAState.LISTENING_WAKE_WORD)
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            self.stats['commands_failed'] += 1
            self._set_state(EVAState.LISTENING_WAKE_WORD)
    
    async def _on_speech_start(self):
        """Callback начала речи"""
        logger.debug("Speech started")
    
    async def _on_speech_end(self):
        """Callback окончания речи"""
        logger.debug("Speech ended")
    
    async def _on_text_recognized(self, text: str):
        """Callback распознанного текста"""
        logger.debug(f"Text recognized: {text}")
        if self.on_speech_recognized:
            await self._call_callback(self.on_speech_recognized, text)
    
    async def _on_audio_level_callback(self, level: float):
        """Callback уровня аудио"""
        if self.on_audio_level:
            await self._call_callback(self.on_audio_level, level)
    
    async def _on_command_executed(self, command):
        """Callback выполненной команды"""
        if self.on_command_executed:
            await self._call_callback(self.on_command_executed, command)
    
    async def _on_command_not_found(self, text: str):
        """Callback когда команда не найдена"""
        logger.debug(f"Command not found for: {text}")
    
    def _set_state(self, new_state: EVAState):
        """Изменить состояние EVA"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"State changed: {old_state.value} -> {new_state.value}")
            
            if self.on_state_changed:
                asyncio.create_task(self._call_callback(self.on_state_changed, new_state))
    
    async def _call_callback(self, callback: Callable, *args):
        """Безопасный вызов callback функции"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def set_callbacks(self, **callbacks):
        """Установить callback функции"""
        self.on_state_changed = callbacks.get('on_state_changed')
        self.on_wake_word_detected = callbacks.get('on_wake_word_detected')
        self.on_speech_recognized = callbacks.get('on_speech_recognized')
        self.on_command_executed = callbacks.get('on_command_executed')
        self.on_audio_level = callbacks.get('on_audio_level')
        self.on_error = callbacks.get('on_error')
    
    def set_online_mode(self, online: bool):
        """Изменить режим работы (онлайн/оффлайн)"""
        self.is_online_mode = online
        if self.speech_engine:
            mode = RecognitionMode.ONLINE if online else RecognitionMode.OFFLINE
            self.speech_engine.set_mode(mode)
        logger.info(f"Mode changed to: {'online' if online else 'offline'}")
    
    def set_wake_word_threshold(self, threshold: int):
        """Установить порог для wake-word"""
        self.wake_word_threshold = threshold
        if self.wake_word_detector:
            self.wake_word_detector.threshold = threshold
        logger.info(f"Wake word threshold set to: {threshold}%")
    
    def set_command_threshold(self, threshold: int):
        """Установить порог для команд"""
        self.command_threshold = threshold
        if self.command_processor:
            self.command_processor.set_threshold(threshold)
        logger.info(f"Command threshold set to: {threshold}%")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус EVA Assistant"""
        return {
            'state': self.state.value,
            'online_mode': self.is_online_mode,
            'wake_word_threshold': self.wake_word_threshold,
            'command_threshold': self.command_threshold,
            'platform': self.platform_detector.current_platform.value if self.platform_detector else 'unknown',
            'components_status': {
                'wake_word_detector': self.wake_word_detector.get_status() if self.wake_word_detector else None,
                'speech_engine': self.speech_engine.get_status() if self.speech_engine else None,
                'command_processor': self.command_processor.get_statistics() if self.command_processor else None,
                'input_controller': self.input_controller.get_status() if self.input_controller else None
            },
            'statistics': self.stats.copy()
        }
    
    def get_commands(self):
        """Получить список команд"""
        if self.command_processor:
            return self.command_processor.get_all_commands()
        return []
    
    def add_command(self, command):
        """Добавить команду"""
        if self.command_processor:
            return self.command_processor.add_command(command)
        return False
    
    def remove_command(self, command_id: str):
        """Удалить команду"""
        if self.command_processor:
            return self.command_processor.remove_command(command_id)
        return False
    
    def update_command(self, command):
        """Обновить команду"""
        if self.command_processor:
            return self.command_processor.update_command(command)
        return False