"""NDJSON logging with sequence numbers and rotation."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, Union


class NdjsonLogger:
    """Thread-safe NDJSON logger with automatic rotation and sequence numbers."""
    
    def __init__(self, log_dir: str, file_prefix: str = "bridge") -> None:
        self.log_dir = Path(log_dir)
        self.file_prefix = file_prefix
        self.mode = "regular"  # regular or verbose
        self.verbose_whitelist: set[str] = set()
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self._seq = 0
        self._current_file: Optional[TextIO] = None
        self._current_date: Optional[str] = None
        self._start_time_ns = time.monotonic_ns()
        
        # Open initial log file
        self._rotate_if_needed()
    
    def log(
        self,
        msg_type: str,
        msg: str,
        plate: Optional[str] = None,
        t_rel_ms: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a structured message to NDJSON."""
        self._rotate_if_needed()
        
        # Filter debug messages based on mode and whitelist
        if msg_type == "debug" and self.mode == "regular":
            if msg not in self.verbose_whitelist:
                return
        
        self._seq += 1
        
        # Calculate timestamps
        now_ns = time.monotonic_ns()
        ts_ms = (now_ns - self._start_time_ns) / 1_000_000
        
        # Build log record
        record = {
            "seq": self._seq,
            "type": msg_type,
            "ts_ms": round(ts_ms, 3),
            "msg": msg,
        }
        
        # Add optional fields
        if t_rel_ms is not None:
            record["t_rel_ms"] = round(t_rel_ms, 3)
        if plate is not None:
            record["plate"] = plate
        if data is not None:
            record["data"] = data
        
        # Add human-readable timestamp
        record["hms"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Write to file
        if self._current_file:
            json.dump(record, self._current_file, separators=(",", ":"), ensure_ascii=False)
            self._current_file.write("\n")
            self._current_file.flush()
    
    def event(
        self,
        msg: str,
        plate: Optional[str] = None,
        t_rel_ms: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an event message."""
        self.log("event", msg, plate=plate, t_rel_ms=t_rel_ms, data=data)
    
    def status(
        self,
        msg: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a status message."""
        self.log("status", msg, data=data)
    
    def error(
        self,
        msg: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an error message."""
        self.log("error", msg, data=data)
    
    def debug(
        self,
        msg: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a debug message (subject to filtering)."""
        self.log("debug", msg, data=data)
    
    def close(self) -> None:
        """Close the current log file."""
        if self._current_file:
            self._current_file.close()
            self._current_file = None
    
    def _rotate_if_needed(self) -> None:
        """Rotate log file if date has changed."""
        current_date = datetime.now().strftime("%Y%m%d")
        
        if self._current_date != current_date:
            # Close existing file
            if self._current_file:
                self._current_file.close()
            
            # Open new file for current date
            log_filename = f"{self.file_prefix}_{current_date}.ndjson"
            log_path = self.log_dir / log_filename
            
            self._current_file = log_path.open("a", encoding="utf-8", buffering=1)
            self._current_date = current_date
    
    def __enter__(self) -> NdjsonLogger:
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class DualNdjsonLogger(NdjsonLogger):
    """Extended logger that writes to both main and debug files."""
    
    def __init__(self, log_dir: str, debug_dir: str, file_prefix: str = "bridge") -> None:
        super().__init__(log_dir, file_prefix)
        
        self.debug_dir = Path(debug_dir)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        
        self._debug_file: Optional[TextIO] = None
        self._debug_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Open debug file
        debug_filename = f"{file_prefix}_debug_{self._debug_session}.ndjson"
        debug_path = self.debug_dir / debug_filename
        self._debug_file = debug_path.open("a", encoding="utf-8", buffering=1)
    
    def log(
        self,
        msg_type: str,
        msg: str,
        plate: Optional[str] = None,
        t_rel_ms: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log to both main and debug files."""
        # Always write to debug file
        if self._debug_file:
            self._seq += 1
            now_ns = time.monotonic_ns()
            ts_ms = (now_ns - self._start_time_ns) / 1_000_000
            
            debug_record = {
                "seq": self._seq,
                "type": msg_type,
                "ts_ms": round(ts_ms, 3),
                "msg": msg,
                "hms": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            }
            
            if t_rel_ms is not None:
                debug_record["t_rel_ms"] = round(t_rel_ms, 3)
            if plate is not None:
                debug_record["plate"] = plate
            if data is not None:
                debug_record["data"] = data
            
            json.dump(debug_record, self._debug_file, separators=(",", ":"), ensure_ascii=False)
            self._debug_file.write("\n")
            self._debug_file.flush()
        
        # Write to main file (with filtering)
        # Decrement seq since parent will increment it
        self._seq -= 1
        super().log(msg_type, msg, plate=plate, t_rel_ms=t_rel_ms, data=data)
    
    def close(self) -> None:
        """Close both main and debug files."""
        super().close()
        if self._debug_file:
            self._debug_file.close()
            self._debug_file = None