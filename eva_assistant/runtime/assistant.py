import time
import threading
import logging
from typing import Optional, List, Dict, Any

from ..logging_setup import init_logging
from ..config import WAKE_WORDS, DEFAULT_FUZZY_THRESHOLD, COMMAND_LISTEN_WINDOW_SECONDS
from ..audio.stream import AudioStream
from ..recognition.vosk_recognizer import VoskRecognizer
from ..recognition.online_recognizer import OnlineRecognizer
from ..commands.loader import load_commands
from ..commands.matcher import best_match
from ..commands.executor import CommandExecutor

logger = init_logging(__name__)

# Threshold holder (set by GUI at runtime)
class MatchConfig:
	threshold: int = int(DEFAULT_FUZZY_THRESHOLD)


class AssistantRuntime:
	def __init__(self, mode: str = "offline") -> None:
		self.mode = mode  # "offline" | "online"
		self._audio = AudioStream()
		self._vosk: Optional[VoskRecognizer] = None
		self._online: Optional[OnlineRecognizer] = None
		self._running = False
		self._thread: Optional[threading.Thread] = None
		self._commands: List[Dict[str, Any]] = []
		self._executor = CommandExecutor()
		self._on_text: Optional[callable] = None
		self._on_level: Optional[callable] = None

	def set_text_callback(self, cb) -> None:
		self._on_text = cb

	def set_level_callback(self, cb) -> None:
		self._on_level = cb
		self._audio.set_level_callback(cb)

	def _emit_text(self, text: str) -> None:
		if self._on_text:
			try:
				self._on_text(text)
			except Exception:
				pass

	def start(self) -> None:
		if self._running:
			return
		self._commands = load_commands()
		if self.mode == "offline":
			self._vosk = VoskRecognizer()
			if not self._vosk.load():
				raise RuntimeError("Не найдена офлайн модель Vosk. См. README.md")
		else:
			self._online = OnlineRecognizer()

		self._audio.start()
		self._running = True
		self._thread = threading.Thread(target=self._run_loop, daemon=True)
		self._thread.start()
		logger.info("Assistant started in %s mode", self.mode)

	def stop(self) -> None:
		self._running = False
		self._audio.stop()
		logger.info("Assistant stopped")

	def _recognize_block(self, block) -> Optional[str]:
		if self.mode == "offline":
			assert self._vosk is not None
			return self._vosk.accept_waveform(block)
		else:
			assert self._online is not None
			return self._online.recognize_block(block)

	def _run_loop(self) -> None:
		state = "idle"
		deadline: float = 0.0
		while self._running:
			block = self._audio.read(timeout=0.2)
			if block is None:
				continue

			text = self._recognize_block(block)
			if text:
				self._emit_text(text)

			if state == "idle":
				if text and any(w in text.lower() for w in WAKE_WORDS):
					state = "listening_commands"
					deadline = time.time() + COMMAND_LISTEN_WINDOW_SECONDS
					logger.info("Wake word detected. Listening for commands...")
			elif state == "listening_commands":
				if text:
					threshold = int(getattr(MatchConfig, 'threshold', int(DEFAULT_FUZZY_THRESHOLD)))
					match = best_match(text, self._commands, threshold)
					if match:
						cmd, sc = match
						logger.info("Matched command '%s' (score=%d)", cmd.get("phrase"), sc)
						self._executor.execute(cmd)
						state = "idle"
						continue
				if time.time() > deadline:
					state = "idle"