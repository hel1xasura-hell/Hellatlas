import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage
from config import (
    BOT_TOKEN,
    JOIN_COUNTDOWN_SECONDS,
    MIN_PLAYERS,
    MODE_ALL,
    MODE_CITY,
    MODE_COUNTRY,
    MODE_LABELS,
    MODE_WORD,
    TURN_TIMEOUT_SECONDS,
)
from game_manager import create_session, get_session, remove_session
from game_session import LOBBY, RUNNING

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def _lobby_text(session):
    label = MODE_LABELS[session.mode]
    return (
        f"🎮 <b>Atlas — {label}</b>\n\n"
        f"Tap <b>Join</b> to play! Game auto-starts in "
        f"{JOIN_COUNTDOWN_SECONDS} seconds, or an admin/player can hit "
        f"<b>Force Start</b> once at least {MIN_PLAYERS} players have joined.\n\n"
        f"<b>Players ({session.player_count()}):</b>\n{session.join_list_text()}"
    )


def _lobby_keyboard(session):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Join", callback_data=f"join:{session.chat_id}")],
            [InlineKeyboardButton("⚡ Force Start", callback_data=f"forcestart:{session.chat_id}")],
        ]
    )


async def _refresh_lobby_message(session, context):
    try:
        await context.bot.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.lobby_message_id,
            text=_lobby_text(session),
            parse_mode=ParseMode.HTML,
            reply_markup=_lobby_keyboard(session),
        )
    except Exception as e:
        logger.warning("Could not refresh lobby message: %s", e)


async def _begin_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Atlas is a group game — add me to a Telegram group and run this command there!"
        )
        return

    existing = get_session(chat.id)
    if existing and existing.state in (LOBBY, RUNNING):
        await update.effective_message.reply_text(
            "A game is already in progress or forming in this chat. "
            "Use /endgame to cancel it first."
        )
        return

    session = create_session(chat.id, mode, update.effective_user.id)
    msg = await update.effective_message.reply_text(
        _lobby_text(session), parse_mode=ParseMode.HTML, reply_markup=_lobby_keyboard(session)
    )
    session.lobby_message_id = msg.message_id

    context.job_queue.run_once(
        _lobby_timeout_callback,
        JOIN_COUNTDOWN_SECONDS,
        chat_id=chat.id,
        name=f"lobby_{chat.id}",
    )


# ---------------------------------------------------------------------------
# mode start commands
# ---------------------------------------------------------------------------

async def cmd_startall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _begin_lobby(update, context, MODE_ALL)


async def cmd_startcountries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _begin_lobby(update, context, MODE_COUNTRY)


async def cmd_startcities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _begin_lobby(update, context, MODE_CITY)


async def cmd_startwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _begin_lobby(update, context, MODE_WORD)


