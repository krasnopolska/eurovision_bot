import json
import logging
import os
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import data as db
from data import TOP_N

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
RATING_COUNTRY = 1
RATING_SCORE = 2
PREDICT_PLACE = 3
PREDICT_COUNTRY = 4

# ── Фіналісти (завантажуються з finalists.json) ───────────────────────────────
FINALISTS_PATH = os.environ.get("FINALISTS_PATH", "finalists.json")


def _load_finalists(path: str) -> tuple[int, list[str]]:
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        sys.exit(f"finalists config not found at {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"finalists config at {path} is not valid JSON: {e}")

    year = cfg.get("year")
    countries = cfg.get("countries")
    if not isinstance(year, int):
        sys.exit(f"finalists config: 'year' must be an integer, got {year!r}")
    if not isinstance(countries, list) or not all(isinstance(c, str) and c for c in countries):
        sys.exit("finalists config: 'countries' must be a non-empty list of strings")
    if len(countries) != len(set(countries)):
        sys.exit("finalists config: 'countries' contains duplicates")
    return year, countries


YEAR, COUNTRIES = _load_finalists(FINALISTS_PATH)

MAIN_KEYBOARD = [
    [InlineKeyboardButton("⭐ Оцінити виступи фіналістів", callback_data="tab_rate")],
    [InlineKeyboardButton("🔮 Передбачити місця фіналістів", callback_data="tab_predict")],
]


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.first_name, user.username)

    await update.message.reply_text(
        f"🎶 *Євробачення {YEAR}!*\n\n"
        f"Привіт, {escape_markdown(user.first_name or '', version=1)}! 👋\n\n"
        f"Тут ти можеш:\n"
        f"• Ставити оцінки виступам (1–10 балів)\n"
        f"• Передбачати фінальні місця\n"
        f"• Змагатись з друзями — хто найточніше вгадає?\n\n"
        f"Після оголошення результатів напиши /winner 🏆",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(MAIN_KEYBOARD),
    )


# ── Головне меню через callback ────────────────────────────────────────────────
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "tab_rate":
        await show_rating_tab(query, context)
    elif data == "tab_predict":
        await show_predict_tab(query, context)
    elif data == "menu_rate":
        await show_countries_for_rating(query, context)
    elif data == "menu_predict":
        await show_prediction_menu(query, context)
    elif data == "menu_my_ratings":
        await show_my_ratings(query, context)
    elif data == "menu_my_predictions":
        await show_my_predictions(query, context)
    elif data == "menu_back":
        await back_to_menu(query, context)


