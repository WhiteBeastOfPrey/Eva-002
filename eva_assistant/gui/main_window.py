"""
Основное окно GUI EVA Assistant на PySide6
"""

import asyncio
import sys
import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QProgressBar, QGroupBox,
    QRadioButton, QSlider, QSpinBox, QStatusBar, QSplitter,
    QListWidget, QListWidgetItem, QTabWidget, QCheckBox,
    QGridLayout, QFrame, QMessageBox, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QObject, QSize
)
from PySide6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QAction
)

from ..core.eva_core import EVACore, EVAState
from ..modules.logger_config import setup_logging
from .equalizer_widget import EqualizerWidget
from .command_editor import CommandEditorWindow

logger = logging.getLogger(__name__)


class EVAWorkerSignals(QObject):
    """Сигналы для работы с EVA в отдельном потоке"""
    state_changed = Signal(object)  # EVAState
    wake_word_detected = Signal(str)
    speech_recognized = Signal(str)
    command_executed = Signal(object)
    audio_level = Signal(float)
    error = Signal(str)
    status_updated = Signal(dict)


class EVAWorkerThread(QThread):
    """Поток для работы EVA Assistant"""
    
    def __init__(self, eva_core: EVACore):
        super().__init__()
        self.eva_core = eva_core
        self.signals = EVAWorkerSignals()
        self.is_running = False
        
        # Подключаем callbacks
        self.eva_core.set_callbacks(
            on_state_changed=self._on_state_changed,
            on_wake_word_detected=self._on_wake_word_detected,
            on_speech_recognized=self._on_speech_recognized,
            on_command_executed=self._on_command_executed,
            on_audio_level=self._on_audio_level,
            on_error=self._on_error
        )
    
    def run(self):
        """Основной цикл потока"""
        self.is_running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._run_eva())
        except Exception as e:
            logger.error(f"EVA worker thread error: {e}")
            self.signals.error.emit(str(e))
        finally:
            loop.close()
    
    async def _run_eva(self):
        """Запуск EVA Assistant"""
        try:
            success = await self.eva_core.start()
            if not success:
                self.signals.error.emit("Failed to start EVA Assistant")
                return
            
            # Основной цикл - просто ждем
            while self.is_running:
                await asyncio.sleep(0.1)
                
                # Периодически отправляем статус
                status = self.eva_core.get_status()
                self.signals.status_updated.emit(status)
                
        except Exception as e:
            logger.error(f"EVA run error: {e}")
            self.signals.error.emit(str(e))
    
    async def stop_eva(self):
        """Остановка EVA Assistant"""
        try:
            await self.eva_core.stop()
        except Exception as e:
            logger.error(f"Error stopping EVA: {e}")
    
    def stop_thread(self):
        """Остановка потока"""
        self.is_running = False
        
        # Создаем новый event loop для остановки EVA
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.stop_eva())
        finally:
            loop.close()
    
    # Callback методы
    async def _on_state_changed(self, state):
        self.signals.state_changed.emit(state)
    
    async def _on_wake_word_detected(self, text):
        self.signals.wake_word_detected.emit(text)
    
    async def _on_speech_recognized(self, text):
        self.signals.speech_recognized.emit(text)
    
    async def _on_command_executed(self, command):
        self.signals.command_executed.emit(command)
    
    async def _on_audio_level(self, level):
        self.signals.audio_level.emit(level)
    
    async def _on_error(self, error):
        self.signals.error.emit(error)


