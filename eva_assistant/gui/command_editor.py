"""
Редактор команд с визуальным выбором сочетания клавиш
"""

import logging
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QTabWidget, QWidget, QSplitter, QMessageBox, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QKeySequence, QKeyEvent

from ..core.command_processor import Command, ActionType
from ..core.eva_core import EVACore

logger = logging.getLogger(__name__)


class KeyCaptureWidget(QWidget):
    """Виджет для захвата нажатий клавиш"""
    
    key_captured = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QWidget {
                border: 2px solid #555;
                border-radius: 5px;
                background-color: #2a2a2a;
                color: white;
                font-size: 12px;
                padding: 5px;
            }
            QWidget:focus {
                border-color: #0078d4;
            }
        """)
        
        self.setFocusPolicy(Qt.StrongFocus)
        self.captured_keys = []
        self.is_capturing = False
        
        # Layout для отображения текста
        layout = QHBoxLayout(self)
        self.label = QLabel("Нажмите клавиши...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.start_capture()
    
    def start_capture(self):
        """Начать захват клавиш"""
        self.is_capturing = True
        self.captured_keys.clear()
        self.label.setText("Нажмите клавиши... (ESC для отмены)")
        self.setFocus()
    
    def stop_capture(self):
        """Остановить захват клавиш"""
        self.is_capturing = False
        if self.captured_keys:
            key_combination = "+".join(self.captured_keys)
            self.label.setText(key_combination)
            self.key_captured.emit(key_combination)
        else:
            self.label.setText("Не выбрано")
    
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатия клавиш"""
        if not self.is_capturing:
            return
        
        key = event.key()
        
        # ESC для отмены
        if key == Qt.Key_Escape:
            self.captured_keys.clear()
            self.label.setText("Отменено")
            self.is_capturing = False
            return
        
        # Enter для завершения
        if key in [Qt.Key_Return, Qt.Key_Enter]:
            self.stop_capture()
            return
        
        # Получаем название клавиши
        key_name = self._get_key_name(key, event.modifiers())
        
        if key_name and key_name not in self.captured_keys:
            self.captured_keys.append(key_name)
            self.label.setText(" + ".join(self.captured_keys))
    
    def _get_key_name(self, key: int, modifiers: Qt.KeyboardModifiers) -> str:
        """Получить название клавиши"""
        # Модификаторы
        if modifiers & Qt.ControlModifier and "Ctrl" not in self.captured_keys:
            return "Ctrl"
        if modifiers & Qt.AltModifier and "Alt" not in self.captured_keys:
            return "Alt"
        if modifiers & Qt.ShiftModifier and "Shift" not in self.captured_keys:
            return "Shift"
        if modifiers & Qt.MetaModifier and "Win" not in self.captured_keys:
            return "Win"
        
        # Обычные клавиши
        key_map = {
            Qt.Key_A: "A", Qt.Key_B: "B", Qt.Key_C: "C", Qt.Key_D: "D",
            Qt.Key_E: "E", Qt.Key_F: "F", Qt.Key_G: "G", Qt.Key_H: "H",
            Qt.Key_I: "I", Qt.Key_J: "J", Qt.Key_K: "K", Qt.Key_L: "L",
            Qt.Key_M: "M", Qt.Key_N: "N", Qt.Key_O: "O", Qt.Key_P: "P",
            Qt.Key_Q: "Q", Qt.Key_R: "R", Qt.Key_S: "S", Qt.Key_T: "T",
            Qt.Key_U: "U", Qt.Key_V: "V", Qt.Key_W: "W", Qt.Key_X: "X",
            Qt.Key_Y: "Y", Qt.Key_Z: "Z",
            
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
            Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
            Qt.Key_8: "8", Qt.Key_9: "9",
            
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3", Qt.Key_F4: "F4",
            Qt.Key_F5: "F5", Qt.Key_F6: "F6", Qt.Key_F7: "F7", Qt.Key_F8: "F8",
            Qt.Key_F9: "F9", Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
            
            Qt.Key_Space: "Space", Qt.Key_Tab: "Tab", Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Delete", Qt.Key_Insert: "Insert", Qt.Key_Home: "Home",
            Qt.Key_End: "End", Qt.Key_PageUp: "PageUp", Qt.Key_PageDown: "PageDown",
            
            Qt.Key_Up: "Up", Qt.Key_Down: "Down", Qt.Key_Left: "Left", Qt.Key_Right: "Right"
        }
        
        return key_map.get(key, "")
    
    def set_keys(self, key_combination: str):
        """Установить комбинацию клавиш"""
        self.captured_keys = key_combination.split("+") if key_combination else []
        self.label.setText(key_combination if key_combination else "Не выбрано")
        self.is_capturing = False


