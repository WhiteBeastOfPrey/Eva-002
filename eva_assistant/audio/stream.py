import queue
import threading
import logging
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from ..config import SAMPLE_RATE, CHANNELS, BLOCK_DURATION_SECONDS

logger = logging.getLogger(__name__)


class AudioStream:
	def __init__(self) -> None:
		self._q: "queue.Queue[np.ndarray]" = queue.Queue()
		self._stream: Optional[sd.InputStream] = None
		self._running = False
		self._level_rms: float = 0.0
		self._on_level: Optional[Callable[[float], None]] = None

	def set_level_callback(self, cb: Callable[[float], None]) -> None:
		self._on_level = cb

	def _callback(self, indata, frames, time_info, status) -> None:  # sd callback thread
		if status:
			logger.debug("Audio status: %s", status)
		mono = np.mean(indata, axis=1).astype(np.float32)
		self._q.put_nowait(mono.copy())
		# level meter
		rms = float(np.sqrt(np.mean(np.square(mono))))
		self._level_rms = rms
		if self._on_level is not None:
			try:
				self._on_level(rms)
			except Exception:
				pass

	def start(self) -> None:
		if self._running:
			return
		blocksize = int(SAMPLE_RATE * BLOCK_DURATION_SECONDS)
		self._stream = sd.InputStream(
			samplerate=SAMPLE_RATE,
			channels=CHANNELS,
			blocksize=blocksize,
			callback=self._callback,
			dtype="float32",
		)
		self._stream.start()
		self._running = True
		logger.info("Audio stream started %d Hz, blocksize=%d", SAMPLE_RATE, blocksize)

	def stop(self) -> None:
		if not self._running:
			return
		try:
			assert self._stream is not None
			self._stream.stop()
			self._stream.close()
		except Exception:
			pass
		self._running = False
		logger.info("Audio stream stopped")

	def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
		try:
			return self._q.get(timeout=timeout)
		except queue.Empty:
			return None

	@property
	def level_rms(self) -> float:
		return self._level_rms