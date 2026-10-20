import sqlite3
import json
from schemas import Framework
from logger import logger

DB_PATH = "sessions.db"

def init_db():
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Персистентное хранилище сессий и аудит.
    Добавлена колонка constraints для сохранения ограничений методиста между шагами.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица сессий (добавлено поле constraints)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, 
            framework_json TEXT, 
            content_json TEXT, 
            constraints TEXT, 
            status TEXT
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
    
    # Простейшая миграция на случай, если БД уже существует со старой схемой
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN constraints TEXT")
    except sqlite3.OperationalError:
        pass # Колонка уже существует, всё ок
        
    conn.commit()
    conn.close()

def save_session(
    session_id: str, 
    framework: Framework, 
    status: str, 
    content: dict = None, 
    constraints: str = None
):
    """Сохраняет или обновляет сессию в БД."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    content_str = json.dumps(content, ensure_ascii=False) if content else None
    
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (id, framework_json, content_json, constraints, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, framework.model_dump_json(), content_str, constraints, status))
    
    conn.commit()
    conn.close()

def get_session(session_id: str) -> dict:
    """Достает сессию из БД по ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT framework_json, content_json, constraints, status 
        FROM sessions WHERE id = ?
    ''', (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "framework": Framework.model_validate_json(row[0]),
            "content": json.loads(row[1]) if row[1] else None,
            "constraints": row[2],
            "status": row[3]
        }
    return None

def log_action(session_id: str, action: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Логирование действий методиста."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('INSERT INTO audit_logs (session_id, action) VALUES (?, ?)', (session_id, action))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка аудита: {e}")