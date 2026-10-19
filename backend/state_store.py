import sqlite3
import json
from schemas import Framework

DB_PATH = "sessions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, framework_json TEXT, content_json TEXT, status TEXT
        )
    ''')
    # [ТРЕБОВАНИЕ КЕЙСА]: Таблица аудита (кто и когда делал запросы)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ... (функции save_session и get_session остаются прежними) ...

def log_action(session_id: str, action: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Логирование действий методиста."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO audit_logs (session_id, action) VALUES (?, ?)', (session_id, action))
    conn.commit()
    conn.close()import sqlite3
import json
from schemas import Framework

DB_PATH = "sessions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, framework_json TEXT, content_json TEXT, status TEXT
        )
    ''')
    # [ТРЕБОВАНИЕ КЕЙСА]: Таблица аудита (кто и когда делал запросы)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ... (функции save_session и get_session остаются прежними) ...

def log_action(session_id: str, action: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Логирование действий методиста."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO audit_logs (session_id, action) VALUES (?, ?)', (session_id, action))
    conn.commit()
    conn.close()