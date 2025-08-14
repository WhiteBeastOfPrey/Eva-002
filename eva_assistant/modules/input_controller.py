"""
Контроллер ввода с поддержкой pydirectinput-rgx и кросс-платформенности
"""

import asyncio
import logging
import platform
import time
from typing import List, Dict, Any, Optional
from ..core.platform_detector import PlatformDetector, SupportedPlatform

logger = logging.getLogger(__name__)


class InputController:
    """Контроллер ввода с кросс-платформенной поддержкой"""
    
    def __init__(self):
        self.platform_detector = PlatformDetector()
        self.platform = self.platform_detector.current_platform
        
        # Инициализация модулей ввода в зависимости от платформы
        self._init_input_modules()
        
        # Маппинг клавиш
        self.key_mapping = self._get_key_mapping()
        
        logger.info(f"Input controller initialized for {self.platform.value}")
    
    def _init_input_modules(self):
        """Инициализация модулей ввода"""
        try:
            if self.platform == SupportedPlatform.WINDOWS_X64:
                # Используем pydirectinput для Windows
                try:
                    import pydirectinput
                    self.input_module = pydirectinput
                    self.input_type = "pydirectinput"
                    
                    # Настройки для pydirectinput
                    pydirectinput.PAUSE = 0.01
                    pydirectinput.FAILSAFE = False
                    
                    logger.info("Using pydirectinput for Windows input")
                except ImportError:
                    logger.warning("pydirectinput not available, falling back to pynput")
                    self._init_pynput()
            
            elif self.platform in [SupportedPlatform.MACOS, SupportedPlatform.LINUX]:
                # Используем pynput для macOS и Linux
                self._init_pynput()
            
            else:
                logger.error("Unsupported platform for input control")
                self.input_module = None
                self.input_type = None
                
        except Exception as e:
            logger.error(f"Failed to initialize input modules: {e}")
            self.input_module = None
            self.input_type = None
    
    def _init_pynput(self):
        """Инициализация pynput"""
        try:
            from pynput import keyboard, mouse
            self.keyboard_controller = keyboard.Controller()
            self.mouse_controller = mouse.Controller()
            self.input_type = "pynput"
            self.pynput_key = keyboard.Key
            
            logger.info("Using pynput for input control")
        except ImportError as e:
            logger.error(f"Failed to import pynput: {e}")
            raise
    
    def _get_key_mapping(self) -> Dict[str, Any]:
        """Получить маппинг клавиш для текущей платформы"""
        if self.input_type == "pydirectinput":
            return {
                # Модификаторы
                'ctrl': 'ctrl',
                'alt': 'alt', 
                'shift': 'shift',
                'win': 'win',
                'cmd': 'win',  # Для совместимости с macOS
                
                # Функциональные клавиши
                'enter': 'enter',
                'space': 'space',
                'tab': 'tab',
                'backspace': 'backspace',
                'delete': 'delete',
                'escape': 'esc',
                'esc': 'esc',
                
                # Стрелки
                'up': 'up',
                'down': 'down',
                'left': 'left',
                'right': 'right',
                
                # F-клавиши
                **{f'f{i}': f'f{i}' for i in range(1, 13)},
                
                # Цифры
                **{str(i): str(i) for i in range(10)},
                
                # Буквы
                **{chr(i): chr(i) for i in range(ord('a'), ord('z') + 1)}
            }
        
        elif self.input_type == "pynput":
            from pynput import keyboard
            return {
                # Модификаторы
                'ctrl': keyboard.Key.ctrl_l,
                'alt': keyboard.Key.alt_l,
                'shift': keyboard.Key.shift_l,
                'win': keyboard.Key.cmd if self.platform == SupportedPlatform.MACOS else keyboard.Key.ctrl_l,
                'cmd': keyboard.Key.cmd,
                
                # Функциональные клавиши
                'enter': keyboard.Key.enter,
                'space': keyboard.Key.space,
                'tab': keyboard.Key.tab,
                'backspace': keyboard.Key.backspace,
                'delete': keyboard.Key.delete,
                'escape': keyboard.Key.esc,
                'esc': keyboard.Key.esc,
                
                # Стрелки
                'up': keyboard.Key.up,
                'down': keyboard.Key.down,
                'left': keyboard.Key.left,
                'right': keyboard.Key.right,
                
                # F-клавиши
                **{f'f{i}': getattr(keyboard.Key, f'f{i}') for i in range(1, 13)},
                
                # Цифры и буквы обрабатываются отдельно
            }
        
        return {}
    
    async def press_key(self, key: str, duration: float = 0.0) -> bool:
        """Нажать клавишу"""
        try:
            if self.input_type == "pydirectinput":
                return await self._press_key_pydirectinput(key, duration)
            elif self.input_type == "pynput":
                return await self._press_key_pynput(key, duration)
            else:
                logger.error("No input module available")
                return False
                
        except Exception as e:
            logger.error(f"Failed to press key '{key}': {e}")
            return False
    
    async def _press_key_pydirectinput(self, key: str, duration: float) -> bool:
        """Нажать клавишу через pydirectinput"""
        mapped_key = self.key_mapping.get(key.lower(), key)
        
        if duration > 0:
            # Нажать и удерживать
            self.input_module.keyDown(mapped_key)
            await asyncio.sleep(duration)
            self.input_module.keyUp(mapped_key)
        else:
            # Обычное нажатие
            self.input_module.press(mapped_key)
        
        return True
    
    async def _press_key_pynput(self, key: str, duration: float) -> bool:
        """Нажать клавишу через pynput"""
        key_lower = key.lower()
        
        # Получаем клавишу
        if key_lower in self.key_mapping:
            pynput_key = self.key_mapping[key_lower]
        elif len(key) == 1 and key.isalnum():
            pynput_key = key.lower()
        else:
            logger.warning(f"Unknown key: {key}")
            return False
        
        if duration > 0:
            # Нажать и удерживать
            self.keyboard_controller.press(pynput_key)
            await asyncio.sleep(duration)
            self.keyboard_controller.release(pynput_key)
        else:
            # Обычное нажатие
            self.keyboard_controller.press(pynput_key)
            self.keyboard_controller.release(pynput_key)
        
        return True
    
    async def press_key_combination(self, keys: List[str], hold_duration: float = 0.0) -> bool:
        """Нажать комбинацию клавиш"""
        try:
            if self.input_type == "pydirectinput":
                return await self._press_combination_pydirectinput(keys, hold_duration)
            elif self.input_type == "pynput":
                return await self._press_combination_pynput(keys, hold_duration)
            else:
                logger.error("No input module available")
                return False
                
        except Exception as e:
            logger.error(f"Failed to press key combination {keys}: {e}")
            return False
    
    async def _press_combination_pydirectinput(self, keys: List[str], hold_duration: float) -> bool:
        """Нажать комбинацию клавиш через pydirectinput"""
        if len(keys) == 1:
            return await self._press_key_pydirectinput(keys[0], hold_duration)
        
        # Конвертируем клавиши
        mapped_keys = []
        for key in keys:
            mapped_key = self.key_mapping.get(key.lower(), key)
            mapped_keys.append(mapped_key)
        
        # Используем hotkey для комбинации
        self.input_module.hotkey(*mapped_keys)
        
        if hold_duration > 0:
            await asyncio.sleep(hold_duration)
        
        return True
    
    async def _press_combination_pynput(self, keys: List[str], hold_duration: float) -> bool:
        """Нажать комбинацию клавиш через pynput"""
        if len(keys) == 1:
            return await self._press_key_pynput(keys[0], hold_duration)
        
        # Конвертируем клавиши
        pynput_keys = []
        for key in keys:
            key_lower = key.lower()
            if key_lower in self.key_mapping:
                pynput_keys.append(self.key_mapping[key_lower])
            elif len(key) == 1 and key.isalnum():
                pynput_keys.append(key.lower())
            else:
                logger.warning(f"Unknown key in combination: {key}")
                return False
        
        # Нажимаем все клавиши
        for key in pynput_keys:
            self.keyboard_controller.press(key)
        
        if hold_duration > 0:
            await asyncio.sleep(hold_duration)
        
        # Отпускаем в обратном порядке
        for key in reversed(pynput_keys):
            self.keyboard_controller.release(key)
        
        return True
    
    async def type_text(self, text: str, delay_between: float = 0.05) -> bool:
        """Ввести текст"""
        try:
            if self.input_type == "pydirectinput":
                self.input_module.write(text, interval=delay_between)
            elif self.input_type == "pynput":
                for char in text:
                    self.keyboard_controller.type(char)
                    if delay_between > 0:
                        await asyncio.sleep(delay_between)
            else:
                logger.error("No input module available")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to type text '{text}': {e}")
            return False
    
    async def click_mouse(self, x: int, y: int, button: str = 'left', clicks: int = 1) -> bool:
        """Клик мышью"""
        try:
            if self.input_type == "pydirectinput":
                if button == 'left':
                    self.input_module.click(x, y, clicks=clicks)
                elif button == 'right':
                    self.input_module.rightClick(x, y)
                elif button == 'middle':
                    self.input_module.middleClick(x, y)
            elif self.input_type == "pynput":
                from pynput import mouse
                
                # Перемещаем курсор
                self.mouse_controller.position = (x, y)
                
                # Выбираем кнопку
                if button == 'left':
                    mouse_button = mouse.Button.left
                elif button == 'right':
                    mouse_button = mouse.Button.right
                elif button == 'middle':
                    mouse_button = mouse.Button.middle
                else:
                    mouse_button = mouse.Button.left
                
                # Кликаем
                for _ in range(clicks):
                    self.mouse_controller.click(mouse_button)
                    if clicks > 1:
                        await asyncio.sleep(0.1)
            else:
                logger.error("No input module available")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to click mouse at ({x}, {y}): {e}")
            return False
    
    async def scroll_mouse(self, x: int, y: int, direction: str = 'up', amount: int = 3) -> bool:
        """Прокрутка мышью"""
        try:
            if self.input_type == "pydirectinput":
                scroll_amount = amount if direction == 'up' else -amount
                self.input_module.scroll(scroll_amount, x, y)
            elif self.input_type == "pynput":
                # Перемещаем курсор
                self.mouse_controller.position = (x, y)
                
                # Прокручиваем
                scroll_amount = amount if direction == 'up' else -amount
                self.mouse_controller.scroll(0, scroll_amount)
            else:
                logger.error("No input module available")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to scroll mouse: {e}")
            return False
    
    def get_mouse_position(self) -> tuple:
        """Получить позицию мыши"""
        try:
            if self.input_type == "pydirectinput":
                return self.input_module.position()
            elif self.input_type == "pynput":
                return self.mouse_controller.position
            else:
                return (0, 0)
        except Exception as e:
            logger.error(f"Failed to get mouse position: {e}")
            return (0, 0)
    
    def is_available(self) -> bool:
        """Проверить доступность контроллера ввода"""
        return self.input_module is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус контроллера"""
        return {
            'platform': self.platform.value,
            'input_type': self.input_type,
            'is_available': self.is_available(),
            'supported_features': {
                'keyboard': True,
                'mouse': True,
                'key_combinations': True,
                'text_typing': True
            }
        }