# ── Вкладки ────────────────────────────────────────────────────────────────────
async def show_rating_tab(query, context):
    keyboard = [
        [InlineKeyboardButton("⭐ Оцінити виступ", callback_data="menu_rate")],
        [InlineKeyboardButton("📊 Мої оцінки", callback_data="menu_my_ratings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ]
    await query.edit_message_text(
        "⭐ *Оцінити виступи фіналістів*\n\nОбери дію:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_predict_tab(query, context):
    keyboard = [
        [InlineKeyboardButton("🔮 Зробити передбачення", callback_data="menu_predict")],
        [InlineKeyboardButton("📋 Мої передбачення", callback_data="menu_my_predictions")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ]
    await query.edit_message_text(
        "🔮 *Передбачити місця фіналістів*\n\nОбери дію:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Оцінка виступів ────────────────────────────────────────────────────────────
async def show_countries_for_rating(query, context):
    user_id = query.from_user.id
    rated = db.get_user_ratings(user_id)
    rated_names = {r["country"] for r in rated}

    keyboard = []
    row = []
    for i, country in enumerate(COUNTRIES):
        done = "✅ " if country in rated_names else ""
        btn = InlineKeyboardButton(f"{done}{country}", callback_data=f"rate_{i}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="tab_rate")])

    await query.edit_message_text(
        "⭐ *Оцінка виступів*\n\n"
        "Обери країну для оцінки (✅ = вже оцінено):\n"
        "Ти можеш змінити оцінку в будь-який час.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def rate_country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])
    country = COUNTRIES[idx]
    context.user_data["rating_country"] = country

    scores = list(range(1, 11))
    keyboard = []
    row = []
    for score in scores:
        row.append(InlineKeyboardButton(f"{score}", callback_data=f"score_{score}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_rate")])

    existing = db.get_user_rating_for_country(query.from_user.id, country)
    extra = f"\n_Поточна оцінка: {existing}/10_" if existing else ""

    await query.edit_message_text(
        f"⭐ Оцінка для *{country}*\n\n"
        f"Скільки балів ти даєш? (1–10){extra}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def score_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    score = int(query.data.split("_")[1])
    country = context.user_data.get("rating_country")
    user_id = query.from_user.id

    if country:
        db.save_rating(user_id, country, score)
        await query.edit_message_text(
            f"✅ Збережено! *{country}* — {score} балів\n\n"
            f"Продовжуй оцінювати або повертайся в меню.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⭐ Оцінити ще", callback_data="menu_rate")],
                    [InlineKeyboardButton("◀️ Головне меню", callback_data="menu_back")],
                ]
            ),
        )


# ── Передбачення місць ─────────────────────────────────────────────────────────
async def show_prediction_menu(query, context):
    user_id = query.from_user.id
    predictions = db.get_user_predictions(user_id)
    count = len(predictions)

    keyboard = []
    for place in range(1, 11):
        pred = next((p for p in predictions if p["place"] == place), None)
        if pred:
            label = f"#{place} → {pred['country']}"
        else:
            label = f"#{place} — не вказано"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"pred_{place}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="tab_predict")])

    await query.edit_message_text(
        "🔮 *Передбачення топ-10*\n\n"
        f"Вгадай фінальні місця! Заповнено: {count}/10\n\n"
        "Натисни на місце, щоб вибрати країну:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def prediction_place_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    place = int(query.data.split("_")[1])
    context.user_data["predict_place"] = place

    used = {p["country"]: p["place"] for p in db.get_user_predictions(query.from_user.id)}

    keyboard = []
    row = []
    for i, country in enumerate(COUNTRIES):
        if country in used and used[country] != place:
            label = f"✅ {country}"
        elif country in used and used[country] == place:
            label = f"⭐ {country}"
        else:
            label = country
        row.append(InlineKeyboardButton(label, callback_data=f"pcountry_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_predict")])

    await query.edit_message_text(
        f"🔮 Хто займе *#{place} місце*?\n\n"
        f"Обери країну (✅ — вже передбачена в іншому місці, ⭐ — поточний вибір):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def prediction_country_selected(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])
    country = COUNTRIES[idx]
    place = context.user_data.get("predict_place")
    user_id = query.from_user.id

    if place:
        moved_from = db.save_prediction(user_id, place, country)
        if moved_from is not None:
            header = (
                f"🔁 Переміщено! *{country}*: #{moved_from} → #{place}\n"
                f"_Кожна країна може зайняти лише одне місце у твоєму топ-10._"
            )
        else:
            header = f"✅ Збережено! Місце #{place} → *{country}*"
        await query.edit_message_text(
            f"{header}\n\nПродовжуй заповнювати передбачення!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔮 Продовжити передбачення", callback_data="menu_predict"
                        )
                    ],
                    [InlineKeyboardButton("◀️ Головне меню", callback_data="menu_back")],
                ]
            ),
        )


# ── Мої оцінки ─────────────────────────────────────────────────────────────────
async def show_my_ratings(query, context):
    user_id = query.from_user.id
    ratings = db.get_user_ratings(user_id)

    if not ratings:
        text = "📊 У тебе ще немає оцінок!\n\nПочни оцінювати виступи 👆"
    else:
        ratings_sorted = sorted(ratings, key=lambda x: x["score"], reverse=True)
        text = f"📊 *Твої оцінки* ({len(ratings)}/{len(COUNTRIES)}):\n\n"
        for r in ratings_sorted:
            stars = "⭐" * ((r["score"] + 1) // 2)
            text += f"{r['country']} — *{r['score']} балів* {stars}\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data="tab_rate")]]
        ),
    )


# ── Мої передбачення ───────────────────────────────────────────────────────────
async def show_my_predictions(query, context):
    user_id = query.from_user.id
    predictions = db.get_user_predictions(user_id)

    if not predictions:
        text = "📋 У тебе ще немає передбачень!\n\nДодай їх в розділі 🔮"
    else:
        predictions_sorted = sorted(predictions, key=lambda x: x["place"])
        text = "📋 *Твої передбачення топ-10:*\n\n"
        for p in predictions_sorted:
            text += f"#{p['place']} → {p['country']}\n"
        remaining = 10 - len(predictions)
        if remaining > 0:
            text += f"\n_Залишилось заповнити: {remaining} місць_"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data="tab_predict")]]
        ),
    )


