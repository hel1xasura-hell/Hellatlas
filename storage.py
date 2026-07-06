import json
import os
import threading

from config import SCORES_FILE

_lock = threading.Lock()


def _load_all():
    if not os.path.exists(SCORES_FILE):
        return {}
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data):
    os.makedirs(os.path.dirname(SCORES_FILE), exist_ok=True)
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_win(chat_id, user_id, name):
    with _lock:
        data = _load_all()
        chat_key = str(chat_id)
        chat_scores = data.setdefault(chat_key, {})
        user_key = str(user_id)
        entry = chat_scores.setdefault(user_key, {"name": name, "wins": 0})
        entry["name"] = name  # keep name fresh in case of a display-name change
        entry["wins"] += 1
        _save_all(data)


def get_leaderboard(chat_id, top_n=10):
    with _lock:
        data = _load_all()
        chat_scores = data.get(str(chat_id), {})
        ranked = sorted(chat_scores.values(), key=lambda e: e["wins"], reverse=True)
        return ranked[:top_n]
