"""Batch NDJSON to SQLite ingest tool."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional

from database import create_database_schema


def parse_ndjson_line(line: str) -> Optional[Dict]:
    """Parse a single NDJSON line."""
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def ingest_ndjson_file(ndjson_path: str, db_path: str, session_filter: Optional[str] = None) -> Dict:
    """Ingest NDJSON file into SQLite database."""
    ndjson_file = Path(ndjson_path)
    if not ndjson_file.exists():
        raise FileNotFoundError(f"NDJSON file not found: {ndjson_path}")
    
    # Create database schema if needed
    create_database_schema(db_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    
    stats = {
        "total_lines": 0,
        "valid_records": 0,
        "inserted_records": 0,
        "skipped_records": 0,
        "error_records": 0,
        "sessions": set(),
    }
    
    try:
        with ndjson_file.open("r", encoding="utf-8") as f:
            for line in f:
                stats["total_lines"] += 1
                
                # Parse JSON
                record = parse_ndjson_line(line)
                if not record:
                    stats["error_records"] += 1
                    continue
                
                stats["valid_records"] += 1
                
                # Extract session_id (from filename or record)
                session_id = record.get("session_id")
                if not session_id:
                    # Derive from filename: bridge_20250906.ndjson -> 20250906
                    session_id = ndjson_file.stem.split("_")[-1]
                    record["session_id"] = session_id
                
                stats["sessions"].add(session_id)
                
                # Filter by session if requested
                if session_filter and session_id != session_filter:
                    stats["skipped_records"] += 1
                    continue
                
                # Insert record
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO events (
                            seq, ts_ms, type, msg, plate, t_rel_ms, session_id, 
                            data_json, schema
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.get("seq"),
                        record.get("ts_ms"),
                        record.get("type"),
                        record.get("msg"),
                        record.get("plate"),
                        record.get("t_rel_ms"),
                        session_id,
                        json.dumps(record.get("data")) if record.get("data") else None,
                        "v1",
                    ))
                    stats["inserted_records"] += 1
                    
                except sqlite3.Error as e:
                    print(f"Error inserting record {stats['total_lines']}: {e}", file=sys.stderr)
                    stats["error_records"] += 1
        
        # Update session summary
        for session_id in stats["sessions"]:
            update_session_summary(conn, session_id)
        
        conn.commit()
        
    finally:
        conn.close()
    
    # Convert set to list for JSON serialization
    stats["sessions"] = sorted(list(stats["sessions"]))
    
    return stats


def update_session_summary(conn: sqlite3.Connection, session_id: str) -> None:
    """Update session summary statistics."""
    # Get session statistics
    session_stats = conn.execute("""
        SELECT 
            MIN(ts_ms) as start_ts,
            MAX(ts_ms) as end_ts,
            COUNT(*) as event_count,
            COUNT(CASE WHEN type='event' AND msg='HIT' THEN 1 END) as hit_count,
            COUNT(DISTINCT plate) as plate_count
        FROM events 
        WHERE session_id = ?
    """, (session_id,)).fetchone()
    
    if session_stats and session_stats[0] is not None:
        # Insert or update session summary
        conn.execute("""
            INSERT OR REPLACE INTO sessions (
                session_id, start_ts_ms, end_ts_ms, event_count, hit_count, plate_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (session_id, *session_stats))


def main() -> None:
    """CLI entry point for batch ingest."""
    parser = argparse.ArgumentParser(description="Ingest NDJSON files into SQLite database")
    parser.add_argument("ndjson_file", help="Path to NDJSON file to ingest")
    parser.add_argument("--db", default="db/bridge.db", help="SQLite database path")
    parser.add_argument("--session", help="Filter by specific session ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    try:
        stats = ingest_ndjson_file(args.ndjson_file, args.db, args.session)
        
        print(f"Ingest completed:")
        print(f"  Total lines: {stats['total_lines']}")
        print(f"  Valid records: {stats['valid_records']}")
        print(f"  Inserted: {stats['inserted_records']}")
        print(f"  Skipped: {stats['skipped_records']}")
        print(f"  Errors: {stats['error_records']}")
        print(f"  Sessions: {', '.join(stats['sessions'])}")
        
        if args.verbose:
            print(f"\\nFull statistics: {json.dumps(stats, indent=2)}")
        
    except Exception as e:
        print(f"Ingest failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()