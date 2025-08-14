import logging
from typing import Optional

import speech_recognition as sr

from ..config import SAMPLE_RATE

logger = logging.getLogger(__name__)


class OnlineRecognizer:
	def __init__(self, language: str = "ru-RU") -> None:
		self.recognizer = sr.Recognizer()
		self.language = language

	def recognize_block(self, pcm_float_mono) -> Optional[str]:
		"""Recognize a short block by feeding it as AudioData to Google Web Speech.
		This is synchronous and may be slower; used for demo purposes.
		"""
		import numpy as np
		# Convert to 16-bit PCM
		pcm16 = (pcm_float_mono * 32767.0).astype('<i2').tobytes()
		audio_data = sr.AudioData(pcm16, SAMPLE_RATE, 2)
		try:
			text = self.recognizer.recognize_google(audio_data, language=self.language)
			return text.lower().strip()
		except sr.UnknownValueError:
			return None
		except Exception as exc:
			logger.debug("Online recognition error: %s", exc)
			return None