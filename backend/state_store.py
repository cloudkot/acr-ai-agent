import sqlite3
import json
import asyncio
from schemas import Framework
from logger import logger

DB_PATH = "sessions.db"

# ==========================================
# [АРХИТЕКТУРА]: Синхронные операции (выполняются в отдельных потоках)
# ==========================================

def _init_db_sync():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Миграции для существующих баз (добавляем колонки, если их нет)
    migrations = ["constraints TEXT", "tokens_used INTEGER DEFAULT 0", "cost_rub REAL DEFAULT 0.0"]
    for col in migrations:
        try:
            cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    conn.close()

def _save_session_sync(session_id, framework_json, status, content_str, constraints, tokens_used, cost_rub):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (id, framework_json, content_json, constraints, status, tokens_used, cost_rub)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, framework_json, content_str, constraints, status, tokens_used, cost_rub))
    conn.commit()
    conn.close()

def _get_session_sync(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT framework_json, content_json, constraints, status, tokens_used, cost_rub 
        FROM sessions WHERE id = ?
    ''', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def _log_action_sync(session_id: str, action: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('INSERT INTO audit_logs (session_id, action) VALUES (?, ?)', (session_id, action))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка аудита: {e}")

def _get_analytics_sync():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(tokens_used), SUM(cost_rub) FROM sessions WHERE status = 'completed'")
    row = cursor.fetchone()
    conn.close()
    return row

# ==========================================
# [АРХИТЕКТУРА]: Асинхронные обертки
# ==========================================

async def init_db():
    """[ФИКС АРХИТЕКТУРЫ]: Инициализация БД в отдельном потоке."""
    await asyncio.to_thread(_init_db_sync)

async def save_session(
    session_id: str, 
    framework: Framework, 
    status: str, 
    content: dict = None, 
    constraints: str = None,
    tokens_used: int = 0,
    cost_rub: float = 0.0
):
    """[ФИКС АРХИТЕКТУРЫ]: Сохранение сессии без блокировки event loop."""
    content_str = json.dumps(content, ensure_ascii=False) if content else None
    await asyncio.to_thread(
        _save_session_sync, 
        session_id, framework.model_dump_json(), status, 
        content_str, constraints, tokens_used, cost_rub
    )

async def get_session(session_id: str) -> dict:
    """[ФИКС АРХИТЕКТУРЫ]: Асинхронное чтение сессии."""
    row = await asyncio.to_thread(_get_session_sync, session_id)
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

async def log_action(session_id: str, action: str):
    """[ФИКС АРХИТЕКТУРЫ]: Асинхронный аудит."""
    await asyncio.to_thread(_log_action_sync, session_id, action)

async def get_analytics() -> dict:
    """[ФИКС АРХИТЕКТУРЫ]: Асинхронный сбор статистики."""
    try:
        completed, total_tokens, total_cost = await asyncio.to_thread(_get_analytics_sync)
        return {
            "completed_programs": completed or 0,
            "total_cost_rub": round(total_cost or 0.0, 2),
            "total_tokens_used": total_tokens or 0
        }
    except Exception as e:
        logger.error(f"Ошибка аналитики: {e}")
        return {"completed_programs": 0, "total_cost_rub": 0.0, "total_tokens_used": 0}