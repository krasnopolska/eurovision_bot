"""
data.py — проста база даних на SQLite для Eurovision Bot
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "eurovision.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_name TEXT,
                username   TEXT,
                joined_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ratings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                country    TEXT,
                score      INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, country)
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                place      INTEGER,
                country    TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, place)
            );

            CREATE TABLE IF NOT EXISTS official_results (
                place   INTEGER PRIMARY KEY,
                country TEXT,
                set_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            );
        """)

init_db()

# ── Users ──────────────────────────────────────────────────────────────────────
def register_user(user_id: int, first_name: str, username: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
            (user_id, first_name, username)
        )

def get_all_users():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM users").fetchall()]

# ── Ratings ────────────────────────────────────────────────────────────────────
def save_rating(user_id: int, country: str, score: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ratings (user_id, country, score, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, country) DO UPDATE SET score=excluded.score, updated_at=excluded.updated_at""",
            (user_id, country, score)
        )

def get_user_ratings(user_id: int):
    with get_conn() as conn:
        return [dict(row) for row in
                conn.execute("SELECT * FROM ratings WHERE user_id=? ORDER BY score DESC", (user_id,)).fetchall()]

def get_user_rating_for_country(user_id: int, country: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT score FROM ratings WHERE user_id=? AND country=?", (user_id, country)
        ).fetchone()
        return row['score'] if row else None

def get_country_averages():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT country, ROUND(AVG(score), 2) as avg, COUNT(*) as votes
               FROM ratings GROUP BY country ORDER BY avg DESC"""
        ).fetchall()
        return [dict(row) for row in rows]

# ── Predictions ────────────────────────────────────────────────────────────────
def save_prediction(user_id: int, place: int, country: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO predictions (user_id, place, country, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, place) DO UPDATE SET country=excluded.country, updated_at=excluded.updated_at""",
            (user_id, place, country)
        )

def get_user_predictions(user_id: int):
    with get_conn() as conn:
        return [dict(row) for row in
                conn.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY place", (user_id,)).fetchall()]

# ── Official Results ───────────────────────────────────────────────────────────
def save_official_results(results: list[tuple[int, str]]):
    with get_conn() as conn:
        conn.execute("DELETE FROM official_results")
        conn.executemany(
            "INSERT INTO official_results (place, country) VALUES (?, ?)", results
        )

def get_official_results():
    with get_conn() as conn:
        return [dict(row) for row in
                conn.execute("SELECT * FROM official_results ORDER BY place").fetchall()]

# ── Score Calculation ──────────────────────────────────────────────────────────
def calculate_all_scores():
    """
    Рахуємо точність передбачень кожного користувача.

    Алгоритм:
    - За кожне передбачення перевіряємо відстань від реального місця.
    - Відстань 0 (влучно) = 100 балів
    - Відстань 1 = 80 балів, 2 = 60, 3 = 40, 4+ = 10
    - Фінальна точність = середнє по всіх передбаченнях / 100 * 100%
    """
    results = get_official_results()
    if not results:
        return []

    result_map = {r['country']: r['place'] for r in results}
    users = get_all_users()

    scores = []
    for user in users:
        predictions = get_user_predictions(user['user_id'])
        if not predictions:
            continue

        total = 0
        count = 0
        for pred in predictions:
            real_place = result_map.get(pred['country'])
            if real_place is None:
                continue
            distance = abs(pred['place'] - real_place)
            if distance == 0:
                pts = 100
            elif distance == 1:
                pts = 80
            elif distance == 2:
                pts = 60
            elif distance == 3:
                pts = 40
            else:
                pts = max(0, 10 - distance)
            total += pts
            count += 1

        if count > 0:
            accuracy = total / count
            scores.append({**user, 'score': accuracy, 'predictions_count': count})

    return sorted(scores, key=lambda x: x['score'], reverse=True)

def get_user_accuracy_score(user_id: int):
    results = get_official_results()
    if not results:
        return None
    all_scores = calculate_all_scores()
    user_score = next((s for s in all_scores if s['user_id'] == user_id), None)
    return user_score['score'] if user_score else None

# ── Admin ──────────────────────────────────────────────────────────────────────
def set_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))

def get_admin():
    with get_conn() as conn:
        return conn.execute("SELECT user_id FROM admins LIMIT 1").fetchone()

def is_admin(user_id: int):
    with get_conn() as conn:
        return bool(conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone())
