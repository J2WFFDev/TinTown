"""Streaming NDJSON to SQLite ingest service."""

import argparse
import asyncio
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from database import create_database_schema


class StreamingIngest:
    """Streams NDJSON logs to SQLite database in real-time."""
    
    def __init__(self, log_dir: str, db_path: str, file_prefix: str = "bridge") -> None:
        self.log_dir = Path(log_dir)
        self.db_path = db_path
        self.file_prefix = file_prefix
        self._stop_requested = False
        self._current_file: Optional[Path] = None
        self._file_position = 0
        
        # Create database schema
        create_database_schema(db_path)
    
    async def start(self) -> None:
        """Start streaming ingest service."""
        print(f"Starting streaming ingest: {self.log_dir} -> {self.db_path}")
        
        while not self._stop_requested:
            try:
                # Check for current log file
                current_file = self._get_current_log_file()
                
                if current_file and current_file.exists():
                    if current_file != self._current_file:
                        # New file detected
                        print(f"Following new log file: {current_file}")
                        self._current_file = current_file
                        self._file_position = 0
                    
                    # Process new lines
                    await self._process_new_lines()
                
                # Check every second
                await asyncio.sleep(1.0)
                
            except Exception as e:
                print(f"Ingest error: {e}")
                await asyncio.sleep(5.0)
    
    def stop(self) -> None:
        """Stop streaming ingest service."""
        self._stop_requested = True
    
    def _get_current_log_file(self) -> Optional[Path]:
        """Get the current log file for today."""
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{self.file_prefix}_{today}.ndjson"
        return self.log_dir / filename
    
    async def _process_new_lines(self) -> None:
        """Process new lines in the current log file."""
        if not self._current_file or not self._current_file.exists():
            return
        
        try:
            with self._current_file.open("r", encoding="utf-8") as f:
                # Seek to last position
                f.seek(self._file_position)
                
                # Read new lines
                new_lines = f.readlines()
                
                if new_lines:
                    # Process lines
                    processed = await self._ingest_lines(new_lines)
                    
                    # Update position
                    self._file_position = f.tell()
                    
                    if processed > 0:
                        print(f"Ingested {processed} new records")
        
        except Exception as e:
            print(f"Error processing file {self._current_file}: {e}")
    
    async def _ingest_lines(self, lines: list[str]) -> int:
        """Ingest a batch of NDJSON lines."""
        if not lines:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        processed = 0
        session_ids = set()
        
        try:
            for line in lines:
                record = self._parse_line(line)
                if record:
                    session_id = self._insert_record(conn, record)
                    if session_id:
                        session_ids.add(session_id)
                        processed += 1
            
            # Update session summaries
            for session_id in session_ids:
                self._update_session_summary(conn, session_id)
            
            conn.commit()
            
        finally:
            conn.close()
        
        return processed
    
    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a single NDJSON line."""
        try:
            record = json.loads(line.strip())
            
            # Add session_id if missing (derive from filename)
            if not record.get("session_id") and self._current_file:
                session_id = self._current_file.stem.split("_")[-1]
                record["session_id"] = session_id
            
            return record
            
        except json.JSONDecodeError:
            return None
    
    def _insert_record(self, conn: sqlite3.Connection, record: Dict) -> Optional[str]:
        """Insert a record into the database."""
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
                record.get("session_id"),
                json.dumps(record.get("data")) if record.get("data") else None,
                "v1",
            ))
            
            return record.get("session_id")
            
        except sqlite3.Error as e:
            print(f"Error inserting record: {e}")
            return None
    
    def _update_session_summary(self, conn: sqlite3.Connection, session_id: str) -> None:
        """Update session summary statistics."""
        try:
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
                conn.execute("""
                    INSERT OR REPLACE INTO sessions (
                        session_id, start_ts_ms, end_ts_ms, event_count, hit_count, plate_count, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (session_id, *session_stats))
                
        except sqlite3.Error as e:
            print(f"Error updating session summary: {e}")


async def main() -> None:
    """CLI entry point for streaming ingest."""
    parser = argparse.ArgumentParser(description="Stream NDJSON logs to SQLite database")
    parser.add_argument("--log-dir", default="logs", help="Log directory to monitor")
    parser.add_argument("--db", default="db/bridge.db", help="SQLite database path")
    parser.add_argument("--prefix", default="bridge", help="Log file prefix")
    
    args = parser.parse_args()
    
    ingest = StreamingIngest(args.log_dir, args.db, args.prefix)
    
    try:
        await ingest.start()
    except KeyboardInterrupt:
        print("\\nStopping streaming ingest...")
        ingest.stop()


if __name__ == "__main__":
    asyncio.run(main())