import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "posts.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection



def init_db():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE NOT NULL,
                channel TEXT NOT NULL,
                original_text TEXT NOT NULL,
                source_url TEXT NOT NULL,
                rewritten_text TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            )
        """)



def save_post(post):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO posts
            (source_id, channel, original_text, source_url)
            VALUES (?, ?, ?, ?)
        """, (
            post["id"],
            post["channel"],
            post["text"],
            post["url"]
        ))

        return cursor.rowcount == 1


def get_new_posts(limit=3):
    with get_connection() as connection:
        return connection.execute("""
            SELECT *
            FROM posts
            WHERE status = 'new'
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    

def update_post_status(source_id, status):
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE posts SET status = ? WHERE source_id = ?",
            (status, source_id),
        )
        return cursor.rowcount == 1

def create_drafts_table():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_draft(text, source_url):
    create_drafts_table()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO drafts (text, source_url)
            VALUES (?, ?)
            """,
            (text, source_url)
        )
        return cursor.lastrowid


def get_draft(draft_id):
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM drafts WHERE id = ?",
            (draft_id,)
        ).fetchone()



def update_draft_status(draft_id, status):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE drafts
            SET status = ?
            WHERE id = ?
            """,
            (status, draft_id)
        )
        return cursor.rowcount == 1

from datetime import datetime, timezone


def get_last_published_at():
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT setting_value
            FROM scheduler_settings
            WHERE setting_key = 'last_published_at'
            """
        ).fetchone()

        return row["setting_value"] if row else None


def save_last_published_at():
    published_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO scheduler_settings (setting_key, setting_value)
            VALUES ('last_published_at', ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            (published_at,)
        )
