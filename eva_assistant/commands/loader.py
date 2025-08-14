import json
from pathlib import Path
from typing import List, Dict, Any

from ..config import COMMANDS_FILE

DEFAULT_COMMANDS: List[Dict[str, Any]] = [
	{
		"phrase": "открой меню",
		"type": "keys",
		"keys": ["alt+f"],
		"hold_ms": 50
	},
	{
		"phrase": "нажми ок",
		"type": "keys",
		"keys": ["enter"],
		"hold_ms": 30
	}
]


def ensure_default_commands(path: Path = COMMANDS_FILE) -> None:
	if not path.exists():
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(DEFAULT_COMMANDS, ensure_ascii=False, indent=2), encoding="utf-8")


def load_commands(path: Path = COMMANDS_FILE) -> List[Dict[str, Any]]:
	ensure_default_commands(path)
	with path.open("r", encoding="utf-8") as f:
		data = json.load(f)
	if not isinstance(data, list):
		raise ValueError("commands.json must contain a list of commands")
	return data


def save_commands(commands: List[Dict[str, Any]], path: Path = COMMANDS_FILE) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as f:
		json.dump(commands, f, ensure_ascii=False, indent=2)