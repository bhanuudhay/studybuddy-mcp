import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "studybuddy.db"
SEED_PATH = DATA_DIR / "seed.json"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY,
            title TEXT,
            module TEXT,
            minutes INTEGER,
            completed INTEGER,
            summary TEXT
        );
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            difficulty TEXT,
            q TEXT,
            a TEXT
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            score INTEGER,
            total INTEGER,
            taken_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    if count == 0:
        with open(SEED_PATH) as f:
            seed = json.load(f)
        for lesson in seed["lessons"]:
            conn.execute(
                "INSERT INTO lessons VALUES (?, ?, ?, ?, ?, ?)",
                (lesson["id"], lesson["title"], lesson["module"],
                 lesson["minutes"], int(lesson["completed"]), lesson["summary"]),
            )
        for card in seed["flashcards"]:
            conn.execute(
                "INSERT INTO flashcards (lesson_id, difficulty, q, a) VALUES (?, ?, ?, ?)",
                (card["lesson_id"], card["difficulty"], card["q"], card["a"]),
            )

    conn.commit()
    conn.close()


def get_lesson(lesson_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_lessons():
    conn = get_conn()
    rows = conn.execute("SELECT id, title, module, completed FROM lessons ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_note(lesson_id, text):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO notes (lesson_id, text) VALUES (?, ?)", (lesson_id, text)
    )
    conn.commit()
    note_id = cur.lastrowid
    conn.close()
    return {"id": note_id, "lesson_id": lesson_id, "text": text}


def get_notes(lesson_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, text, created_at FROM notes WHERE lesson_id = ? ORDER BY id",
        (lesson_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_flashcards(lesson_id, difficulty, limit):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM flashcards WHERE lesson_id = ? AND difficulty = ? ORDER BY RANDOM() LIMIT ?",
        (lesson_id, difficulty, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_flashcard(card_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_flashcard(lesson_id, q, a, difficulty):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO flashcards (lesson_id, difficulty, q, a) VALUES (?, ?, ?, ?)",
        (lesson_id, difficulty, q, a),
    )
    conn.commit()
    card_id = cur.lastrowid
    conn.close()
    return {"id": card_id, "lesson_id": lesson_id, "difficulty": difficulty, "q": q, "a": a}


def search_notes(query, lesson_id=None, limit=5):
    sql = "SELECT id, lesson_id, text, created_at FROM notes WHERE text LIKE ?"
    params = [f"%{query}%"]
    if lesson_id is not None:
        sql += " AND lesson_id = ?"
        params.append(lesson_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_progress(lesson_id, score, total):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO progress (lesson_id, score, total) VALUES (?, ?, ?)",
        (lesson_id, score, total),
    )
    conn.commit()
    progress_id = cur.lastrowid
    conn.close()
    return {"id": progress_id, "lesson_id": lesson_id, "score": score, "total": total}
