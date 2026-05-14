import json
import logging
import os
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
RATING_COUNTRY = 1
RATING_SCORE = 2
PREDICT_PLACE = 3
PREDICT_COUNTRY = 4

# ── Євробачення 2025 — фіналісти ──────────────────────────────────────────────
COUNTRIES = [
    "🇦🇱 Албанія",
    "🇦🇲 Вірменія",
    "🇦🇹 Австрія",
    "🇦🇿 Азербайджан",
    "🇧🇪 Бельгія",
    "🇭🇷 Хорватія",
    "🇨🇾 Кіпр",
    "🇨🇿 Чехія",
    "🇩🇰 Данія",
    "🇪🇪 Естонія",
    "🇫🇮 Фінляндія",
    "🇫🇷 Франція",
    "🇬🇪 Грузія",
    "🇩🇪 Німеччина",
    "🇬🇷 Греція",
    "🇮🇸 Ісландія",
    "🇮🇪 Ірландія",
    "🇮🇱 Ізраїль",
    "🇮🇹 Італія",
    "🇱🇻 Латвія",
    "🇱🇹 Литва",
    "🇲🇹 Мальта",
    "🇲🇩 Молдова",
    "🇳🇱 Нідерланди",
    "🇳🇴 Норвегія",
    "🇵🇱 Польща",
    "🇵🇹 Португалія",
    "🇸🇲 Сан-Марино",
    "🇷🇸 Сербія",
    "🇸🇮 Словенія",
    "🇪🇸 Іспанія",
    "🇸🇪 Швеція",
    "🇨🇭 Швейцарія",
    "🇬🇧 Велика Британія",
    "🇺🇦 Україна",
    "🇦🇺 Австралія",
    "🇱🇺 Люксембург",
]


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.first_name, user.username)

    keyboard = [
        [InlineKeyboardButton("⭐ Оцінити виступ", callback_data="menu_rate")],
        [InlineKeyboardButton("🔮 Передбачення місць", callback_data="menu_predict")],
        [InlineKeyboardButton("🏆 Таблиця лідерів", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("📊 Мої оцінки", callback_data="menu_my_ratings")],
        [
            InlineKeyboardButton(
                "📋 Мої передбачення", callback_data="menu_my_predictions"
            )
        ],
        [
            InlineKeyboardButton(
                "🎯 Результати (після фіналу)", callback_data="menu_results"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎶 *Євробачення 2026!*\n\n"
        f"Привіт, {user.first_name}! 👋\n\n"
        f"Тут ти можеш:\n"
        f"• Ставити оцінки виступам (1–10 балів)\n"
        f"• Передбачати фінальні місця\n"
        f"• Змагатись з друзями — хто найточніше вгадає?\n\n"
        f"Після оголошення результатів бот автоматично підрахує переможця 🏆",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


# ── Головне меню через callback ────────────────────────────────────────────────
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_rate":
        await show_countries_for_rating(query, context)
    elif data == "menu_predict":
        await show_prediction_menu(query, context)
    elif data == "menu_leaderboard":
        await show_leaderboard(query, context)
    elif data == "menu_my_ratings":
        await show_my_ratings(query, context)
    elif data == "menu_my_predictions":
        await show_my_predictions(query, context)
    elif data == "menu_results":
        await show_results(query, context)
    elif data == "menu_back":
        await back_to_menu(query, context)


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
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_back")])

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

    # Check existing rating
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
    for place in range(1, 11):  # Передбачаємо топ-10
        pred = next((p for p in predictions if p["place"] == place), None)
        if pred:
            label = f"#{place} → {pred['country']}"
        else:
            label = f"#{place} — не вказано"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"pred_{place}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_back")])

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

    keyboard = []
    row = []
    for i, country in enumerate(COUNTRIES):
        btn = InlineKeyboardButton(country, callback_data=f"pcountry_{i}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_predict")])

    await query.edit_message_text(
        f"🔮 Хто займе *#{place} місце*?\n\nОбери країну:",
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
        db.save_prediction(user_id, place, country)
        await query.edit_message_text(
            f"✅ Збережено! Місце #{place} → *{country}*\n\n"
            f"Продовжуй заповнювати передбачення!",
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
            [[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]
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
            [[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]
        ),
    )


# ── Таблиця лідерів ────────────────────────────────────────────────────────────
async def show_leaderboard(query, context):
    users = db.get_all_users()
    lines = ["🏆 *Таблиця лідерів*\n"]

    if not users:
        lines.append("Ще ніхто не зареєстрований!")
    else:
        for i, u in enumerate(users, 1):
            ratings_count = len(db.get_user_ratings(u["user_id"]))
            preds_count = len(db.get_user_predictions(u["user_id"]))
            name = u.get("username") or u.get("first_name", "Анонім")
            score = db.get_user_accuracy_score(u["user_id"])

            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            if score is not None:
                lines.append(f"{medal} @{name} — точність: *{score:.0f}%*")
            else:
                lines.append(
                    f"{medal} @{name} — оцінок: {ratings_count} | передбачень: {preds_count}/10"
                )

    lines.append("\n_Точність підрахується після введення офіційних результатів_ ⏳")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Оновити", callback_data="menu_leaderboard")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
            ]
        ),
    )


