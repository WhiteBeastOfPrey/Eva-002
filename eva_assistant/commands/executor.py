import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
	import pydirectinput as pdi
	_has_pdi = True
	# Make pydirectinput faster
	pdi.PAUSE = 0.02
except Exception:
	_has_pdi = False

try:
	import pyautogui as pag
	_has_pag = True
	pag.PAUSE = 0.02
except Exception:
	_has_pag = False


class CommandExecutor:
	def __init__(self) -> None:
		if not (_has_pdi or _has_pag):
			logger.warning("Neither pydirectinput nor pyautogui available. Execution will be no-op.")

	def _press_combo(self, combo: str, hold_ms: int) -> None:
		keys = [k.strip() for k in combo.lower().split('+') if k.strip()]
		if not keys:
			return
		if _has_pdi:
			for k in keys:
				pdi.keyDown(k)
			time.sleep(max(hold_ms, 0) / 1000.0)
			for k in reversed(keys):
				pdi.keyUp(k)
		elif _has_pag:
			for k in keys:
				pag.keyDown(k)
			time.sleep(max(hold_ms, 0) / 1000.0)
			for k in reversed(keys):
				pag.keyUp(k)
		else:
			logger.debug("No input backend. Skipping combo: %s", combo)

	def execute(self, cmd: Dict[str, Any]) -> None:
		type_ = cmd.get("type", "keys")
		if type_ == "keys":
			keys: List[str] = cmd.get("keys", [])
			hold_ms: int = int(cmd.get("hold_ms", 30))
			for combo in keys:
				logger.info("Execute combo: %s (%d ms)", combo, hold_ms)
				self._press_combo(combo, hold_ms)
		elif type_ == "text":
			text = cmd.get("text", "")
			logger.info("Typing text: %s", text)
			if _has_pag:
				pag.write(text)
			elif _has_pdi:
				for ch in text:
					pdi.typewrite(ch)
			else:
				logger.debug("No input backend. Skipping text typing")
		else:
			logger.warning("Unknown command type: %s", type_)