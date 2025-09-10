"""SQLite database schema and utilities for NDJSON ingest."""

import sqlite3
from pathlib import Path
from typing import Optional


def create_database_schema(db_path: str) -> None:
    """Create SQLite database schema for bridge events."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for concurrent access
    
    # Create events table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq INTEGER NOT NULL,
            ts_ms REAL NOT NULL,
            type TEXT NOT NULL,
            msg TEXT NOT NULL,
            plate TEXT,
            t_rel_ms REAL,
            session_id TEXT,
            pid INTEGER,
            schema TEXT DEFAULT 'v1',
            data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, seq)
        )
    """)
    
    # Create indices for common queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts_ms ON events(ts_ms)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_plate ON events(plate)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_msg ON events(msg)")
    
    # Create sessions summary table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            start_ts_ms REAL,
            end_ts_ms REAL,
            event_count INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            plate_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def get_database_info(db_path: str) -> dict:
    """Get database information and statistics."""
    if not Path(db_path).exists():
        return {"error": "Database not found"}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get table info
    tables = conn.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
    """).fetchall()
    
    # Get event counts
    event_stats = conn.execute("""
        SELECT 
            COUNT(*) as total_events,
            COUNT(DISTINCT session_id) as session_count,
            COUNT(DISTINCT plate) as plate_count,
            MIN(ts_ms) as earliest_ts,
            MAX(ts_ms) as latest_ts,
            COUNT(CASE WHEN type='event' AND msg='HIT' THEN 1 END) as hit_count
        FROM events
    """).fetchone()
    
    # Get recent sessions
    recent_sessions = conn.execute("""
        SELECT session_id, start_ts_ms, end_ts_ms, event_count, hit_count
        FROM sessions
        ORDER BY start_ts_ms DESC
        LIMIT 5
    """).fetchall()
    
    conn.close()
    
    return {
        "tables": [dict(row) for row in tables],
        "stats": dict(event_stats) if event_stats else {},
        "recent_sessions": [dict(row) for row in recent_sessions],
    }


def validate_database(db_path: str) -> list[str]:
    """Validate database schema and return any issues."""
    issues = []
    
    if not Path(db_path).exists():
        issues.append("Database file does not exist")
        return issues
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check required tables exist
        tables = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table'
        """).fetchall()
        table_names = [row[0] for row in tables]
        
        if "events" not in table_names:
            issues.append("Missing events table")
        
        if "sessions" not in table_names:
            issues.append("Missing sessions table")
        
        # Check events table schema
        if "events" in table_names:
            columns = conn.execute("PRAGMA table_info(events)").fetchall()
            column_names = [col[1] for col in columns]
            
            required_columns = ["seq", "ts_ms", "type", "msg", "plate", "t_rel_ms", "session_id"]
            for col in required_columns:
                if col not in column_names:
                    issues.append(f"Missing column in events table: {col}")
        
        # Check indices exist
        indices = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        index_names = [row[0] for row in indices]
        
        required_indices = ["idx_events_session_id", "idx_events_type", "idx_events_ts_ms"]
        for idx in required_indices:
            if idx not in index_names:
                issues.append(f"Missing index: {idx}")
        
        conn.close()
        
    except sqlite3.Error as e:
        issues.append(f"Database error: {e}")
    
    return issues