class EVAMainWindow(QMainWindow):
    """Основное окно EVA Assistant"""
    
    def __init__(self):
        super().__init__()
        
        # Настройка логирования
        setup_logging(log_level="INFO", console_output=True)
        
        # Инициализация EVA Core
        self.eva_core = EVACore()
        self.eva_worker: Optional[EVAWorkerThread] = None
        
        # UI компоненты
        self.equalizer_widget: Optional[EqualizerWidget] = None
        self.command_editor: Optional[CommandEditorWindow] = None
        
        # Состояние
        self.is_eva_running = False
        
        # Настройка UI
        self._setup_ui()
        self._setup_tray_icon()
        self._connect_signals()
        
        # Таймеры
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # Обновление каждую секунду
        
        logger.info("EVA Main Window initialized")
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("EVA Assistant v1.0")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        
        # Создаем сплиттер
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель - управление
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - информация и логи
        right_panel = self._create_info_panel()
        splitter.addWidget(right_panel)
        
        # Устанавливаем пропорции
        splitter.setSizes([300, 500])
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("EVA Assistant готов к запуску")
        
        # Применяем стиль
        self._apply_dark_theme()
    
    def _create_control_panel(self) -> QWidget:
        """Создать панель управления"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Группа управления
        control_group = QGroupBox("Управление")
        control_layout = QVBoxLayout(control_group)
        
        # Кнопки управления
        self.start_button = QPushButton("▶ Запустить EVA")
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._start_eva)
        
        self.stop_button = QPushButton("⏸ Остановить EVA")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_eva)
        
        self.force_stop_button = QPushButton("⏹ Принудительная остановка")
        self.force_stop_button.setMinimumHeight(30)
        self.force_stop_button.setEnabled(False)
        self.force_stop_button.clicked.connect(self._force_stop_eva)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.force_stop_button)
        
        # Группа режимов
        mode_group = QGroupBox("Режим работы")
        mode_layout = QVBoxLayout(mode_group)
        
        self.online_radio = QRadioButton("Онлайн режим")
        self.online_radio.setChecked(True)
        self.online_radio.toggled.connect(self._mode_changed)
        
        self.offline_radio = QRadioButton("Оффлайн режим")
        self.offline_radio.toggled.connect(self._mode_changed)
        
        mode_layout.addWidget(self.online_radio)
        mode_layout.addWidget(self.offline_radio)
        
        # Группа настроек
        settings_group = QGroupBox("Настройки")
        settings_layout = QGridLayout(settings_group)
        
        # Порог wake-word
        settings_layout.addWidget(QLabel("Порог wake-word:"), 0, 0)
        self.wake_word_slider = QSlider(Qt.Horizontal)
        self.wake_word_slider.setRange(50, 95)
        self.wake_word_slider.setValue(65)
        self.wake_word_slider.valueChanged.connect(self._wake_word_threshold_changed)
        settings_layout.addWidget(self.wake_word_slider, 0, 1)
        
        self.wake_word_value = QLabel("65%")
        settings_layout.addWidget(self.wake_word_value, 0, 2)
        
        # Порог команд
        settings_layout.addWidget(QLabel("Порог команд:"), 1, 0)
        self.command_slider = QSlider(Qt.Horizontal)
        self.command_slider.setRange(50, 95)
        self.command_slider.setValue(65)
        self.command_slider.valueChanged.connect(self._command_threshold_changed)
        settings_layout.addWidget(self.command_slider, 1, 1)
        
        self.command_value = QLabel("65%")
        settings_layout.addWidget(self.command_value, 1, 2)
        
        # Эквалайзер
        equalizer_group = QGroupBox("Индикатор аудио")
        equalizer_layout = QVBoxLayout(equalizer_group)
        
        self.equalizer_widget = EqualizerWidget()
        equalizer_layout.addWidget(self.equalizer_widget)
        
        # Кнопки дополнительных окон
        buttons_group = QGroupBox("Дополнительно")
        buttons_layout = QVBoxLayout(buttons_group)
        
        self.command_editor_button = QPushButton("📝 Редактор команд")
        self.command_editor_button.clicked.connect(self._open_command_editor)
        
        buttons_layout.addWidget(self.command_editor_button)
        
        # Добавляем все группы в панель
        layout.addWidget(control_group)
        layout.addWidget(mode_group)
        layout.addWidget(settings_group)
        layout.addWidget(equalizer_group)
        layout.addWidget(buttons_group)
        layout.addStretch()
        
        return panel
    
    def _create_info_panel(self) -> QWidget:
        """Создать информационную панель"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Вкладки
        tab_widget = QTabWidget()
        
        # Вкладка статуса
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        
        # Статус EVA
        status_group = QGroupBox("Статус EVA")
        status_group_layout = QGridLayout(status_group)
        
        status_group_layout.addWidget(QLabel("Состояние:"), 0, 0)
        self.state_label = QLabel("Остановлен")
        self.state_label.setStyleSheet("font-weight: bold; color: #ff6b6b;")
        status_group_layout.addWidget(self.state_label, 0, 1)
        
        status_group_layout.addWidget(QLabel("Платформа:"), 1, 0)
        self.platform_label = QLabel("Определение...")
        status_group_layout.addWidget(self.platform_label, 1, 1)
        
        status_group_layout.addWidget(QLabel("Wake-word обнаружено:"), 2, 0)
        self.wake_word_count = QLabel("0")
        status_group_layout.addWidget(self.wake_word_count, 2, 1)
        
        status_group_layout.addWidget(QLabel("Команд выполнено:"), 3, 0)
        self.commands_count = QLabel("0")
        status_group_layout.addWidget(self.commands_count, 3, 1)
        
        # Распознанная речь
        speech_group = QGroupBox("Распознанная речь")
        speech_layout = QVBoxLayout(speech_group)
        
        self.speech_text = QTextEdit()
        self.speech_text.setMaximumHeight(100)
        self.speech_text.setReadOnly(True)
        speech_layout.addWidget(self.speech_text)
        
        status_layout.addWidget(status_group)
        status_layout.addWidget(speech_group)
        status_layout.addStretch()
        
        # Вкладка логов
        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        # Кнопки управления логами
        log_buttons = QHBoxLayout()
        clear_logs_button = QPushButton("Очистить")
        clear_logs_button.clicked.connect(self.log_text.clear)
        log_buttons.addWidget(clear_logs_button)
        log_buttons.addStretch()
        
        logs_layout.addWidget(self.log_text)
        logs_layout.addLayout(log_buttons)
        
        # Вкладка команд
        commands_tab = QWidget()
        commands_layout = QVBoxLayout(commands_tab)
        
        self.commands_list = QListWidget()
        self._update_commands_list()
        
        commands_layout.addWidget(QLabel("Доступные команды:"))
        commands_layout.addWidget(self.commands_list)
        
        # Добавляем вкладки
        tab_widget.addTab(status_tab, "Статус")
        tab_widget.addTab(logs_tab, "Логи")
        tab_widget.addTab(commands_tab, "Команды")
        
        layout.addWidget(tab_widget)
        
        return panel
    
    def _setup_tray_icon(self):
        """Настройка иконки в системном трее"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # Создаем меню для трея
        tray_menu = QMenu()
        
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self._quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Устанавливаем иконку (можно заменить на собственную)
        self.tray_icon.setToolTip("EVA Assistant")
        self.tray_icon.show()
    
    def _connect_signals(self):
        """Подключение сигналов"""
        pass
    
    def _apply_dark_theme(self):
        """Применить темную тему"""
        dark_palette = QPalette()
        
        # Цвета темной темы
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        
        self.setPalette(dark_palette)
    
    # Слоты для управления EVA
    def _start_eva(self):
        """Запуск EVA Assistant"""
        if self.is_eva_running:
            return
        
        try:
            # Создаем и запускаем worker поток
            self.eva_worker = EVAWorkerThread(self.eva_core)
            
            # Подключаем сигналы
            self.eva_worker.signals.state_changed.connect(self._on_state_changed)
            self.eva_worker.signals.wake_word_detected.connect(self._on_wake_word_detected)
            self.eva_worker.signals.speech_recognized.connect(self._on_speech_recognized)
            self.eva_worker.signals.command_executed.connect(self._on_command_executed)
            self.eva_worker.signals.audio_level.connect(self._on_audio_level)
            self.eva_worker.signals.error.connect(self._on_error)
            self.eva_worker.signals.status_updated.connect(self._on_status_updated)
            
            self.eva_worker.start()
            
            self.is_eva_running = True
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.force_stop_button.setEnabled(True)
            
            self._log_message("EVA Assistant запущен")
            
        except Exception as e:
            self._show_error(f"Ошибка запуска EVA: {e}")
    
    def _stop_eva(self):
        """Остановка EVA Assistant"""
        if not self.is_eva_running or not self.eva_worker:
            return
        
        try:
            self.eva_worker.stop_thread()
            self.eva_worker.wait(5000)  # Ждем 5 секунд
            
            self.is_eva_running = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.force_stop_button.setEnabled(False)
            
            self._log_message("EVA Assistant остановлен")
            
        except Exception as e:
            self._show_error(f"Ошибка остановки EVA: {e}")
    
    def _force_stop_eva(self):
        """Принудительная остановка EVA Assistant"""
        if not self.is_eva_running or not self.eva_worker:
            return
        
        try:
            self.eva_worker.terminate()
            self.eva_worker.wait(2000)
            
            self.is_eva_running = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.force_stop_button.setEnabled(False)
            
            self._log_message("EVA Assistant принудительно остановлен")
            
        except Exception as e:
            self._show_error(f"Ошибка принудительной остановки EVA: {e}")
    
    # Слоты для настроек
    def _mode_changed(self):
        """Изменение режима работы"""
        online_mode = self.online_radio.isChecked()
        self.eva_core.set_online_mode(online_mode)
        mode_text = "онлайн" if online_mode else "оффлайн"
        self._log_message(f"Режим изменен на: {mode_text}")
    
    def _wake_word_threshold_changed(self, value):
        """Изменение порога wake-word"""
        self.wake_word_value.setText(f"{value}%")
        self.eva_core.set_wake_word_threshold(value)
    
    def _command_threshold_changed(self, value):
        """Изменение порога команд"""
        self.command_value.setText(f"{value}%")
        self.eva_core.set_command_threshold(value)
    
    def _open_command_editor(self):
        """Открыть редактор команд"""
        if not self.command_editor:
            self.command_editor = CommandEditorWindow(self.eva_core)
        
        self.command_editor.show()
        self.command_editor.raise_()
    
    # Слоты для обработки сигналов EVA
    def _on_state_changed(self, state: EVAState):
        """Обработка изменения состояния EVA"""
        state_colors = {
            EVAState.STOPPED: "#ff6b6b",
            EVAState.INITIALIZING: "#ffa726",
            EVAState.LISTENING_WAKE_WORD: "#4fc3f7",
            EVAState.LISTENING_COMMAND: "#66bb6a",
            EVAState.PROCESSING_COMMAND: "#ffee58",
            EVAState.EXECUTING_COMMAND: "#ab47bc",
            EVAState.ERROR: "#f44336"
        }
        
        state_names = {
            EVAState.STOPPED: "Остановлен",
            EVAState.INITIALIZING: "Инициализация",
            EVAState.LISTENING_WAKE_WORD: "Слушает wake-word",
            EVAState.LISTENING_COMMAND: "Слушает команду",
            EVAState.PROCESSING_COMMAND: "Обрабатывает команду",
            EVAState.EXECUTING_COMMAND: "Выполняет команду",
            EVAState.ERROR: "Ошибка"
        }
        
        name = state_names.get(state, state.value)
        color = state_colors.get(state, "#ffffff")
        
        self.state_label.setText(name)
        self.state_label.setStyleSheet(f"font-weight: bold; color: {color};")
        
        self.status_bar.showMessage(f"EVA: {name}")
    
    def _on_wake_word_detected(self, text: str):
        """Обработка обнаружения wake-word"""
        self._log_message(f"Wake-word обнаружен: {text}")
        
        # Обновляем счетчик
        current = int(self.wake_word_count.text())
        self.wake_word_count.setText(str(current + 1))
    
    def _on_speech_recognized(self, text: str):
        """Обработка распознанной речи"""
        self.speech_text.append(f"[{self._get_current_time()}] {text}")
        self._log_message(f"Распознана речь: {text}")
    
    def _on_command_executed(self, command):
        """Обработка выполненной команды"""
        self._log_message(f"Выполнена команда: {command.name}")
        
        # Обновляем счетчик
        current = int(self.commands_count.text())
        self.commands_count.setText(str(current + 1))
    
    def _on_audio_level(self, level: float):
        """Обработка уровня аудио"""
        if self.equalizer_widget:
            self.equalizer_widget.update_level(level)
    
    def _on_error(self, error: str):
        """Обработка ошибки"""
        self._show_error(error)
        self._log_message(f"ОШИБКА: {error}")
    
    def _on_status_updated(self, status: dict):
        """Обновление статуса"""
        # Обновляем информацию о платформе
        platform = status.get('platform', 'unknown')
        self.platform_label.setText(platform)
        
        # Обновляем статистику
        stats = status.get('statistics', {})
        self.wake_word_count.setText(str(stats.get('wake_words_detected', 0)))
        self.commands_count.setText(str(stats.get('commands_executed', 0)))
    
    # Вспомогательные методы
    def _update_status(self):
        """Периодическое обновление статуса"""
        if not self.is_eva_running:
            return
        
        # Здесь можно добавить дополнительную логику обновления
        pass
    
    def _update_commands_list(self):
        """Обновить список команд"""
        self.commands_list.clear()
        
        commands = self.eva_core.get_commands()
        for command in commands:
            item = QListWidgetItem(f"{command.name} - {', '.join(command.phrases[:2])}")
            item.setToolTip(command.description)
            self.commands_list.addItem(item)
    
    def _log_message(self, message: str):
        """Добавить сообщение в лог"""
        timestamp = self._get_current_time()
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        
        # Автопрокрутка
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _get_current_time(self) -> str:
        """Получить текущее время в формате строки"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def _show_error(self, message: str):
        """Показать сообщение об ошибке"""
        QMessageBox.critical(self, "Ошибка EVA Assistant", message)
    
    def _quit_application(self):
        """Выход из приложения"""
        if self.is_eva_running:
            self._force_stop_eva()
        
        QApplication.quit()
    
    # Обработка событий окна
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.tray_icon and self.tray_icon.isVisible():
            # Сворачиваем в трей
            self.hide()
            event.ignore()
        else:
            # Закрываем приложение
            self._quit_application()
            event.accept()


def main():
    """Главная функция для запуска GUI"""
    app = QApplication(sys.argv)
    app.setApplicationName("EVA Assistant")
    app.setApplicationVersion("1.0")
    
    # Создаем и показываем главное окно
    window = EVAMainWindow()
    window.show()
    
    return app.exec()