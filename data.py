"""
data.py — проста база даних на SQLite для Eurovision Bot
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "eurovision.db")

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
                place      INTEGER CHECK(place BETWEEN 1 AND 10),
                country    TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, place),
                UNIQUE(user_id, country)
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
        _migrate_predictions(conn)


def _migrate_predictions(conn):
    """Upgrade legacy `predictions` tables (no UNIQUE(user_id, country), no place CHECK).

    Idempotent: if the table already has UNIQUE(user_id, country), this is a no-op.
    Deduplicates rows that violate the new constraint by keeping the highest `id`
    (most recently inserted) per (user_id, country), and drops any rows with
    place outside 1..10.
    """
    indexes = conn.execute("PRAGMA index_list('predictions')").fetchall()
    for idx in indexes:
        if not idx['unique']:
            continue
        cols = {row['name'] for row in conn.execute(f"PRAGMA index_info('{idx['name']}')")}
        if cols == {'user_id', 'country'}:
            return  # already migrated

    conn.executescript("""
        ALTER TABLE predictions RENAME TO predictions_old;

        CREATE TABLE predictions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            place      INTEGER CHECK(place BETWEEN 1 AND 10),
            country    TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, place),
            UNIQUE(user_id, country)
        );

        INSERT INTO predictions (id, user_id, place, country, updated_at)
        SELECT id, user_id, place, country, updated_at
        FROM predictions_old
        WHERE place BETWEEN 1 AND 10
          AND id IN (
              SELECT MAX(id) FROM predictions_old
              WHERE place BETWEEN 1 AND 10
              GROUP BY user_id, country
          );

        DROP TABLE predictions_old;
    """)


init_db()

# ── Users ──────────────────────────────────────────────────────────────────────
def register_user(user_id: int, first_name: str, username: str | None):
    """Insert or refresh a user. On every call, the latest first_name and
    username from Telegram overwrite whatever was stored before, so leaderboards
    show current handles after a rename."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (user_id, first_name, username)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   first_name=excluded.first_name,
                   username=excluded.username""",
            (user_id, first_name, username),
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


def delete_rating(user_id: int, country: str) -> bool:
    """Delete a single rating. Returns True if a row was removed, False if none existed."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM ratings WHERE user_id=? AND country=?", (user_id, country)
        )
        return cur.rowcount > 0

def get_country_averages():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT country, ROUND(AVG(score), 2) as avg, COUNT(*) as votes
               FROM ratings GROUP BY country ORDER BY avg DESC"""
        ).fetchall()
        return [dict(row) for row in rows]

# ── Predictions ────────────────────────────────────────────────────────────────
def save_prediction(user_id: int, place: int, country: str) -> int | None:
    """Save a prediction. If the same country was previously placed in a different
    slot for this user, it's moved here (the old row is removed atomically).

    Returns the previous place the country occupied if a move happened, else None.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT place FROM predictions WHERE user_id=? AND country=?",
            (user_id, country),
        ).fetchone()
        moved_from = row['place'] if row and row['place'] != place else None

        if moved_from is not None:
            conn.execute(
                "DELETE FROM predictions WHERE user_id=? AND country=?",
                (user_id, country),
            )

        conn.execute(
            """INSERT INTO predictions (user_id, place, country, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, place) DO UPDATE SET country=excluded.country, updated_at=excluded.updated_at""",
            (user_id, place, country),
        )
        return moved_from

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
def _points_for_distance(distance: int) -> int:
    if distance == 0:
        return 100
    if distance == 1:
        return 80
    if distance == 2:
        return 60
    if distance == 3:
        return 40
    return max(0, 10 - distance)


TOP_N = 10


def calculate_all_scores():
    """
    Рахуємо точність передбачень кожного користувача.

    Алгоритм:
    - За кожне передбачення перевіряємо відстань від реального місця.
    - Відстань 0 = 100 балів, 1 = 80, 2 = 60, 3 = 40, 4+ = max(0, 10 - distance).
    - Якщо передбачена країна не потрапила в офіційний топ-10 — 0 балів.
    - Незаповнені слоти теж = 0 балів. Середнє завжди ділиться на TOP_N (10),
      щоб користувач, який зробив лише 1 «впевнене» передбачення, не міг
      обійти того, хто чесно заповнив усі 10.
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
        for pred in predictions:
            real_place = result_map.get(pred['country'])
            if real_place is None:
                pts = 0
            else:
                pts = _points_for_distance(abs(pred['place'] - real_place))
            total += pts

        accuracy = total / TOP_N
        scores.append({**user, 'score': accuracy, 'predictions_count': len(predictions)})

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