# ── /хтопереміг ───────────────────────────────────────────────────────────────
async def who_won(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = db.get_official_results()
    if not results:
        await update.message.reply_text(
            "🎯 Результати ще не введені.\n\n"
            "Адмін може ввести їх командою `/setresults`.",
            parse_mode="Markdown",
        )
        return
    if len(results) < TOP_N:
        await update.message.reply_text(
            f"⏳ Результати ще не завершено: введено *{len(results)}/{TOP_N}* місць.\n\n"
            f"Рейтинг з'явиться, коли адмін заповнить усі {TOP_N}.",
            parse_mode="Markdown",
        )
        return

    text = f"🎯 *Офіційні результати Євробачення {YEAR}:*\n\n"
    for r in results:
        text += f"#{r['place']} {r['country']}\n"

    scores = db.calculate_all_scores()
    if scores:
        text += "\n🏆 *Рейтинг передбачень:*\n"
        for i, s in enumerate(scores, 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            name = escape_markdown(
                s.get("username") or s.get("first_name") or "Анонім", version=1
            )
            text += f"{medal} @{name} — {s['score']:.0f}%\n"
    else:
        text += "\n_Ніхто ще не зробив передбачень._"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── Введення результатів (тільки адмін) ───────────────────────────────────────
async def set_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text(
            "❌ Тільки адміністратор може вводити результати."
        )
        return

    existing = db.get_official_results()
    if existing:
        await update.message.reply_text(
            f"⚠️ Вже введено *{len(existing)}* результат(ів). "
            f"Замінити їх новими?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Так, замінити", callback_data="admin_overwrite_yes"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Скасувати", callback_data="admin_overwrite_no"
                        )
                    ],
                ]
            ),
        )
        return

    context.user_data["admin_pending"] = {}
    await _show_admin_wizard(update.message, context)


