import sys
import json
import math
import threading
import logging
from typing import List, Dict, Any, Set

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
	QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
	QPushButton, QTextEdit, QComboBox, QProgressBar, QMessageBox,
	QDialog, QFormLayout, QLineEdit, QListWidget, QListWidgetItem,
	QSpinBox, QDialogButtonBox
)

from ..config import APP_TITLE, DEFAULT_FUZZY_THRESHOLD
from ..logging_setup import init_logging
from ..runtime.assistant import AssistantRuntime
from ..commands.loader import load_commands, save_commands
from ..process.manager import list_process_names
from ..platform_utils import activate_application

logger = init_logging(__name__)


class KeyCaptureDialog(QDialog):
	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.setWindowTitle("Захват сочетания клавиш")
		self.resize(400, 120)
		self.label = QLabel("Нажмите сочетание клавиш…")
		self.output = QLineEdit(); self.output.setReadOnly(True)
		layout = QVBoxLayout()
		layout.addWidget(self.label)
		layout.addWidget(self.output)
		self.setLayout(layout)
		self._pressed: Set[int] = set()
		self._result: str = ""
		self.setModal(True)

	def keyPressEvent(self, event: QKeyEvent) -> None:
		self._pressed.add(event.key())
		combo = self._format_combo()
		self.output.setText(combo)

	def keyReleaseEvent(self, event: QKeyEvent) -> None:
		# finalize on full release
		self._pressed.discard(event.key())
		if not self._pressed:
			self._result = self.output.text().strip()
			self.accept()

	@staticmethod
	def _key_to_name(k: int) -> str:
		# map Qt keys to common names used by input libs
		map_simple = {
			Qt.Key_Control: "ctrl",
			Qt.Key_Shift: "shift",
			Qt.Key_Alt: "alt",
			Qt.Key_Meta: "win",
			Qt.Key_Return: "enter",
			Qt.Key_Enter: "enter",
			Qt.Key_Space: "space",
			Qt.Key_Tab: "tab",
			Qt.Key_Escape: "esc",
			Qt.Key_Backspace: "backspace",
			Qt.Key_Left: "left",
			Qt.Key_Right: "right",
			Qt.Key_Up: "up",
			Qt.Key_Down: "down",
		}
		if k in map_simple:
			return map_simple[k]
		if Qt.Key_F1 <= k <= Qt.Key_F35:
			return f"f{k - Qt.Key_F1 + 1}"
		# letters and digits
		if Qt.Key_A <= k <= Qt.Key_Z:
			return chr(k).lower()
		if Qt.Key_0 <= k <= Qt.Key_9:
			return chr(k)
		return str(k)

	def _format_combo(self) -> str:
		names = []
		mods = []
		normal = []
		for k in self._pressed:
			name = self._key_to_name(k)
			if name in ("ctrl", "shift", "alt", "win"):
				mods.append(name)
			else:
				normal.append(name)
		mods.sort()
		normal.sort()
		return "+".join(mods + normal)

	def result_combo(self) -> str:
		return self._result


class CommandEditor(QDialog):
	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.setWindowTitle("Редактор команд")
		self.resize(600, 450)

		self.list = QListWidget()
		self.phrase = QLineEdit()
		self.keys = QLineEdit()
		self.hold = QSpinBox(); self.hold.setRange(0, 5000); self.hold.setValue(30)
		self.btn_capture = QPushButton("Захват сочетания")
		self.btn_capture.clicked.connect(self.on_capture)

		form = QFormLayout()
		form.addRow("Фраза:", self.phrase)
		form.addRow("Клавиши (через запятую):", self.keys)
		form.addRow("Удержание, мс:", self.hold)

		btn_add = QPushButton("Добавить/Обновить")
		btn_del = QPushButton("Удалить")
		btn_add.clicked.connect(self.on_add_update)
		btn_del.clicked.connect(self.on_delete)

		buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
		buttons.accepted.connect(self.accept)
		buttons.rejected.connect(self.reject)

		layout = QVBoxLayout()
		layout.addWidget(self.list)
		layout.addLayout(form)
		layout.addWidget(self.btn_capture)
		layout.addWidget(btn_add)
		layout.addWidget(btn_del)
		layout.addWidget(buttons)
		self.setLayout(layout)

		self._load()
		self.list.currentItemChanged.connect(self.on_select)

	def _load(self) -> None:
		self.commands = load_commands()
		self.refresh_list()

	def refresh_list(self) -> None:
		self.list.clear()
		for cmd in self.commands:
			item = QListWidgetItem(cmd.get("phrase", ""))
			item.setData(Qt.UserRole, cmd)
			self.list.addItem(item)

	def on_select(self, current: QListWidgetItem) -> None:
		if not current:
			return
		cmd = current.data(Qt.UserRole)
		self.phrase.setText(cmd.get("phrase", ""))
		self.keys.setText(", ".join(cmd.get("keys", [])))
		self.hold.setValue(int(cmd.get("hold_ms", 30)))

	def on_capture(self) -> None:
		dlg = KeyCaptureDialog(self)
		if dlg.exec() == QDialog.Accepted:
			combo = dlg.result_combo()
			if combo:
				text = self.keys.text().strip()
				self.keys.setText((text + ", " if text else "") + combo)

	def on_add_update(self) -> None:
		phrase = self.phrase.text().strip()
		keys = [k.strip() for k in self.keys.text().split(',') if k.strip()]
		hold = int(self.hold.value())
		if not phrase:
			return
		# update if exists
		for cmd in self.commands:
			if cmd.get("phrase", "") == phrase:
				cmd.update({"type": "keys", "keys": keys, "hold_ms": hold})
				self.refresh_list()
				self._select_phrase(phrase)
				save_commands(self.commands)
				return
		self.commands.append({"phrase": phrase, "type": "keys", "keys": keys, "hold_ms": hold})
		save_commands(self.commands)
		self.refresh_list()
		self._select_phrase(phrase)

	def _select_phrase(self, phrase: str) -> None:
		for i in range(self.list.count()):
			item = self.list.item(i)
			if item.text() == phrase:
				self.list.setCurrentItem(item)
				break

	def on_delete(self) -> None:
		current = self.list.currentItem()
		if not current:
			return
		cmd = current.data(Qt.UserRole)
		phrase = cmd.get("phrase", "")
		self.commands = [c for c in self.commands if c.get("phrase", "") != phrase]
		save_commands(self.commands)
		self.refresh_list()