async def cmd_atlas_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/atlas shows a button menu instead of remembering each command."""
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Atlas is a group game — add me to a Telegram group and run /atlas there!"
        )
        return
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(MODE_LABELS[MODE_ALL], callback_data="mode:all")],
            [InlineKeyboardButton(MODE_LABELS[MODE_COUNTRY], callback_data="mode:country")],
            [InlineKeyboardButton(MODE_LABELS[MODE_CITY], callback_data="mode:city")],
            [InlineKeyboardButton(MODE_LABELS[MODE_WORD], callback_data="mode:word")],
        ]
    )
    await update.effective_message.reply_text(
        "Choose a game mode:", reply_markup=keyboard
    )


async def on_mode_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":", 1)[1]
    await _begin_lobby(update, context, mode)


# ---------------------------------------------------------------------------
# lobby: join / force start / timeout
# ---------------------------------------------------------------------------

async def on_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":", 1)[1])
    session = get_session(chat_id)

    if not session or session.state != LOBBY:
        await query.answer("This lobby isn't open anymore.", show_alert=True)
        return

    user = query.from_user
    added = session.add_player(user.id, user.full_name)
    if not added:
        await query.answer("You've already joined!")
        return

    await query.answer("You're in! ✅")
    await _refresh_lobby_message(session, context)


async def on_force_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":", 1)[1])
    session = get_session(chat_id)

    if not session or session.state != LOBBY:
        await query.answer("This lobby isn't open anymore.", show_alert=True)
        return

    if not session.can_force_start():
        await query.answer(
            f"Need at least {MIN_PLAYERS} players before you can force start.",
            show_alert=True,
        )
        return

    await query.answer("Starting now! 🚀")
    for job in context.job_queue.get_jobs_by_name(f"lobby_{chat_id}"):
        job.schedule_removal()
    await _launch_game(session, context)


async def _lobby_timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    session = get_session(chat_id)
    if not session or session.state != LOBBY:
        return
    await _launch_game(session, context)


async def _launch_game(session, context: ContextTypes.DEFAULT_TYPE):
    if session.player_count() < MIN_PLAYERS:
        await context.bot.send_message(
            session.chat_id,
            f"Not enough players joined (need at least {MIN_PLAYERS}). Game cancelled.",
        )
        remove_session(session.chat_id)
        return

    session.start_game()
    order_text = "\n".join(
        f"{i+1}. {session.players[uid].name}" for i, uid in enumerate(session.turn_order)
    )
    await context.bot.send_message(
        session.chat_id,
        f"🎲 <b>Game on!</b> Turn order:\n{order_text}\n\n"
        "The first player may start with <b>any</b> valid answer for this mode. "
        "After that, each answer must start with the last letter of the previous one!",
        parse_mode=ParseMode.HTML,
    )
    await _announce_turn(session, context)


async def _announce_turn(session, context: ContextTypes.DEFAULT_TYPE):
    player = session.current_player()
    letter_note = (
        f" (must start with '{session.required_letter.upper()}')"
        if session.required_letter
        else " (any valid word to start!)"
    )
    await context.bot.send_message(
        session.chat_id,
        f"👉 {_mention(player.user_id, player.name)}'s turn{letter_note}. "
        f"You have {TURN_TIMEOUT_SECONDS} seconds.",
        parse_mode=ParseMode.HTML,
    )
    for job in context.job_queue.get_jobs_by_name(f"turn_{session.chat_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        _turn_timeout_callback,
        TURN_TIMEOUT_SECONDS,
        chat_id=session.chat_id,
        data={"user_id": player.user_id},
        name=f"turn_{session.chat_id}",
    )


async def _turn_timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    session = get_session(chat_id)
    if not session or session.state != RUNNING:
        return
    player = session.current_player()
    if not player or player.user_id != context.job.data["user_id"]:
        return  # they already answered and turn moved on

    await context.bot.send_message(
        chat_id,
        f"⏰ Time's up, {_mention(player.user_id, player.name)}! You're eliminated.",
        parse_mode=ParseMode.HTML,
    )
    session.eliminate_current()
    await _check_game_over_or_continue(session, context)


async def _check_game_over_or_continue(session, context: ContextTypes.DEFAULT_TYPE):
    if session.is_over():
        winner = session.winner()
        for job in context.job_queue.get_jobs_by_name(f"turn_{session.chat_id}"):
            job.schedule_removal()
        if winner:
            storage.add_win(session.chat_id, winner.user_id, winner.name)
            await context.bot.send_message(
                session.chat_id,
                f"🏆 <b>{_mention(winner.user_id, winner.name)} wins the game!</b> Congratulations!",
                parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.send_message(session.chat_id, "Game over — no winner.")
        remove_session(session.chat_id)
        return
    session.advance_turn()
    await _announce_turn(session, context)


# ---------------------------------------------------------------------------
# turn-by-turn message handling
# ---------------------------------------------------------------------------

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        return
    session = get_session(chat.id)
    if not session or session.state != RUNNING:
        return

    current = session.current_player()
    user = update.effective_user
    if not current or user.id != current.user_id:
        return  # not their turn; leave normal chat alone

    text = update.effective_message.text or ""
    ok, err, cleaned = session.validate_answer(text)
    if not ok:
        await update.effective_message.reply_text(err)
        return

    display = session.display_for(cleaned, text)
    session.apply_answer(cleaned)
    await update.effective_message.reply_text(f"✅ {display} accepted!")
    await _check_game_over_or_continue(session, context)


# ---------------------------------------------------------------------------
# misc commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "👋 I run the Atlas geography word-chain game! Add me to a group and try:\n"
        "/startall, /startcountries, /startcities, /startwords, or /atlas for a menu.\n"
        "Use /rules for how the game works."
    )


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📜 <b>Atlas rules</b>\n\n"
        "1. Pick a mode: /startall (countries+cities), /startcountries, /startcities, "
        "or /startwords (any word).\n"
        "2. Everyone taps Join during the lobby countdown, or an admin/player hits Force Start.\n"
        "3. Turn order is randomized. The first player says any valid word for the mode.\n"
        "4. Each next player must say a NEW word that starts with the LAST letter of the "
        "previous word (e.g. India → Angola → Australia...).\n"
        f"5. You have {TURN_TIMEOUT_SECONDS}s per turn — miss it or answer invalidly and "
        "you're eliminated (invalid answers can be retried until time runs out).\n"
        "6. Last player standing wins!\n\n"
        "Other commands: /players, /score, /endgame",
        parse_mode=ParseMode.HTML,
    )


async def cmd_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.effective_chat.id)
    if not session:
        await update.effective_message.reply_text("No game running right now.")
        return
    if session.state == LOBBY:
        await update.effective_message.reply_text(
            f"Lobby open — players so far:\n{session.join_list_text()}"
        )
    else:
        alive = session.alive_players()
        names = "\n".join(f"• {p.name}" for p in alive)
        await update.effective_message.reply_text(f"Still in the game:\n{names}")


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = storage.get_leaderboard(update.effective_chat.id)
    if not board:
        await update.effective_message.reply_text("No games have been won yet in this chat.")
        return
    lines = [f"{i+1}. {e['name']} — {e['wins']} win(s)" for i, e in enumerate(board)]
    await update.effective_message.reply_text("🏅 <b>Leaderboard</b>\n" + "\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = get_session(chat_id)
    if not session:
        await update.effective_message.reply_text("No game to end.")
        return
    for job in context.job_queue.get_jobs_by_name(f"lobby_{chat_id}"):
        job.schedule_removal()
    for job in context.job_queue.get_jobs_by_name(f"turn_{chat_id}"):
        job.schedule_removal()
    remove_session(chat_id)
    await update.effective_message.reply_text("Game ended.")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Set the ATLAS_BOT_TOKEN environment variable to your BotFather token before running."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("atlas", cmd_atlas_menu))
    app.add_handler(CommandHandler("startall", cmd_startall))
    app.add_handler(CommandHandler("startcountries", cmd_startcountries))
    app.add_handler(CommandHandler("startcities", cmd_startcities))
    app.add_handler(CommandHandler("startwords", cmd_startwords))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("players", cmd_players))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("endgame", cmd_endgame))

    app.add_handler(CallbackQueryHandler(on_mode_chosen, pattern=r"^mode:"))
    app.add_handler(CallbackQueryHandler(on_join, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(on_force_start, pattern=r"^forcestart:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))

    logger.info("Atlas bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
