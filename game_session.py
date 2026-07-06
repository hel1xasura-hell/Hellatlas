import random
import time

from config import MIN_PLAYERS
from data_loader import geo, clean_name

LOBBY = "lobby"
RUNNING = "running"
ENDED = "ended"


class Player:
    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        self.alive = True


class GameSession:
    """
    One instance per group chat. Tracks the lobby, turn order, used words,
    and whose turn it is.
    """

    def __init__(self, chat_id, mode, started_by):
        self.chat_id = chat_id
        self.mode = mode
        self.started_by = started_by
        self.state = LOBBY
        self.players = {}          # user_id -> Player, insertion order preserved
        self.turn_order = []       # list of user_ids, rebuilt when game starts
        self.turn_index = 0
        self.used_names = set()    # cleaned names already used this game
        self.required_letter = None
        self.lobby_message_id = None
        self.created_at = time.time()

    # ---------- lobby ----------

    def add_player(self, user_id, name):
        if user_id in self.players:
            return False
        self.players[user_id] = Player(user_id, name)
        return True

    def player_count(self):
        return len(self.players)

    def can_force_start(self):
        return self.player_count() >= MIN_PLAYERS

    def join_list_text(self):
        if not self.players:
            return "No one has joined yet."
        return "\n".join(f"• {p.name}" for p in self.players.values())

    # ---------- game start ----------

    def start_game(self):
        self.turn_order = list(self.players.keys())
        random.shuffle(self.turn_order)
        self.turn_index = 0
        self.state = RUNNING

    def current_player(self):
        if not self.turn_order:
            return None
        return self.players[self.turn_order[self.turn_index]]

    def alive_players(self):
        return [self.players[uid] for uid in self.turn_order if self.players[uid].alive]

    def advance_turn(self):
        """Move to the next alive player."""
        n = len(self.turn_order)
        if n == 0:
            return
        for _ in range(n):
            self.turn_index = (self.turn_index + 1) % n
            if self.players[self.turn_order[self.turn_index]].alive:
                return

    def eliminate_current(self):
        p = self.current_player()
        if p:
            p.alive = False

    def is_over(self):
        return len(self.alive_players()) <= 1

    def winner(self):
        alive = self.alive_players()
        return alive[0] if len(alive) == 1 else None

    # ---------- turn validation ----------

    def validate_answer(self, raw_text):
        """
        Returns (ok: bool, message: str, cleaned: str or None)
        Does NOT mutate state - caller applies the result via apply_answer().
        """
        cleaned = clean_name(raw_text)
        if not cleaned:
            return False, "That doesn't look like a place name. Try again.", None

        if self.required_letter and not cleaned.startswith(self.required_letter):
            return False, (
                f"❌ Your answer must start with the letter "
                f"'{self.required_letter.upper()}'."
            ), None

        if cleaned in self.used_names:
            return False, "❌ That name has already been used this game.", None

        if not geo.valid_for_mode(self.mode, cleaned):
            mode_label = {
                "country": "a country",
                "city": "a city",
                "all": "a country or city",
                "word": "a word",
            }.get(self.mode, "valid")
            return False, f"❌ '{raw_text.strip()}' isn't recognized as {mode_label}. Try again.", None

        return True, "", cleaned

    def apply_answer(self, cleaned):
        """Commit a validated answer: mark used, set next required letter, advance turn."""
        self.used_names.add(cleaned)
        self.required_letter = cleaned[-1]
        self.advance_turn()

    def display_for(self, cleaned, raw_fallback):
        return geo.display_name(self.mode, cleaned, raw_fallback)
