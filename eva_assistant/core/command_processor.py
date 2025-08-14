"""
Процессор команд с нечетким сравнением через fuzzywuzzy
"""

import asyncio
import logging
import json
import os
from typing import Dict, List, Optional, Callable, Any, Tuple
from fuzzywuzzy import fuzz, process
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Типы действий команд"""
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    PROCESS = "process"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class KeyAction:
    """Действие клавиши"""
    key: str
    hold_duration: float = 0.0
    delay_before: float = 0.0
    delay_after: float = 0.0


@dataclass
class Command:
    """Структура команды"""
    id: str
    name: str
    phrases: List[str]  # Фразы для распознавания
    action_type: ActionType
    actions: List[Dict[str, Any]]  # Список действий
    enabled: bool = True
    description: str = ""
    hotkey: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        result = asdict(self)
        result['action_type'] = self.action_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Command':
        """Создать из словаря"""
        data['action_type'] = ActionType(data['action_type'])
        return cls(**data)


class CommandProcessor:
    """Процессор команд с нечетким сравнением"""
    
    def __init__(self, commands_file: str = None, threshold: int = 65):
        self.threshold = threshold
        self.commands: Dict[str, Command] = {}
        self.commands_file = commands_file or "commands.json"
        
        # Callbacks
        self.on_command_executed: Optional[Callable] = None
        self.on_command_not_found: Optional[Callable] = None
        
        # Загружаем команды
        self._load_commands()
        
        logger.info(f"Command processor initialized with threshold {threshold}%")
    
    def _load_commands(self):
        """Загрузить команды из файла"""
        try:
            if os.path.exists(self.commands_file):
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for cmd_data in data.get('commands', []):
                    try:
                        command = Command.from_dict(cmd_data)
                        self.commands[command.id] = command
                    except Exception as e:
                        logger.error(f"Failed to load command {cmd_data.get('id', 'unknown')}: {e}")
                
                logger.info(f"Loaded {len(self.commands)} commands from {self.commands_file}")
            else:
                logger.info("Commands file not found, creating default commands")
                self._create_default_commands()
                self.save_commands()
                
        except Exception as e:
            logger.error(f"Failed to load commands: {e}")
            self._create_default_commands()
    
    def _create_default_commands(self):
        """Создать команды по умолчанию"""
        default_commands = [
            Command(
                id="copy",
                name="Копировать",
                phrases=["копировать", "скопировать", "copy", "копи"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "c"]}],
                description="Копирование в буфер обмена"
            ),
            Command(
                id="paste", 
                name="Вставить",
                phrases=["вставить", "вставь", "paste", "паст"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "v"]}],
                description="Вставка из буфера обмена"
            ),
            Command(
                id="save",
                name="Сохранить",
                phrases=["сохранить", "сохрани", "save", "сейв"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "s"]}],
                description="Сохранение файла"
            ),
            Command(
                id="undo",
                name="Отменить",
                phrases=["отменить", "отмени", "undo", "назад"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "z"]}],
                description="Отмена последнего действия"
            ),
            Command(
                id="new_tab",
                name="Новая вкладка",
                phrases=["новая вкладка", "новый таб", "new tab", "открой вкладку"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "t"]}],
                description="Открытие новой вкладки"
            ),
            Command(
                id="close_tab",
                name="Закрыть вкладку",
                phrases=["закрыть вкладку", "закрой таб", "close tab", "закрой вкладку"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["ctrl", "w"]}],
                description="Закрытие текущей вкладки"
            ),
            Command(
                id="alt_tab",
                name="Переключить окно",
                phrases=["переключить окно", "альт таб", "alt tab", "следующее окно"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["alt", "tab"]}],
                description="Переключение между окнами"
            ),
            Command(
                id="minimize",
                name="Свернуть окно",
                phrases=["свернуть", "минимизировать", "minimize", "сверни"],
                action_type=ActionType.KEYBOARD,
                actions=[{"type": "key_combination", "keys": ["win", "down"]}],
                description="Сворачивание активного окна"
            )
        ]
        
        for cmd in default_commands:
            self.commands[cmd.id] = cmd
    
    def save_commands(self):
        """Сохранить команды в файл"""
        try:
            data = {
                'version': '1.0',
                'commands': [cmd.to_dict() for cmd in self.commands.values()]
            }
            
            with open(self.commands_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Commands saved to {self.commands_file}")
            
        except Exception as e:
            logger.error(f"Failed to save commands: {e}")
    
    async def process_text(self, text: str) -> Optional[Command]:
        """Обработать текст и найти подходящую команду"""
        if not text or not text.strip():
            return None
        
        text = text.lower().strip()
        logger.debug(f"Processing text: '{text}'")
        
        # Собираем все фразы из всех команд
        all_phrases = []
        phrase_to_command = {}
        
        for command in self.commands.values():
            if not command.enabled:
                continue
                
            for phrase in command.phrases:
                phrase_lower = phrase.lower()
                all_phrases.append(phrase_lower)
                phrase_to_command[phrase_lower] = command
        
        if not all_phrases:
            logger.warning("No enabled commands available")
            return None
        
        # Используем fuzzywuzzy для поиска лучшего совпадения
        best_matches = process.extractBests(
            text, 
            all_phrases, 
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.threshold,
            limit=3
        )
        
        if not best_matches:
            logger.debug(f"No command matches found for '{text}' (threshold: {self.threshold}%)")
            if self.on_command_not_found:
                await self._call_callback(self.on_command_not_found, text)
            return None
        
        # Берем лучшее совпадение
        best_phrase, best_score = best_matches[0]
        best_command = phrase_to_command[best_phrase]
        
        logger.info(f"Command found: '{best_command.name}' for '{text}' (score: {best_score}%)")
        
        return best_command
    
    async def execute_command(self, command: Command) -> bool:
        """Выполнить команду"""
        if not command or not command.enabled:
            return False
        
        logger.info(f"Executing command: {command.name}")
        
        try:
            success = True
            
            for action in command.actions:
                action_success = await self._execute_action(action)
                if not action_success:
                    success = False
                    logger.error(f"Failed to execute action: {action}")
            
            if success and self.on_command_executed:
                await self._call_callback(self.on_command_executed, command)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to execute command '{command.name}': {e}")
            return False
    
    async def _execute_action(self, action: Dict[str, Any]) -> bool:
        """Выполнить действие"""
        action_type = action.get('type')
        
        if action_type == 'key_combination':
            return await self._execute_key_combination(action)
        elif action_type == 'key_sequence':
            return await self._execute_key_sequence(action)
        elif action_type == 'type_text':
            return await self._execute_type_text(action)
        elif action_type == 'delay':
            return await self._execute_delay(action)
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return False
    
    async def _execute_key_combination(self, action: Dict[str, Any]) -> bool:
        """Выполнить комбинацию клавиш"""
        keys = action.get('keys', [])
        hold_duration = action.get('hold_duration', 0.0)
        
        if not keys:
            return False
        
        try:
            # Импортируем модуль ввода в зависимости от платформы
            from ..modules.input_controller import InputController
            input_controller = InputController()
            
            return await input_controller.press_key_combination(keys, hold_duration)
            
        except Exception as e:
            logger.error(f"Failed to execute key combination {keys}: {e}")
            return False
    
    async def _execute_key_sequence(self, action: Dict[str, Any]) -> bool:
        """Выполнить последовательность клавиш"""
        sequence = action.get('sequence', [])
        delay_between = action.get('delay_between', 0.1)
        
        if not sequence:
            return False
        
        try:
            from ..modules.input_controller import InputController
            input_controller = InputController()
            
            for key_info in sequence:
                if isinstance(key_info, str):
                    await input_controller.press_key(key_info)
                else:
                    key = key_info.get('key')
                    duration = key_info.get('duration', 0.0)
                    await input_controller.press_key(key, duration)
                
                if delay_between > 0:
                    await asyncio.sleep(delay_between)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute key sequence: {e}")
            return False
    
    async def _execute_type_text(self, action: Dict[str, Any]) -> bool:
        """Ввести текст"""
        text = action.get('text', '')
        delay_between = action.get('delay_between', 0.05)
        
        if not text:
            return False
        
        try:
            from ..modules.input_controller import InputController
            input_controller = InputController()
            
            return await input_controller.type_text(text, delay_between)
            
        except Exception as e:
            logger.error(f"Failed to type text '{text}': {e}")
            return False
    
    async def _execute_delay(self, action: Dict[str, Any]) -> bool:
        """Выполнить задержку"""
        duration = action.get('duration', 0.0)
        
        if duration > 0:
            await asyncio.sleep(duration)
        
        return True
    
    async def _call_callback(self, callback: Callable, *args):
        """Безопасный вызов callback функции"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    def add_command(self, command: Command) -> bool:
        """Добавить команду"""
        try:
            self.commands[command.id] = command
            self.save_commands()
            logger.info(f"Command '{command.name}' added successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to add command: {e}")
            return False
    
    def remove_command(self, command_id: str) -> bool:
        """Удалить команду"""
        try:
            if command_id in self.commands:
                del self.commands[command_id]
                self.save_commands()
                logger.info(f"Command '{command_id}' removed successfully")
                return True
            else:
                logger.warning(f"Command '{command_id}' not found")
                return False
        except Exception as e:
            logger.error(f"Failed to remove command: {e}")
            return False
    
    def update_command(self, command: Command) -> bool:
        """Обновить команду"""
        return self.add_command(command)
    
    def get_command(self, command_id: str) -> Optional[Command]:
        """Получить команду по ID"""
        return self.commands.get(command_id)
    
    def get_all_commands(self) -> List[Command]:
        """Получить все команды"""
        return list(self.commands.values())
    
    def get_enabled_commands(self) -> List[Command]:
        """Получить только включенные команды"""
        return [cmd for cmd in self.commands.values() if cmd.enabled]
    
    def set_threshold(self, threshold: int):
        """Установить порог сходства"""
        if 0 <= threshold <= 100:
            self.threshold = threshold
            logger.info(f"Threshold set to {threshold}%")
        else:
            logger.warning(f"Invalid threshold value: {threshold}")
    
    def set_callbacks(self, **callbacks):
        """Установить callback функции"""
        self.on_command_executed = callbacks.get('on_command_executed')
        self.on_command_not_found = callbacks.get('on_command_not_found')
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику команд"""
        total_commands = len(self.commands)
        enabled_commands = len(self.get_enabled_commands())
        
        action_types = {}
        for command in self.commands.values():
            action_type = command.action_type.value
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        return {
            'total_commands': total_commands,
            'enabled_commands': enabled_commands,
            'disabled_commands': total_commands - enabled_commands,
            'action_types': action_types,
            'threshold': self.threshold
        }