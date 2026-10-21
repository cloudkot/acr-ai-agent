import sqlite3
import json
from schemas import Framework
from logger import logger

DB_PATH = "sessions.db"

def init_db():
    """[ТРЕБОВАНИЕ КЕЙСА]: Инициализация БД и миграции."""
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
    
    # Надежная миграция для всех новых колонок
    migrations = [
        "constraints TEXT", 
        "tokens_used INTEGER DEFAULT 0", 
        "cost_rub REAL DEFAULT 0.0"
    ]
    for col in migrations:
        try:
            cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass # Колонка уже существует
            
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
    """Сохраняет или обновляет сессию и метрики."""
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
    """Достает сессию из БД."""
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

def get_analytics():
    """
    [УНИКАЛЬНАЯ ФИЧА]: Сбор метрик для дашборда.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        conn.close()
        
        return {
            "completed_programs": completed,
            "estimated_hours_saved": completed * 40, # 40 часов экономии на 1 программу
            "estimated_cost_rub": completed * 15.0   # Примерная стоимость 15 руб за программу
        }
    except Exception as e:
        logger.error(f"Ошибка аналитики: {e}")
        return {"completed_programs": 0, "estimated_hours_saved": 0, "estimated_cost_rub": 0.0}