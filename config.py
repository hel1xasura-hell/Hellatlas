import os

# Telegram bot token - set this as an environment variable, never hardcode it.
BOT_TOKEN = os.environ.get("ATLAS_BOT_TOKEN", "")

# How long (seconds) the join lobby stays open before auto-starting.
JOIN_COUNTDOWN_SECONDS = 50

# How long (seconds) a player has to answer on their turn before being eliminated.
TURN_TIMEOUT_SECONDS = 30

# Minimum players required to start a game.
MIN_PLAYERS = 2

# Where per-chat scoreboards are persisted (simple JSON file, no DB needed).
SCORES_FILE = os.path.join(os.path.dirname(__file__), "data", "scores.json")

# Game modes
MODE_ALL = "all"          # countries + cities
MODE_COUNTRY = "country"  # countries only
MODE_CITY = "city"        # cities only
MODE_WORD = "word"        # any word, no geography dictionary check

MODE_LABELS = {
    MODE_ALL: "🌍 All (Countries + Cities)",
    MODE_COUNTRY: "🏳️ Countries Only",
    MODE_CITY: "🏙️ Cities Only",
    MODE_WORD: "🔤 Any Word (word-chain)",
}
