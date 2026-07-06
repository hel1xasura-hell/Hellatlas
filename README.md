# Atlas Telegram Bot

A group game bot for **Atlas** — the classic geography word chain. Players take
turns naming a country/city (or any word, in word mode) that starts with the
last letter of the previous answer. Miss the timer or give an invalid answer
and you're out — last player standing wins.

## 1. Create your bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram.
2. Send `/newbot`, follow the prompts, and copy the API token it gives you.
3. In BotFather, also run `/setprivacy` on your bot and choose **Disable**.
   This is required so the bot can read every message in the group (needed
   to check players' answers), not just commands.
4. Add the bot to your group and make it an admin (recommended, not strictly
   required unless you want it to delete/pin messages later).

## 2. Install & run

```bash
cd atlas_bot
pip install -r requirements.txt
export ATLAS_BOT_TOKEN="123456:ABC-your-bot-token"
python bot.py
```

The bot uses long polling, so it just needs to stay running somewhere (a
small VPS, a Raspberry Pi, Railway/Render/Fly.io, etc.) — no public URL or
webhook needed.

## 3. How to play (in a group)

| Command            | What it does                                   |
|---------------------|-------------------------------------------------|
| `/atlas`            | Shows a button menu to pick a mode              |
| `/startall`         | Start a game using countries **and** cities     |
| `/startcountries`   | Start a game using **countries only**           |
| `/startcities`      | Start a game using **cities only**              |
| `/startwords`       | Start a free word-chain game (any word)         |
| `/players`          | Show who's in the lobby / still alive           |
| `/score`            | Show this chat's all-time leaderboard           |
| `/endgame`          | Cancel the current lobby or running game        |
| `/rules`            | Explain the rules in-chat                       |

Flow:
1. Someone runs `/startall` (or one of the other mode commands).
2. The bot posts a lobby message with a **✅ Join** button and a
   **⚡ Force Start** button. The lobby auto-starts after 50 seconds.
3. Once 2+ players have joined, anyone can tap **Force Start** to skip the
   wait instead of sitting through the full countdown.
4. Turn order is shuffled. The first player can answer with anything valid
   for the mode. After that, every answer must:
   - start with the **last letter** of the previous answer,
   - be a real country/city from the bot's dataset (or any real word, in
     word mode),
   - not have been used already this game.
5. Each player gets 30 seconds per turn. Invalid answers can be retried
   until the timer runs out; running out of time eliminates you.
6. Last player standing wins, and it's recorded on `/score`.

## 4. Customizing

- **Timers** — edit `JOIN_COUNTDOWN_SECONDS`, `TURN_TIMEOUT_SECONDS`, and
  `MIN_PLAYERS` in `config.py`.
- **Word lists** — `data/countries.json` and `data/cities.json` are plain
  JSON arrays of strings. Add or remove entries freely; the included city
  list covers a broad but not exhaustive set of world cities, so expand it
  if your group wants deeper cutthroat play.
- **Multiple groups at once** — fully supported out of the box; each chat
  gets its own independent game session.

## 5. Known limitations

- No dictionary check in `/startwords` mode beyond "is this alphabetic and
  unused" — validity of the word itself is left to the honor system/group
  moderation.
- Tricky Atlas letters (X, Q, Z, ...) can occasionally leave a player stuck
  if the dataset doesn't have a matching city/country — expand
  `data/cities.json` for more coverage, or add a `/pass` command if your
  group wants to allow skipping without elimination.
