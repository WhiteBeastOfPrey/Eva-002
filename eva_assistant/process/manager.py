import logging
from typing import List, Optional

import psutil

logger = logging.getLogger(__name__)


def list_process_names() -> List[str]:
	seen = set()
	names: List[str] = []
	for p in psutil.process_iter(attrs=["name"]):
		name = p.info.get("name") or ""
		if name and name not in seen:
			seen.add(name)
			names.append(name)
	names.sort()
	return names


def find_process_by_name(name: str) -> Optional[psutil.Process]:
	for p in psutil.process_iter(attrs=["name"]):
		if (p.info.get("name") or "").lower() == name.lower():
			return p
	return None