async def _show_admin_wizard(target, context):
    """Render the results wizard. `target` is either a Message (initial send) or a
    CallbackQuery (edit existing message)."""
    pending: dict[int, str] = context.user_data.get("admin_pending", {})

    keyboard = []
    for place in range(1, TOP_N + 1):
        country = pending.get(place)
        label = f"#{place} → {country}" if country else f"#{place} — не встановлено"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"admin_place_{place}")])

    filled = len(pending)
    if filled == TOP_N:
        save_btn = InlineKeyboardButton("💾 Зберегти результати", callback_data="admin_save")
    else:
        save_btn = InlineKeyboardButton(
            f"💾 Зберегти ({filled}/{TOP_N})", callback_data="admin_save_blocked"
        )
    keyboard.append(
        [save_btn, InlineKeyboardButton("❌ Скасувати", callback_data="admin_cancel")]
    )

    text = (
        "🎯 *Офіційні результати*\n\n"
        f"Заповнено: {filled}/{TOP_N}. Натисни на місце, щоб обрати країну."
    )
    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def _show_admin_country_picker(query, context, place: int):
    pending: dict[int, str] = context.user_data.get("admin_pending", {})
    used = {c: p for p, c in pending.items()}

    keyboard = []
    row = []
    for i, country in enumerate(COUNTRIES):
        if country in used and used[country] != place:
            label = f"✅ {country}"
        elif country in used and used[country] == place:
            label = f"⭐ {country}"
        else:
            label = country
        row.append(InlineKeyboardButton(label, callback_data=f"admin_country_{place}_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    bottom = []
    if place in pending:
        bottom.append(
            InlineKeyboardButton(f"🗑 Очистити #{place}", callback_data=f"admin_clear_{place}")
        )
    bottom.append(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    keyboard.append(bottom)

    await query.edit_message_text(
        f"🎯 Хто посів *#{place} місце*?\n\n"
        f"Обери країну (✅ — вже у списку, ⭐ — поточний вибір):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not db.is_admin(user_id):
        await query.answer("❌ Тільки адміністратор.", show_alert=True)
        return

    data = query.data

    if data == "admin_overwrite_yes":
        await query.answer()
        context.user_data["admin_pending"] = {}
        await _show_admin_wizard(query, context)
        return

    if data == "admin_overwrite_no":
        await query.answer()
        await query.edit_message_text("✅ Скасовано. Існуючі результати збережено.")
        return

    if data == "admin_cancel":
        await query.answer()
        context.user_data.pop("admin_pending", None)
        await query.edit_message_text("❌ Скасовано.")
        return

    if data == "admin_save_blocked":
        await query.answer(
            f"Заповни всі {TOP_N} місць перед збереженням.", show_alert=True
        )
        return

    if data == "admin_save":
        await query.answer()
        pending: dict[int, str] = context.user_data.get("admin_pending", {})
        if len(pending) != TOP_N:
            await query.answer(
                f"Потрібно заповнити всі {TOP_N} місць.", show_alert=True
            )
            return
        results = [(place, country) for place, country in sorted(pending.items())]
        db.save_official_results(results)
        context.user_data.pop("admin_pending", None)

        scores = db.calculate_all_scores()
        lines = [f"✅ Результати збережено! ({len(results)} місць)\n"]
        if scores:
            winner = scores[0]
            name = escape_markdown(
                winner.get("username") or winner.get("first_name") or "Анонім",
                version=1,
            )
            lines.append(f"🥇 @{name} з точністю {winner['score']:.0f}%!")
        await query.edit_message_text("\n".join(lines))
        return

    if data == "admin_back":
        await query.answer()
        await _show_admin_wizard(query, context)
        return

    if data.startswith("admin_place_"):
        await query.answer()
        place = int(data.split("_")[2])
        await _show_admin_country_picker(query, context, place)
        return

    if data.startswith("admin_clear_"):
        await query.answer()
        place = int(data.split("_")[2])
        pending = context.user_data.setdefault("admin_pending", {})
        pending.pop(place, None)
        await _show_admin_wizard(query, context)
        return

    if data.startswith("admin_country_"):
        await query.answer()
        parts = data.split("_")
        place = int(parts[2])
        idx = int(parts[3])
        country = COUNTRIES[idx]
        pending = context.user_data.setdefault("admin_pending", {})
        # Single-slot rule: if this country is already in another slot, move it.
        for p, c in list(pending.items()):
            if c == country and p != place:
                del pending[p]
        pending[place] = country
        await _show_admin_wizard(query, context)
        return


# ── Встановити адміна ──────────────────────────────────────────────────────────
async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.get_admin():
        await update.message.reply_text("Адмін вже встановлений!")
        return
    db.set_admin(user_id)
    await update.message.reply_text(
        f"✅ Ти тепер адмін!\nПісля фіналу введи результати: /setresults"
    )


# ── Статистика ─────────────────────────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    total_ratings = sum(len(db.get_user_ratings(u["user_id"])) for u in users)

    country_avgs = db.get_country_averages()

    text = f"📊 *Загальна статистика:*\n\n"
    text += f"👥 Учасників: {len(users)}\n"
    text += f"⭐ Оцінок виставлено: {total_ratings}\n\n"

    if country_avgs:
        text += "*Топ-5 за середньою оцінкою:*\n"
        for c in country_avgs[:5]:
            text += f"• {c['country']} — {c['avg']:.1f} балів\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── Назад в меню ──────────────────────────────────────────────────────────────
async def back_to_menu(query, context):
    await query.edit_message_text(
        f"🎶 *Євробачення {YEAR} — Головне меню*\n\nОбери розділ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(MAIN_KEYBOARD),
    )


# ── Запуск ─────────────────────────────────────────────────────────────────────
def _load_token() -> str:
    token = os.environ.get("BOT_TOKEN")
    if token:
        return token.strip()
    if sys.stdin.isatty():
        return input("Введи токен бота: ").strip()
    sys.exit("BOT_TOKEN is not set. Provide it via the BOT_TOKEN environment variable.")


def main():
    TOKEN = _load_token()

    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setresults", set_results))
    app.add_handler(CommandHandler("setadmin", set_admin))
    app.add_handler(CommandHandler("winner", who_won))

    # Tab and menu callbacks
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^(tab_|menu_)"))

    # Rating flow
    app.add_handler(CallbackQueryHandler(rate_country_selected, pattern="^rate_\\d+$"))
    app.add_handler(CallbackQueryHandler(score_selected, pattern="^score_\\d+$"))

    # Prediction flow
    app.add_handler(
        CallbackQueryHandler(prediction_place_selected, pattern="^pred_\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(prediction_country_selected, pattern="^pcountry_\\d+$")
    )

    # Admin wizard flow (/setresults)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    print("🎶 Eurovision Bot запущено! Натисни Ctrl+C для зупинки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
