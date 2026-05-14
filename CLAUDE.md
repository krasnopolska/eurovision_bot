# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```bash
pip install -r requirements.txt

# With env var (preferred):
export BOT_TOKEN="your_token_here"
python bot.py

# Or let it prompt for the token:
python bot.py
```

The bot token comes from [@BotFather](https://t.me/BotFather). After starting, the first user to send `/setadmin` becomes the admin.

## Architecture

Two files:

**`data.py`** — SQLite data layer (`eurovision.db`). All DB access goes through this module. Tables: `users`, `ratings`, `predictions`, `official_results`, `admins`. `init_db()` runs on import. The scoring algorithm in `calculate_all_scores()` compares each user's top-10 predictions against official results by positional distance (0 off = 100 pts, ±1 = 80, ±2 = 60, ±3 = 40, ±4+ = max(0, 10−distance)).

**`bot.py`** — All Telegram logic. Uses `python-telegram-bot` v21 with `Application`, inline keyboards, and `CallbackQueryHandler`. Navigation state between multi-step flows (e.g. which country was picked for rating) is stored in `context.user_data`. Callback data prefixes map to handlers: `menu_*` → `menu_handler`, `rate_*` → `rate_country_selected`, `score_*` → `score_selected`, `pred_*` → `prediction_place_selected`, `pcountry_*` → `prediction_country_selected`.

## Key data flows

- **Rating a country**: `menu_rate` → `show_countries_for_rating` → user clicks `rate_{idx}` → `rate_country_selected` (stores country in `user_data`) → user clicks `score_{n}` → `score_selected` → `db.save_rating()`
- **Making a prediction**: `menu_predict` → `show_prediction_menu` → user clicks `pred_{place}` → `prediction_place_selected` (stores place in `user_data`) → user clicks `pcountry_{idx}` → `prediction_country_selected` → `db.save_prediction()`
- **Entering official results** (admin only): `/setresults 1 Country 2 Country ...` — pairs of place+country name; country name is fuzzy-matched against `COUNTRIES` list

## Countries list

`COUNTRIES` in `bot.py` is the hardcoded list of 37 Eurovision 2025 finalists with flag emojis. Country names in the DB are stored with their flag emojis (e.g. `"🇨🇭 Швейцарія"`), so `/setresults` arguments must match (partial match against the emoji+name string).
