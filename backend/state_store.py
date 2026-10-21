import sqlite3
import json
from schemas import Framework
from logger import logger

DB_PATH = "sessions.db"

def init_db():
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Персистентное хранилище сессий, аудита и аналитики.
    Добавлены колонки для подсчета токенов и стоимости в рублях.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица сессий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, 
            framework_json TEXT, 
            content_json TEXT, 
            constraints TEXT, 
            status TEXT,
            tokens_used INTEGER DEFAULT 0,
            cost_rub REAL DEFAULT 0.0
        )
    ''')
    
    # Таблица аудита
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Миграция для существующих баз (добавляем колонки, если их нет)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN tokens_used INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE sessions ADD COLUMN cost_rub REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass # Колонки уже существуют
        
    conn.commit()
    conn.close()

def save_session(
    session_id: str, 
    framework: Framework, 
    status: str, 
    content: dict = None, 
    constraints: str = None,
    tokens_used: int = 0,
    cost_rub: float = 0.0
):
    """Сохраняет или обновляет сессию и метрики расхода токенов."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    content_str = json.dumps(content, ensure_ascii=False) if content else None
    
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (id, framework_json, content_json, constraints, status, tokens_used, cost_rub)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, framework.model_dump_json(), content_str, constraints, status, tokens_used, cost_rub))
    
    conn.commit()
    conn.close()

def get_session(session_id: str) -> dict:
    """Достает сессию из БД, включая аналитику."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT framework_json, content_json, constraints, status, tokens_used, cost_rub 
        FROM sessions WHERE id = ?
    ''', (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "framework": Framework.model_validate_json(row[0]),
            "content": json.loads(row[1]) if row[1] else None,
            "constraints": row[2],
            "status": row[3],
            "tokens_used": row[4],
            "cost_rub": row[5]
        }
    return None

def log_action(session_id: str, action: str):
    """Логирование действий методиста."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('INSERT INTO audit_logs (session_id, action) VALUES (?, ?)', (session_id, action))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка аудита: {e}")