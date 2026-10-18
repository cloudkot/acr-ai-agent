import sqlite3
import json
from schemas import Framework

DB_PATH = "sessions.db"

def init_db():
    """[ТРЕБОВАНИЕ КЕЙСА]: Персистентное хранилище сессий."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            framework_json TEXT,
            content_json TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_session(session_id: str, framework: Framework, status: str, content: dict = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    content_str = json.dumps(content, ensure_ascii=False) if content else None
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (id, framework_json, content_json, status)
        VALUES (?, ?, ?, ?)
    ''', (session_id, framework.model_dump_json(), content_str, status))
    conn.commit()
    conn.close()

def get_session(session_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT framework_json, content_json, status FROM sessions WHERE id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "framework": Framework.model_validate_json(row[0]),
            "content": json.loads(row[1]) if row[1] else None,
            "status": row[2]
        }
    return None