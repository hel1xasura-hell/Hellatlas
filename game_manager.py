from game_session import GameSession

# chat_id -> GameSession
_sessions = {}


def get_session(chat_id):
    return _sessions.get(chat_id)


def create_session(chat_id, mode, started_by):
    session = GameSession(chat_id, mode, started_by)
    _sessions[chat_id] = session
    return session


def remove_session(chat_id):
    _sessions.pop(chat_id, None)
