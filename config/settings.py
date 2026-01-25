from pathlib import Path

# Base directory của project
BASE_DIR = Path(__file__).parent.parent

# Database paths
DATABASE_DIR = BASE_DIR / "database"
CHAT_HISTORY_FILE = DATABASE_DIR / "recent_chat_history.json"
CHAT_SUMMARY_FILE = DATABASE_DIR / "chat_summary.json"
USER_FACTS_FILE = DATABASE_DIR / "user_facts.json"

# Slide storage paths
SLIDES_DIR = DATABASE_DIR / "slides"
SLIDE_INDEX_FILE = DATABASE_DIR / "slide_index.json"

