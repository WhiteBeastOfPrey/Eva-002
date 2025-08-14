import json
import logging
from pathlib import Path
from typing import Optional

from vosk import Model, KaldiRecognizer

from ..config import MODELS_DIR, SAMPLE_RATE

logger = logging.getLogger(__name__)


class VoskRecognizer:
	def __init__(self, model_dir: Optional[Path] = None) -> None:
		self.model_dir = model_dir or (MODELS_DIR / "vosk-ru")
		self._model: Optional[Model] = None
		self._rec: Optional[KaldiRecognizer] = None

	def load(self) -> bool:
		if not self.model_dir.exists():
			logger.error("Vosk model not found: %s", self.model_dir)
			return False
		self._model = Model(str(self.model_dir))
		self._rec = KaldiRecognizer(self._model, SAMPLE_RATE)
		self._rec.SetWords(True)
		logger.info("Vosk model loaded from %s", self.model_dir)
		return True

	def accept_waveform(self, pcm_float_mono) -> Optional[str]:
		if self._rec is None:
			return None
		import numpy as np
		# Vosk expects 16-bit little endian PCM
		pcm16 = (pcm_float_mono * 32767.0).astype('<i2').tobytes()
		if self._rec.AcceptWaveform(pcm16):
			res = json.loads(self._rec.Result())
			return res.get("text", "").strip()
		else:
			partial = json.loads(self._rec.PartialResult())
			return partial.get("partial", "").strip()