class CommandEditorWindow(QDialog):
    """Окно редактора команд"""
    
    def __init__(self, eva_core: EVACore, parent=None):
        super().__init__(parent)
        
        self.eva_core = eva_core
        self.current_command: Optional[Command] = None
        self.is_editing = False
        
        self._setup_ui()
        self._load_commands()
        
        logger.info("Command editor window initialized")
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("Редактор команд EVA Assistant")
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)
        
        # Основной layout
        main_layout = QHBoxLayout(self)
        
        # Создаем сплиттер
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель - список команд
        left_panel = self._create_commands_list()
        splitter.addWidget(left_panel)
        
        # Правая панель - редактор команды
        right_panel = self._create_command_editor()
        splitter.addWidget(right_panel)
        
        # Устанавливаем пропорции
        splitter.setSizes([300, 600])
        
        # Применяем темную тему
        self._apply_dark_theme()
    
    def _create_commands_list(self) -> QWidget:
        """Создать панель со списком команд"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Заголовок
        title = QLabel("Команды")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Список команд
        self.commands_list = QListWidget()
        self.commands_list.itemClicked.connect(self._on_command_selected)
        layout.addWidget(self.commands_list)
        
        # Кнопки управления
        buttons_layout = QVBoxLayout()
        
        self.new_command_btn = QPushButton("➕ Новая команда")
        self.new_command_btn.clicked.connect(self._new_command)
        buttons_layout.addWidget(self.new_command_btn)
        
        self.duplicate_command_btn = QPushButton("📋 Дублировать")
        self.duplicate_command_btn.clicked.connect(self._duplicate_command)
        self.duplicate_command_btn.setEnabled(False)
        buttons_layout.addWidget(self.duplicate_command_btn)
        
        self.delete_command_btn = QPushButton("🗑️ Удалить")
        self.delete_command_btn.clicked.connect(self._delete_command)
        self.delete_command_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_command_btn)
        
        buttons_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Сохранить все")
        self.save_btn.clicked.connect(self._save_all_commands)
        buttons_layout.addWidget(self.save_btn)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_command_editor(self) -> QWidget:
        """Создать панель редактора команды"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Вкладки
        self.tabs = QTabWidget()
        
        # Вкладка основных настроек
        basic_tab = self._create_basic_settings_tab()
        self.tabs.addTab(basic_tab, "Основные")
        
        # Вкладка действий
        actions_tab = self._create_actions_tab()
        self.tabs.addTab(actions_tab, "Действия")
        
        # Вкладка фраз
        phrases_tab = self._create_phrases_tab()
        self.tabs.addTab(phrases_tab, "Фразы")
        
        layout.addWidget(self.tabs)
        
        # Кнопки сохранения
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.save_command_btn = QPushButton("💾 Сохранить команду")
        self.save_command_btn.clicked.connect(self._save_current_command)
        self.save_command_btn.setEnabled(False)
        buttons_layout.addWidget(self.save_command_btn)
        
        self.cancel_btn = QPushButton("❌ Отменить")
        self.cancel_btn.clicked.connect(self._cancel_editing)
        self.cancel_btn.setEnabled(False)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_basic_settings_tab(self) -> QWidget:
        """Создать вкладку основных настроек"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # ID команды
        self.command_id_edit = QLineEdit()
        self.command_id_edit.textChanged.connect(self._on_command_changed)
        layout.addRow("ID команды:", self.command_id_edit)
        
        # Название команды
        self.command_name_edit = QLineEdit()
        self.command_name_edit.textChanged.connect(self._on_command_changed)
        layout.addRow("Название:", self.command_name_edit)
        
        # Описание
        self.command_description_edit = QTextEdit()
        self.command_description_edit.setMaximumHeight(80)
        self.command_description_edit.textChanged.connect(self._on_command_changed)
        layout.addRow("Описание:", self.command_description_edit)
        
        # Тип действия
        self.action_type_combo = QComboBox()
        for action_type in ActionType:
            self.action_type_combo.addItem(action_type.value.title(), action_type)
        self.action_type_combo.currentTextChanged.connect(self._on_command_changed)
        layout.addRow("Тип действия:", self.action_type_combo)
        
        # Включена ли команда
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.toggled.connect(self._on_command_changed)
        layout.addRow("Включена:", self.enabled_checkbox)
        
        # Горячая клавиша
        hotkey_layout = QHBoxLayout()
        self.hotkey_capture = KeyCaptureWidget()
        self.hotkey_capture.key_captured.connect(self._on_hotkey_captured)
        hotkey_layout.addWidget(self.hotkey_capture)
        
        self.clear_hotkey_btn = QPushButton("Очистить")
        self.clear_hotkey_btn.clicked.connect(self._clear_hotkey)
        hotkey_layout.addWidget(self.clear_hotkey_btn)
        
        layout.addRow("Горячая клавиша:", hotkey_layout)
        
        return tab
    
    def _create_actions_tab(self) -> QWidget:
        """Создать вкладку действий"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Заголовок
        title = QLabel("Действия команды")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(title)
        
        # Список действий
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(4)
        self.actions_table.setHorizontalHeaderLabels(["Тип", "Параметры", "Задержка", "Описание"])
        
        # Настройка таблицы
        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        layout.addWidget(self.actions_table)
        
        # Кнопки управления действиями
        actions_buttons = QHBoxLayout()
        
        self.add_key_action_btn = QPushButton("➕ Клавиша")
        self.add_key_action_btn.clicked.connect(self._add_key_action)
        actions_buttons.addWidget(self.add_key_action_btn)
        
        self.add_text_action_btn = QPushButton("➕ Текст")
        self.add_text_action_btn.clicked.connect(self._add_text_action)
        actions_buttons.addWidget(self.add_text_action_btn)
        
        self.add_delay_action_btn = QPushButton("➕ Задержка")
        self.add_delay_action_btn.clicked.connect(self._add_delay_action)
        actions_buttons.addWidget(self.add_delay_action_btn)
        
        actions_buttons.addStretch()
        
        self.remove_action_btn = QPushButton("🗑️ Удалить")
        self.remove_action_btn.clicked.connect(self._remove_action)
        actions_buttons.addWidget(self.remove_action_btn)
        
        layout.addLayout(actions_buttons)
        
        return tab
    
    def _create_phrases_tab(self) -> QWidget:
        """Создать вкладку фраз"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Заголовок
        title = QLabel("Фразы для распознавания")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(title)
        
        # Список фраз
        self.phrases_list = QListWidget()
        layout.addWidget(self.phrases_list)
        
        # Добавление фразы
        add_phrase_layout = QHBoxLayout()
        
        self.new_phrase_edit = QLineEdit()
        self.new_phrase_edit.setPlaceholderText("Введите новую фразу...")
        self.new_phrase_edit.returnPressed.connect(self._add_phrase)
        add_phrase_layout.addWidget(self.new_phrase_edit)
        
        self.add_phrase_btn = QPushButton("➕ Добавить")
        self.add_phrase_btn.clicked.connect(self._add_phrase)
        add_phrase_layout.addWidget(self.add_phrase_btn)
        
        layout.addLayout(add_phrase_layout)
        
        # Кнопки управления фразами
        phrases_buttons = QHBoxLayout()
        phrases_buttons.addStretch()
        
        self.edit_phrase_btn = QPushButton("✏️ Редактировать")
        self.edit_phrase_btn.clicked.connect(self._edit_phrase)
        phrases_buttons.addWidget(self.edit_phrase_btn)
        
        self.remove_phrase_btn = QPushButton("🗑️ Удалить")
        self.remove_phrase_btn.clicked.connect(self._remove_phrase)
        phrases_buttons.addWidget(self.remove_phrase_btn)
        
        layout.addLayout(phrases_buttons)
        
        return tab
    
    def _apply_dark_theme(self):
        """Применить темную тему"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
            }
            QComboBox {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
            }
            QListWidget, QTableWidget {
                background-color: #3a3a3a;
                border: 1px solid #555;
                alternate-background-color: #404040;
            }
            QTabWidget::pane {
                border: 1px solid #555;
            }
            QTabBar::tab {
                background-color: #404040;
                border: 1px solid #555;
                padding: 5px 10px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
        """)
    
    # Методы управления командами
    def _load_commands(self):
        """Загрузить список команд"""
        self.commands_list.clear()
        
        commands = self.eva_core.get_commands()
        for command in commands:
            item = QListWidgetItem(f"{command.name} ({command.id})")
            item.setData(Qt.UserRole, command)
            
            # Цветовая индикация
            if not command.enabled:
                item.setForeground(QColor(150, 150, 150))
            
            self.commands_list.addItem(item)
    
    def _on_command_selected(self, item: QListWidgetItem):
        """Обработка выбора команды"""
        command = item.data(Qt.UserRole)
        if command:
            self._load_command(command)
            self.duplicate_command_btn.setEnabled(True)
            self.delete_command_btn.setEnabled(True)
    
    def _load_command(self, command: Command):
        """Загрузить команду в редактор"""
        self.current_command = command
        self.is_editing = True
        
        # Основные настройки
        self.command_id_edit.setText(command.id)
        self.command_name_edit.setText(command.name)
        self.command_description_edit.setText(command.description)
        self.enabled_checkbox.setChecked(command.enabled)
        
        # Тип действия
        for i in range(self.action_type_combo.count()):
            if self.action_type_combo.itemData(i) == command.action_type:
                self.action_type_combo.setCurrentIndex(i)
                break
        
        # Горячая клавиша
        self.hotkey_capture.set_keys(command.hotkey or "")
        
        # Действия
        self._load_actions(command.actions)
        
        # Фразы
        self._load_phrases(command.phrases)
        
        # Включаем кнопки сохранения
        self.save_command_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
    
    def _load_actions(self, actions: List[Dict[str, Any]]):
        """Загрузить действия в таблицу"""
        self.actions_table.setRowCount(len(actions))
        
        for i, action in enumerate(actions):
            action_type = action.get('type', '')
            
            # Тип действия
            type_item = QTableWidgetItem(action_type)
            self.actions_table.setItem(i, 0, type_item)
            
            # Параметры
            params = []
            if action_type == 'key_combination':
                keys = action.get('keys', [])
                params.append(f"Keys: {', '.join(keys)}")
                hold_duration = action.get('hold_duration', 0)
                if hold_duration > 0:
                    params.append(f"Hold: {hold_duration}s")
            elif action_type == 'type_text':
                text = action.get('text', '')
                params.append(f"Text: {text}")
            elif action_type == 'delay':
                duration = action.get('duration', 0)
                params.append(f"Duration: {duration}s")
            
            params_item = QTableWidgetItem("; ".join(params))
            self.actions_table.setItem(i, 1, params_item)
            
            # Задержка
            delay = action.get('delay_before', 0) + action.get('delay_after', 0)
            delay_item = QTableWidgetItem(f"{delay}s")
            self.actions_table.setItem(i, 2, delay_item)
            
            # Описание
            desc = action.get('description', '')
            desc_item = QTableWidgetItem(desc)
            self.actions_table.setItem(i, 3, desc_item)
    
    def _load_phrases(self, phrases: List[str]):
        """Загрузить фразы в список"""
        self.phrases_list.clear()
        
        for phrase in phrases:
            item = QListWidgetItem(phrase)
            self.phrases_list.addItem(item)
    
    def _new_command(self):
        """Создать новую команду"""
        # Генерируем уникальный ID
        base_id = "new_command"
        command_id = base_id
        counter = 1
        
        existing_ids = {cmd.id for cmd in self.eva_core.get_commands()}
        while command_id in existing_ids:
            command_id = f"{base_id}_{counter}"
            counter += 1
        
        # Создаем новую команду
        new_command = Command(
            id=command_id,
            name="Новая команда",
            phrases=["новая команда"],
            action_type=ActionType.KEYBOARD,
            actions=[{"type": "key_combination", "keys": ["ctrl", "c"]}],
            description="Описание новой команды"
        )
        
        # Добавляем в список
        item = QListWidgetItem(f"{new_command.name} ({new_command.id})")
        item.setData(Qt.UserRole, new_command)
        self.commands_list.addItem(item)
        
        # Выбираем и загружаем
        self.commands_list.setCurrentItem(item)
        self._load_command(new_command)
    
    def _duplicate_command(self):
        """Дублировать выбранную команду"""
        current_item = self.commands_list.currentItem()
        if not current_item:
            return
        
        original_command = current_item.data(Qt.UserRole)
        if not original_command:
            return
        
        # Создаем копию
        new_id = f"{original_command.id}_copy"
        counter = 1
        existing_ids = {cmd.id for cmd in self.eva_core.get_commands()}
        
        while new_id in existing_ids:
            new_id = f"{original_command.id}_copy_{counter}"
            counter += 1
        
        duplicated_command = Command(
            id=new_id,
            name=f"{original_command.name} (копия)",
            phrases=original_command.phrases.copy(),
            action_type=original_command.action_type,
            actions=[action.copy() for action in original_command.actions],
            enabled=original_command.enabled,
            description=original_command.description,
            hotkey=original_command.hotkey
        )
        
        # Добавляем в список
        item = QListWidgetItem(f"{duplicated_command.name} ({duplicated_command.id})")
        item.setData(Qt.UserRole, duplicated_command)
        self.commands_list.addItem(item)
        
        # Выбираем и загружаем
        self.commands_list.setCurrentItem(item)
        self._load_command(duplicated_command)
    
    def _delete_command(self):
        """Удалить выбранную команду"""
        current_item = self.commands_list.currentItem()
        if not current_item:
            return
        
        command = current_item.data(Qt.UserRole)
        if not command:
            return
        
        # Подтверждение удаления
        reply = QMessageBox.question(
            self, "Удаление команды",
            f"Вы уверены, что хотите удалить команду '{command.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Удаляем из EVA Core
            self.eva_core.remove_command(command.id)
            
            # Удаляем из списка
            row = self.commands_list.row(current_item)
            self.commands_list.takeItem(row)
            
            # Очищаем редактор
            self._clear_editor()
    
    def _save_current_command(self):
        """Сохранить текущую команду"""
        if not self.current_command:
            return
        
        try:
            # Собираем данные из формы
            self.current_command.id = self.command_id_edit.text().strip()
            self.current_command.name = self.command_name_edit.text().strip()
            self.current_command.description = self.command_description_edit.toPlainText().strip()
            self.current_command.enabled = self.enabled_checkbox.isChecked()
            
            # Тип действия
            self.current_command.action_type = self.action_type_combo.currentData()
            
            # Горячая клавиша
            hotkey = self.hotkey_capture.label.text()
            self.current_command.hotkey = hotkey if hotkey != "Не выбрано" else None
            
            # Фразы
            phrases = []
            for i in range(self.phrases_list.count()):
                phrase = self.phrases_list.item(i).text().strip()
                if phrase:
                    phrases.append(phrase)
            self.current_command.phrases = phrases
            
            # Действия (пока что простая реализация)
            # В полной версии здесь была бы более сложная логика
            
            # Сохраняем в EVA Core
            success = self.eva_core.update_command(self.current_command)
            
            if success:
                # Обновляем список
                self._load_commands()
                
                # Показываем сообщение об успехе
                QMessageBox.information(self, "Сохранение", "Команда успешно сохранена!")
                
                self.is_editing = False
                self.save_command_btn.setEnabled(False)
                self.cancel_btn.setEnabled(False)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить команду!")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении команды: {e}")
    
    def _save_all_commands(self):
        """Сохранить все команды"""
        try:
            # Сохраняем текущую команду если редактируется
            if self.is_editing:
                self._save_current_command()
            
            QMessageBox.information(self, "Сохранение", "Все команды сохранены!")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {e}")
    
    def _cancel_editing(self):
        """Отменить редактирование"""
        self._clear_editor()
        self.is_editing = False
        self.save_command_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
    
    def _clear_editor(self):
        """Очистить редактор"""
        self.command_id_edit.clear()
        self.command_name_edit.clear()
        self.command_description_edit.clear()
        self.enabled_checkbox.setChecked(True)
        self.action_type_combo.setCurrentIndex(0)
        self.hotkey_capture.set_keys("")
        self.actions_table.setRowCount(0)
        self.phrases_list.clear()
        self.current_command = None
    
    # Обработчики событий
    def _on_command_changed(self):
        """Обработка изменения команды"""
        if self.is_editing:
            self.save_command_btn.setEnabled(True)
    
    def _on_hotkey_captured(self, key_combination: str):
        """Обработка захвата горячей клавиши"""
        if self.is_editing:
            self.save_command_btn.setEnabled(True)
    
    def _clear_hotkey(self):
        """Очистить горячую клавишу"""
        self.hotkey_capture.set_keys("")
        if self.is_editing:
            self.save_command_btn.setEnabled(True)
    
    # Методы для работы с действиями
    def _add_key_action(self):
        """Добавить действие клавиши"""
        # Простая реализация - добавляем строку в таблицу
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        
        self.actions_table.setItem(row, 0, QTableWidgetItem("key_combination"))
        self.actions_table.setItem(row, 1, QTableWidgetItem("Keys: Ctrl+C"))
        self.actions_table.setItem(row, 2, QTableWidgetItem("0s"))
        self.actions_table.setItem(row, 3, QTableWidgetItem("Новое действие клавиши"))
        
        if self.is_editing:
            self.save_command_btn.setEnabled(True)
    
    def _add_text_action(self):
        """Добавить действие ввода текста"""
        text, ok = QInputDialog.getText(self, "Ввод текста", "Введите текст для ввода:")
        if ok and text:
            row = self.actions_table.rowCount()
            self.actions_table.insertRow(row)
            
            self.actions_table.setItem(row, 0, QTableWidgetItem("type_text"))
            self.actions_table.setItem(row, 1, QTableWidgetItem(f"Text: {text}"))
            self.actions_table.setItem(row, 2, QTableWidgetItem("0s"))
            self.actions_table.setItem(row, 3, QTableWidgetItem("Ввод текста"))
            
            if self.is_editing:
                self.save_command_btn.setEnabled(True)
    
    def _add_delay_action(self):
        """Добавить действие задержки"""
        duration, ok = QInputDialog.getDouble(
            self, "Задержка", "Введите длительность задержки (секунды):",
            value=1.0, min=0.1, max=60.0, decimals=1
        )
        if ok:
            row = self.actions_table.rowCount()
            self.actions_table.insertRow(row)
            
            self.actions_table.setItem(row, 0, QTableWidgetItem("delay"))
            self.actions_table.setItem(row, 1, QTableWidgetItem(f"Duration: {duration}s"))
            self.actions_table.setItem(row, 2, QTableWidgetItem("0s"))
            self.actions_table.setItem(row, 3, QTableWidgetItem("Задержка"))
            
            if self.is_editing:
                self.save_command_btn.setEnabled(True)
    
    def _remove_action(self):
        """Удалить выбранное действие"""
        current_row = self.actions_table.currentRow()
        if current_row >= 0:
            self.actions_table.removeRow(current_row)
            if self.is_editing:
                self.save_command_btn.setEnabled(True)
    
    # Методы для работы с фразами
    def _add_phrase(self):
        """Добавить фразу"""
        phrase = self.new_phrase_edit.text().strip()
        if phrase:
            # Проверяем, что фраза не существует
            for i in range(self.phrases_list.count()):
                if self.phrases_list.item(i).text() == phrase:
                    QMessageBox.warning(self, "Предупреждение", "Такая фраза уже существует!")
                    return
            
            item = QListWidgetItem(phrase)
            self.phrases_list.addItem(item)
            self.new_phrase_edit.clear()
            
            if self.is_editing:
                self.save_command_btn.setEnabled(True)
    
    def _edit_phrase(self):
        """Редактировать выбранную фразу"""
        current_item = self.phrases_list.currentItem()
        if current_item:
            old_phrase = current_item.text()
            new_phrase, ok = QInputDialog.getText(
                self, "Редактирование фразы", "Фраза:", text=old_phrase
            )
            if ok and new_phrase.strip() and new_phrase != old_phrase:
                current_item.setText(new_phrase.strip())
                if self.is_editing:
                    self.save_command_btn.setEnabled(True)
    
    def _remove_phrase(self):
        """Удалить выбранную фразу"""
        current_row = self.phrases_list.currentRow()
        if current_row >= 0:
            self.phrases_list.takeItem(current_row)
            if self.is_editing:
                self.save_command_btn.setEnabled(True)