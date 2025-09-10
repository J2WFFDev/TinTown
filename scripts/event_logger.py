"""Structured event logging for main operational events."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, Union


class StructuredEventLogger:
    """Logger for structured events in CSV and NDJSON formats."""
    
    def __init__(self, log_dir: str, debug_dir: str, file_prefix: str = "bridge") -> None:
        self.log_dir = Path(log_dir)
        self.debug_dir = Path(debug_dir)
        self.file_prefix = file_prefix
        
        # Ensure directories exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self._seq = 0
        self._session_start = datetime.now()
        self._string_start_time: Optional[datetime] = None
        self._shots_detected = 0
        self._impacts_detected = 0
        
        # File handles
        self._main_csv: Optional[TextIO] = None
        self._main_ndjson: Optional[TextIO] = None
        self._debug_ndjson: Optional[TextIO] = None
        self._current_date: Optional[str] = None
        
        # Device position mappings
        self._device_positions = {
            "MCU1": "Bay 1",
            "12:E3": "Plate 1",  # BT50 sensor (last 5 chars of F8:FE:92:31:12:E3)
            "DC:1A": "Bay 1",    # AMG timer (last 5 chars of 60:09:C3:1F:DC:1A)
            "2:E3": "Plate 1",   # Alternative format for BT50 (old 4-char format)
            "C:1A": "Bay 1",     # Alternative format for AMG (old 4-char format)
        }
        
        # Initialize log files
        self._rotate_if_needed()
    
    def _rotate_if_needed(self) -> None:
        """Rotate log files if date has changed."""
        current_date = datetime.now().strftime("%Y%m%d")
        
        if self._current_date != current_date:
            # Close existing files
            if self._main_csv:
                self._main_csv.close()
            if self._main_ndjson:
                self._main_ndjson.close()
            if self._debug_ndjson:
                self._debug_ndjson.close()
            
            # Open new files for current date
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Main CSV file (structured events)
            csv_filename = f"{self.file_prefix}_main_{current_date}.csv"
            csv_path = self.log_dir / "main" / csv_filename
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._main_csv = csv_path.open("a", encoding="utf-8", newline="")
            
            # Write CSV header if file is empty
            if csv_path.stat().st_size == 0:
                csv_writer = csv.writer(self._main_csv)
                csv_writer.writerow(["Datetime", "Type", "Device", "DeviceID", "DevicePosition", "Details"])
            
            # Main NDJSON file (structured events)
            ndjson_filename = f"{self.file_prefix}_main_{current_date}.ndjson"
            ndjson_path = self.log_dir / "main" / ndjson_filename
            self._main_ndjson = ndjson_path.open("a", encoding="utf-8", buffering=1)
            
            # Debug NDJSON file (raw device signals)
            debug_filename = f"{self.file_prefix}_debug_{timestamp}.ndjson"
            debug_path = self.debug_dir / debug_filename
            self._debug_ndjson = debug_path.open("a", encoding="utf-8", buffering=1)
            
            self._current_date = current_date
    
    def _format_datetime(self, dt: Optional[datetime] = None) -> str:
        """Format datetime in the required format: 9/9/25 8:44:01.22am"""
        if dt is None:
            dt = datetime.now()
        
        # Format: M/D/YY H:MM:SS.SSam/pm
        # Use strftime for cross-platform compatibility
        date_part = dt.strftime("%m/%d/%y").lstrip("0").replace("/0", "/")
        time_part = dt.strftime("%I:%M:%S.%f")[:-4]  # Remove last 4 microsecond digits
        time_part = time_part.lstrip("0")  # Remove leading zero from hour
        if time_part.startswith(":"):
            time_part = "12" + time_part  # Handle midnight case
        ampm = dt.strftime("%p").lower()
        
        return f"{date_part} {time_part}{ampm}"
    
    def _get_device_position(self, device_id: str) -> str:
        """Get device position from device ID."""
        return self._device_positions.get(device_id, "Unknown")
    
    def _write_main_event(self, event_type: str, device: str, device_id: str, details: str) -> None:
        """Write event to both CSV and NDJSON main logs."""
        self._rotate_if_needed()
        
        datetime_str = self._format_datetime()
        device_position = self._get_device_position(device_id)
        
        # Write to CSV
        if self._main_csv:
            csv_writer = csv.writer(self._main_csv)
            csv_writer.writerow([datetime_str, event_type, device, device_id, device_position, details])
            self._main_csv.flush()
        
        # Write to NDJSON
        if self._main_ndjson:
            record = {
                "datetime": datetime_str,
                "type": event_type,
                "device": device,
                "device_id": device_id,
                "device_position": device_position,
                "details": details,
                "timestamp_iso": datetime.now().isoformat(),
                "seq": self._seq
            }
            json.dump(record, self._main_ndjson, separators=(",", ":"))
            self._main_ndjson.write("\n")
            self._main_ndjson.flush()
        
        self._seq += 1
    
    def _write_debug_raw(self, device: str, device_id: str, msg_type: str, data: Dict[str, Any]) -> None:
        """Write raw device signal to debug log."""
        if self._debug_ndjson:
            record = {
                "timestamp_iso": datetime.now().isoformat(),
                "device": device,
                "device_id": device_id,
                "type": msg_type,
                "data": data,
                "seq": self._seq
            }
            json.dump(record, self._debug_ndjson, separators=(",", ":"))
            self._debug_ndjson.write("\n")
            self._debug_ndjson.flush()
        
        self._seq += 1
    
    # Main event logging methods
    def bridge_initialized(self) -> None:
        """Log bridge initialization."""
        self._write_main_event(
            "Status", "Bridge", "MCU1", 
            "Bridge Initialized (Killed any existing bridge processes, reset BLE)"
        )
    
    def ble_scanning(self) -> None:
        """Log BLE scanning start."""
        self._write_main_event("Status", "Bridge", "MCU1", "BLE Scanning")
    
    def devices_located(self) -> None:
        """Log device discovery completion."""
        self._write_main_event("Status", "Bridge", "MCU1", "Devices Located")
    
    def sensor_connected(self, device_id: str) -> None:
        """Log sensor connection."""
        self._write_main_event("Status", "Sensor", device_id, "Connected")
    
    def timer_connected(self, device_id: str) -> None:
        """Log timer connection."""
        self._write_main_event("Status", "Timer", device_id, "Connected")
    
    def sensor_streaming(self, device_id: str) -> None:
        """Log sensor data streaming start."""
        self._write_main_event("Status", "Sensor", device_id, "Sensor data streaming")
    
    def timer_start_button(self, device_id: str, countdown_seconds: float) -> None:
        """Log timer start button press."""
        self._string_start_time = datetime.now()
        self._shots_detected = 0
        self._impacts_detected = 0
        
        self._write_main_event(
            "String", "Timer", device_id, 
            f"Timer Start Button pressed, Random countdown: {countdown_seconds:.2f}s"
        )
    
    def timer_start_beep(self, device_id: str) -> None:
        """Log timer start beep."""
        self._write_main_event("String", "Timer", device_id, "Timer Start Beep")
    
    def shot_detected(self, device_id: str) -> None:
        """Log shot detection by timer."""
        self._shots_detected += 1
        self._write_main_event("String", "Timer", device_id, "Shot detected")
    
    def impact_detected(self, device_id: str) -> None:
        """Log impact detection by sensor."""
        self._impacts_detected += 1
        self._write_main_event("String", "Sensor", device_id, "Sensor Impact detected")
    
    def timer_stop_button(self, device_id: str) -> None:
        """Log timer stop button press."""
        self._write_main_event("String", "Timer", device_id, "Timer stop button pressed")
    
    def string_summary(self) -> None:
        """Log string summary."""
        if self._string_start_time:
            duration = (datetime.now() - self._string_start_time).total_seconds()
            self._write_main_event(
                "StringSummary", "Bridge", "MCU1",
                f"String Time: {duration:.2f}s; Shots Detected: {self._shots_detected}; Impacts Detected: {self._impacts_detected}"
            )
    
    # Raw device signal logging methods
    def log_amg_raw(self, device_id: str, data: Dict[str, Any]) -> None:
        """Log raw AMG timer data."""
        self._write_debug_raw("Timer", device_id, "amg_raw", data)
    
    def log_string_event(self, device_id: str, event_detail: str, parsed_data: Dict[str, Any]) -> None:
        """Log structured string event from parsed AMG data."""
        self._write_main_event("String", "Timer", device_id, event_detail)
        
        # Also log to debug with full parsed data
        self._write_debug_raw("Timer", device_id, "amg_parsed", {
            "event": event_detail,
            "parsed": parsed_data
        })
    
    def log_bt50_raw(self, device_id: str, data: Dict[str, Any]) -> None:
        """Log raw BT50 sensor data."""
        self._write_debug_raw("Sensor", device_id, "bt50_raw", data)
    
    def log_bt50_parsed(self, device_id: str, data: Dict[str, Any]) -> None:
        """Log parsed BT50 sensor data."""
        self._write_debug_raw("Sensor", device_id, "bt50_parsed", data)
    
    def log_connection_event(self, device: str, device_id: str, event: str, data: Dict[str, Any]) -> None:
        """Log connection-related events."""
        self._write_debug_raw(device, device_id, f"connection_{event}", data)
    
    def close(self) -> None:
        """Close all log files."""
        if self._main_csv:
            self._main_csv.close()
            self._main_csv = None
        if self._main_ndjson:
            self._main_ndjson.close()
            self._main_ndjson = None
        if self._debug_ndjson:
            self._debug_ndjson.close()
            self._debug_ndjson = None
    
    def __enter__(self) -> StructuredEventLogger:
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class EventDetector:
    """Detects events from raw device data and triggers structured logging."""
    
    def __init__(self, event_logger: StructuredEventLogger) -> None:
        self.logger = event_logger
        self._timer_state = "idle"  # idle, countdown, active, stopped
        self._last_amg_message = ""
        self._impact_threshold = 0.002  # Threshold for impact detection (2mg - tuned for BT50 sensor readings)
        self._last_shot_number = 0  # Track last shot number to avoid duplicates
    
    def process_amg_data(self, device_id: str, ascii_data: str, raw_data: Dict[str, Any]) -> None:
        """Process AMG timer data and detect events."""
        # Log raw data
        self.logger.log_amg_raw(device_id, raw_data)
        
        # Detect timer events from ASCII data
        ascii_clean = ascii_data.strip().lower()
        
        if "start" in ascii_clean and "button" in ascii_clean:
            # Extract countdown if present
            countdown = 2.25  # Default, could parse from message
            self.logger.timer_start_button(device_id, countdown)
            self._timer_state = "countdown"
        
        elif "beep" in ascii_clean or "start beep" in ascii_clean:
            self.logger.timer_start_beep(device_id)
            self._timer_state = "active"
        
        elif "shot" in ascii_clean and self._timer_state == "active":
            self.logger.shot_detected(device_id)
        
        elif "stop" in ascii_clean and "button" in ascii_clean:
            self.logger.timer_stop_button(device_id)
            self.logger.string_summary()
            self._timer_state = "stopped"
    
    def process_amg_string_event(self, device_id: str, event_detail: str, parsed_data: Dict[str, Any]) -> None:
        """Process parsed AMG timer string events."""
        # Log the parsed string event
        self.logger.log_string_event(device_id, event_detail, parsed_data)
        
        # Determine state based on parsed data
        shot_state = parsed_data.get('shot_state', '')
        
        if shot_state == 'START':
            self.logger.timer_start_beep(device_id)
            self._timer_state = "active"
        
        elif shot_state == 'ACTIVE':
            # Shot detection - only trigger on new shots
            current_shot = parsed_data.get('current_shot', 0)
            if current_shot > 0 and current_shot > self._last_shot_number:
                self.logger.shot_detected(device_id)
                self._last_shot_number = current_shot
        
        elif shot_state == 'STOPPED':
            self.logger.timer_stop_button(device_id)
            self.logger.string_summary()
            self._timer_state = "stopped"
    
    def process_bt50_data(self, device_id: str, parsed_data: Dict[str, Any], raw_data: Dict[str, Any]) -> None:
        """Process BT50 sensor data and detect impacts."""
        # Log raw and parsed data
        self.logger.log_bt50_raw(device_id, raw_data)
        self.logger.log_bt50_parsed(device_id, parsed_data)
        
        # Check if we have raw count data (new approach)
        if 'magnitude_corrected' in parsed_data:
            # Use raw count-based impact detection
            magnitude_corrected = parsed_data.get('magnitude_corrected', 0.0)
            threshold = parsed_data.get('threshold', 50)
            
            if magnitude_corrected > threshold and self._timer_state == "active":
                self.logger.impact_detected(device_id)
        else:
            # Fallback to float-based detection (old approach)
            magnitude = parsed_data.get('mag', 0.0)
            rms = parsed_data.get('rms', 0.0)
            peak = parsed_data.get('peak', 0.0)
            
            # Use highest value for impact detection
            amplitude = max(magnitude or 0.0, rms or 0.0, peak or 0.0)
            
            if amplitude > self._impact_threshold and self._timer_state == "active":
                self.logger.impact_detected(device_id)
    
    def process_bt50_impact(self, device_id: str, impact_data: Dict[str, Any]) -> None:
        """Process a detected BT50 impact using raw count data."""
        # Log the impact if timer is active
        if self._timer_state == "active":
            self.logger.impact_detected(device_id)
        
        # Always log the raw impact data for debugging
        self.logger.log_bt50_raw(device_id, {
            "impact_magnitude": impact_data.get('magnitude', 0),
            "threshold": impact_data.get('threshold', 50),
            "raw_values": impact_data.get('raw_values', []),
            "corrected_values": impact_data.get('corrected_values', []),
            "timestamp_ns": impact_data.get('timestamp_ns', 0)
        })