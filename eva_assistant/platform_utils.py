import sys
import platform
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)


def get_platform() -> str:
	plt = sys.platform
	if plt.startswith("win"):
		return "windows"
	elif plt == "darwin":
		return "mac"
	else:
		return "linux"


def is_64bit() -> bool:
	return platform.machine().endswith("64") or sys.maxsize > 2**32


def activate_application(app_name: str) -> bool:
	"""Attempt to focus/activate an application by name. Best-effort per OS.
	Returns True if a request was issued, not necessarily if the focus changed.
	"""
	os_name = get_platform()
	try:
		if os_name == "mac":
			# Use AppleScript to activate application
			subprocess.run([
				"osascript", "-e", f'tell application "{app_name}" to activate'
			], check=False)
			return True
		elif os_name == "windows":
			# Without pywin32, we cannot reliably focus by name.
			# Attempt via powershell to start the app if not running (best-effort)
			subprocess.run([
				"powershell", "-NoProfile", "-Command",
				f"$p=Get-Process -Name '{app_name}' -ErrorAction SilentlyContinue; if(-not $p){{ Start-Process '{app_name}' }}"
			], check=False)
			return True
		else:
			# On Linux it's highly DE-specific; try 'wmctrl' if present
			if shutil.which("wmctrl"):
				subprocess.run(["wmctrl", "-xa", app_name], check=False)
				return True
			return False
	except Exception as exc:
		logger.warning("activate_application failed: %s", exc)
		return False