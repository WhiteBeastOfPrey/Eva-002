from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

# Audio
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION_SECONDS = 0.5

# Recognition
WAKE_WORDS = ["ева"]
COMMAND_LISTEN_WINDOW_SECONDS = 6.0

# Matching
DEFAULT_FUZZY_THRESHOLD = 65

# Files
COMMANDS_FILE = DATA_DIR / "commands.json"

# GUI
APP_TITLE = "ЕВА — голосовой ассистент"

# Ensure dirs exist at import-time for convenience
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)