# ── Результати (для адміна) ────────────────────────────────────────────────────
async def show_results(query, context):
    results = db.get_official_results()
    if not results:
        await query.edit_message_text(
            "🎯 *Офіційні результати*\n\n"
            "Результати ще не введені.\n\n"
            "Адмін може ввести їх командою:\n"
            "`/setresults`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]
            ),
        )
        return

    text = "🎯 *Офіційні результати Євробачення 2025:*\n\n"
    for r in results:
        text += f"#{r['place']} {r['country']}\n"

    scores = db.calculate_all_scores()
    if scores:
        text += "\n🏆 *Рейтинг передбачень:*\n"
        for i, s in enumerate(scores[:5], 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            name = s.get("username") or s.get("first_name", "Анонім")
            text += f"{medal} @{name} — {s['score']:.0f}%\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]
        ),
    )


# ── Введення результатів (тільки адмін) ───────────────────────────────────────
async def set_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text(
            "❌ Тільки адміністратор може вводити результати."
        )
        return

    args = context.args
    if len(args) < 2 or len(args) % 2 != 0:
        await update.message.reply_text(
            "Формат: `/setresults 1 Швейцарія 2 Франція 3 Ізраїль ...`\n(місце країна)",
            parse_mode="Markdown",
        )
        return

    results = []
    for i in range(0, len(args), 2):
        place = int(args[i])
        country_query = args[i + 1]
        # Find matching country
        matched = next(
            (c for c in COUNTRIES if country_query.lower() in c.lower()), country_query
        )
        results.append((place, matched))

    db.save_official_results(results)

    # Recalculate scores
    scores = db.calculate_all_scores()
    msg = f"✅ Результати збережено! ({len(results)} місць)\n\n"
    if scores:
        msg += "🏆 Переможець передбачень:\n"
        winner = scores[0]
        name = winner.get("username") or winner.get("first_name", "Анонім")
        msg += f"🥇 @{name} з точністю {winner['score']:.0f}%!"

    await update.message.reply_text(msg)


# ── Встановити адміна ──────────────────────────────────────────────────────────
async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перший хто запустить /setadmin стає адміном"""
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

    # Average scores per country
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
    keyboard = [
        [InlineKeyboardButton("⭐ Оцінити виступ", callback_data="menu_rate")],
        [InlineKeyboardButton("🔮 Передбачення місць", callback_data="menu_predict")],
        [InlineKeyboardButton("🏆 Таблиця лідерів", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("📊 Мої оцінки", callback_data="menu_my_ratings")],
        [
            InlineKeyboardButton(
                "📋 Мої передбачення", callback_data="menu_my_predictions"
            )
        ],
        [
            InlineKeyboardButton(
                "🎯 Результати (після фіналу)", callback_data="menu_results"
            )
        ],
    ]
    await query.edit_message_text(
        "🎶 *Євробачення 2025 — Головне меню*\n\nОбери дію:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Запуск ─────────────────────────────────────────────────────────────────────
def _load_token() -> str:
    token = os.environ.get("BOT_TOKEN")
    if token:
        return token.strip()
    if sys.stdin.isatty():
        return input("Введи токен бота: ").strip()
    sys.exit("BOT_TOKEN is not set. Provide it via the BOT_TOKEN environment variable (e.g. in .env).")


def main():
    TOKEN = _load_token()

    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setresults", set_results))
    app.add_handler(CommandHandler("setadmin", set_admin))

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))

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

    print("🎶 Eurovision Bot запущено! Натисни Ctrl+C для зупинки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