class MainWindow(QWidget):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle(APP_TITLE)
		self.resize(1000, 680)

		self.mode = QComboBox(); self.mode.addItems(["offline", "online"])
		self.threshold = QSpinBox(); self.threshold.setRange(0, 100); self.threshold.setValue(int(DEFAULT_FUZZY_THRESHOLD))
		self.btn_start = QPushButton("Старт")
		self.btn_stop = QPushButton("Стоп")
		self.btn_stop.setEnabled(False)
		self.btn_edit = QPushButton("Редактор команд")

		self.proc_box = QComboBox(); self.btn_proc_refresh = QPushButton("Обновить процессы"); self.btn_proc_activate = QPushButton("Активировать")

		self.log = QTextEdit(); self.log.setReadOnly(True)
		self.level = QProgressBar(); self.level.setRange(0, 100)
		self.status = QLabel("Ожидание...")

		row = QHBoxLayout()
		row.addWidget(QLabel("Режим:"))
		row.addWidget(self.mode)
		row.addWidget(QLabel("Порог (%):"))
		row.addWidget(self.threshold)
		row.addStretch(1)
		row.addWidget(self.btn_edit)
		row.addWidget(self.btn_start)
		row.addWidget(self.btn_stop)

		prow = QHBoxLayout()
		prow.addWidget(QLabel("Процесс:"))
		prow.addWidget(self.proc_box, 1)
		prow.addWidget(self.btn_proc_refresh)
		prow.addWidget(self.btn_proc_activate)

		layout = QVBoxLayout()
		layout.addLayout(row)
		layout.addLayout(prow)
		layout.addWidget(QLabel("Распознанный текст:"))
		layout.addWidget(self.log, 1)
		layout.addWidget(QLabel("Индикатор уровня (эквалайзер):"))
		layout.addWidget(self.level)
		layout.addWidget(self.status)
		self.setLayout(layout)

		self.assistant: AssistantRuntime | None = None

		self.btn_start.clicked.connect(self.on_start)
		self.btn_stop.clicked.connect(self.on_stop)
		self.btn_edit.clicked.connect(self.on_edit)
		self.btn_proc_refresh.clicked.connect(self.on_proc_refresh)
		self.btn_proc_activate.clicked.connect(self.on_proc_activate)

		self.timer = QTimer(self)
		self.timer.setInterval(100)
		self.timer.timeout.connect(self.on_tick)

		self.on_proc_refresh()

	def on_proc_refresh(self) -> None:
		self.proc_box.clear()
		try:
			names = list_process_names()
			self.proc_box.addItems(names)
		except Exception:
			self.proc_box.addItem("<недоступно>")

	def on_proc_activate(self) -> None:
		name = self.proc_box.currentText().strip()
		if not name or name == "<недоступно>":
			return
		ok = activate_application(name)
		if not ok:
			QMessageBox.information(self, "Инфо", "Не удалось активировать процесс (ограничения ОС)")

	def on_edit(self) -> None:
		dlg = CommandEditor(self)
		dlg.exec()

	def on_start(self) -> None:
		if self.assistant is not None:
			return
		mode = self.mode.currentText()
		self.assistant = AssistantRuntime(mode=mode)
		self.assistant.set_text_callback(self.on_text)
		self.assistant.set_level_callback(self.on_level)
		# set threshold dynamically
		AssistantRuntimeMatchConfig.threshold = int(self.threshold.value())
		try:
			self.assistant.start()
		except Exception as exc:
			logger.exception("Start failed")
			QMessageBox.critical(self, "Ошибка", str(exc))
			self.assistant = None
			return
		self.btn_start.setEnabled(False)
		self.btn_stop.setEnabled(True)
		self.status.setText("Работает")
		self.timer.start()

	def on_stop(self) -> None:
		if self.assistant is None:
			return
		self.assistant.stop()
		self.assistant = None
		self.btn_start.setEnabled(True)
		self.btn_stop.setEnabled(False)
		self.status.setText("Остановлено")
		self.timer.stop()

	def on_text(self, text: str) -> None:
		self.log.append(text)
		self.log.moveCursor(self.log.textCursor().End)

	def on_level(self, rms: float) -> None:
		# rms ~ 0..1, map to 0..100 with log scale
		val = 0 if rms <= 0 else min(100, int(20 * math.log10(max(rms, 1e-6)) + 100))
		self.level.setValue(max(0, val))

	def on_tick(self) -> None:
		pass


# Simple config holder to pass threshold to runtime matcher without changing API too much
class AssistantRuntimeMatchConfig:
	threshold: int = int(DEFAULT_FUZZY_THRESHOLD)


def main() -> None:
	app = QApplication(sys.argv)
	w = MainWindow()
	w.show()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()