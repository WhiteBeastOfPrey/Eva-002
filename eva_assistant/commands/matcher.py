from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

try:
	from rapidfuzz import fuzz, process
	exists_rapidfuzz = True
except Exception:
	exists_rapidfuzz = False
	try:
		from fuzzywuzzy import fuzz as fw_fuzz
	except Exception:  # pragma: no cover - fallback absence
		fw_fuzz = None


def score(a: str, b: str) -> int:
	a = (a or "").lower().strip()
	b = (b or "").lower().strip()
	if exists_rapidfuzz:
		return int(fuzz.token_set_ratio(a, b))
	elif fw_fuzz is not None:
		return int(fw_fuzz.token_set_ratio(a, b))
	else:
		# naive fallback
		return 100 if a == b else 0


def best_match(text: str, commands: List[Dict[str, Any]], threshold: int) -> Optional[Tuple[Dict[str, Any], int]]:
	best = None
	best_score = -1
	for cmd in commands:
		phrase = cmd.get("phrase", "")
		s = score(text, phrase)
		if s > best_score:
			best = cmd
			best_score = s
	if best is None:
		return None
	if best_score >= threshold:
		return best, best_score
	return None