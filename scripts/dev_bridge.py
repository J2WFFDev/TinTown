#!/usr/bin/env python3
"""
Dev Bridge - Copy of Minimal Bridge that logs to `logs/dev`

Purpose: Preserve the minimal bridge as a development baseline while
allowing separate logs and runs from the original `minimal_bridge.py`.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner
import struct
import logging
import math
import traceback
import random
import subprocess

# Helper functions

def parse_bt50_payload(data: bytes, units='g'):
    """Interpret payload as little-endian float32 array and convert units."""
    n = len(data) // 4
    if n <= 0:
        return []
    fmt = '<' + 'f' * n
    parts = list(struct.unpack(fmt, data[:4*n]))
    if units == 'm/s2':
        parts = [v * 9.80665 for v in parts]
    return parts


def compute_rms(values):
    if not values:
        return 0.0
    s = sum((v * v) for v in values)
    return math.sqrt(s / len(values))


def compute_peak(values):
    if not values:
        return 0.0
    return max((abs(v) for v in values), default=0.0)


def vector_magnitude(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


class Lowpass:
    """Simple single-pole IIR lowpass filter."""
    def __init__(self, alpha=0.1):
        self.alpha = float(alpha)
        self.state = None

    def filter(self, x):
        if self.state is None:
            self.state = x
        else:
            self.state = self.alpha * x + (1.0 - self.alpha) * self.state
        return self.state


# Prefer the structured parser when available
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    from impact_bridge.event_logger import StructuredEventLogger, EventDetector
    print("✓ Successfully imported parse_5561 and event logging modules")
except Exception:
    try:
        from impact_bridge.ble.wtvb_parse import parse_5561
        from impact_bridge.event_logger import StructuredEventLogger, EventDetector
        print("✓ Successfully imported parse_5561 and event logging modules (fallback path)")
    except Exception as e:
        print(f"⚠ Could not import modules: {e}")
        parse_5561 = None
        StructuredEventLogger = None
        EventDetector = None


class ConnectionManager:
    """Maintain a connection to a single peripheral and restart on disconnect."""
    def __init__(self, address, notify_uuid, on_notify_cb, adapter='hci0', logger=None):
        self.address = address
        self.notify_uuid = notify_uuid
        self.on_notify_cb = on_notify_cb
        self.adapter = adapter
        self.logger = logger
        self._task = None
        self._stop = False
        self._consecutive_failures = 0
        self._last_bluez_reset = 0

    async def _reset_bluez_if_needed(self):
        """Reset BlueZ if we're getting too many 'Operation already in progress' errors"""
        now = time.time()
        if self._consecutive_failures >= 3 and (now - self._last_bluez_reset) > 60:
            self._log("warning", "Multiple BlueZ errors detected, attempting adapter reset")
            try:
                # Try to reset the Bluetooth adapter
                result = subprocess.run(['sudo', 'hciconfig', self.adapter, 'down'], 
                                      capture_output=True, text=True, timeout=10)
                await asyncio.sleep(2)
                result = subprocess.run(['sudo', 'hciconfig', self.adapter, 'up'], 
                                      capture_output=True, text=True, timeout=10)
                self._log("info", "Bluetooth adapter reset completed")
                self._last_bluez_reset = now
                self._consecutive_failures = 0
                await asyncio.sleep(5)  # Give BlueZ time to stabilize
                return True
            except Exception as e:
                self._log("error", "Failed to reset Bluetooth adapter", {"error": str(e)})
                return False
        return False

    def _log(self, level, msg, data=None):
        if self.logger:
            self.logger(level, f"ConnectionManager[{self.address}]: {msg}", data or {})

    def start(self):
        if self._task is None:
            self._stop = False
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    async def _run(self):
        backoff = 0.5
        while not self._stop:
            try:
                # Try discovery first
                self._log("debug", "Starting discovery", {"backoff": backoff})
                device = None
                try:
                    device = await BleakScanner.find_device_by_address(self.address, timeout=10.0)
                except Exception as e:
                    self._log("error", "Discovery failed", {"error": str(e)})

                if not device:
                    # If discovery fails, try creating a device from the address directly
                    self._log("warning", "Device not found in discovery, trying direct connection")
                    try:
                        # This works when the device is already connected/paired
                        client = BleakClient(self.address, device=self.adapter)
                        self._log("debug", "Direct client created, attempting connection")
                    except Exception as e:
                        self._log("error", "Could not create direct client", {"error": str(e)})
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30.0)
                        continue
                else:
                    self._log("info", "Device found, attempting connection")
                    client = BleakClient(device, device=self.adapter)

                try:
                    self._log("debug", "Attempting connection with 30s timeout")
                    await client.connect(timeout=30.0)
                    self._log("info", "Connected successfully")

                    def _dc(_client):
                        self._log("warning", "Device disconnected")
                        return

                    try:
                        client.set_disconnected_callback(_dc)
                    except Exception as e:
                        self._log("warning", "Could not set disconnect callback", {"error": str(e)})

                    def _notify(characteristic, data):
                        try:
                            asyncio.get_event_loop().create_task(self.on_notify_cb(characteristic, data, time.time_ns()))
                        except Exception:
                            asyncio.get_event_loop().call_soon_threadsafe(lambda: asyncio.create_task(self.on_notify_cb(characteristic, data, time.time_ns())))

                    await client.start_notify(self.notify_uuid, _notify)
                    self._log("info", "Notifications started")

                    backoff = 0.5
                    while client.is_connected and not self._stop:
                        await asyncio.sleep(1.0)

                    try:
                        await client.stop_notify(self.notify_uuid)
                    except Exception:
                        pass
                finally:
                    try:
                        if client and client.is_connected:
                            await client.disconnect()
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                error_str = str(e)
                self._log("error", "Connection attempt failed", {"error": error_str, "backoff": backoff})
                
                # Track consecutive BlueZ errors
                if "Operation already in progress" in error_str or "org.bluez.Error.InProgress" in error_str:
                    self._consecutive_failures += 1
                    if await self._reset_bluez_if_needed():
                        continue  # Try again immediately after reset
                else:
                    self._consecutive_failures = 0  # Reset counter for non-BlueZ errors
                
                wait = backoff + random.random() * 0.5
                await asyncio.sleep(wait)
                backoff = min(backoff * 2, 30.0)


class DevBridge:
    def __init__(self, log_dir: str | None = None, decode: bool = False, filter_alpha: float = 0.0, units: str = 'g', force_bt_reset: bool = False):
        # Device configurations (same defaults as minimal bridge)
        self.amg_timer_mac = "60:09:C3:1F:DC:1A"
        self.bt50_sensor_mac = "F8:FE:92:31:12:E3"

        # UUIDs for notifications
        self.amg_notify_uuid = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
        self.bt50_notify_uuid = "0000ffe4-0000-1000-8000-00805f9a34fb"

        # Raw count baseline - use integer values directly from sensor (from calibration 20250909_174244)
        self.baseline_x = 2089  # Raw counts - X-axis baseline when vertical (most common value: 108/300 samples)
        self.baseline_y = 0     # Raw counts - Y-axis baseline  
        self.baseline_z = 0     # Raw counts - Z-axis baseline

        # Impact threshold - Raw count changes (based on stationary variation analysis)
        # Normal variation: 2070-2127 (57 counts), so threshold = 3x normal variation
        self.impact_threshold = 150  # Raw counts - Detect changes > 150 counts from baseline

        # Setup logging system
        base_log_dir = log_dir or "logs"
        self.log_dir = Path(base_log_dir)
        self.debug_dir = self.log_dir / "debug"
        
        # Initialize structured event logger
        if StructuredEventLogger and EventDetector:
            self.event_logger = StructuredEventLogger(str(self.log_dir), str(self.debug_dir))
            self.event_detector = EventDetector(self.event_logger)
            print(f"✓ Structured logging initialized")
            print(f"  Main logs: {self.log_dir / 'main'}")
            print(f"  Debug logs: {self.debug_dir}")
        else:
            self.event_logger = None
            self.event_detector = None
            print("⚠ Structured logging disabled - using fallback")

        # Session tracking for fallback logging
        self.session_id = str(int(time.time()))
        self.seq_counter = 0
        
        # Setup fallback log file (dev_bridge format)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fallback_log_file = self.log_dir / "dev" / f"dev_bridge_{timestamp}.ndjson"
        self.fallback_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Debug import status
        if parse_5561:
            print(f"✓ parse_5561 imported successfully")
        else:
            print("⚠ WARNING: parse_5561 not imported - structured parsing disabled")
        
        # Decoding / filtering options
        self.decode_enabled = bool(decode)
        self.filter_alpha = float(filter_alpha) if filter_alpha else 0.0
        self.units = units
        self.force_bt_reset = force_bt_reset
        # lowpass state per value index when filtering is enabled
        self._lp_map = {}
        # last-discovered RSSI placeholder
        self.bt50_rssi = None

        print(f"Dev Bridge starting - Session: {self.session_id}")

        # Notification queue for offloading parse work
        self._notify_q = asyncio.Queue()
        self._parser_workers = []
        # Connection manager placeholder
        self._conn_mgr = None

    def log(self, msg_type, message, data=None):
        """Log an event - now uses dual logging system when available"""
        self.seq_counter += 1
        now = time.time()

        # Use structured logging when available
        if self.event_logger and msg_type in ["status", "connection"]:
            # Map to structured events
            if "Bridge Initialized" in message or "starting" in message.lower():
                self.event_logger.bridge_initialized()
            elif "Scanning" in message or "scan" in message.lower():
                self.event_logger.ble_scanning()
            elif "found" in message.lower() or "located" in message.lower():
                self.event_logger.devices_located()
            # Additional mapping can be added here
        
        # Fallback to NDJSON logging
        log_entry = {
            "type": msg_type,
            "msg": message,
            "data": data or {},
            "hms": datetime.fromtimestamp(now).strftime("%H:%M:%S.%f")[:-3],
            "seq": self.seq_counter,
            "schema": "dev_minimal_v1",
            "session_id": self.session_id
        }

        # Avoid print statements that can cause BrokenPipeError in SSH
        try:
            print(f"[{log_entry['hms']}] {msg_type.upper()}: {message}")
            if data:
                print(f"    Data: {data}")
        except BrokenPipeError:
            # Ignore broken pipe errors when stdout is redirected
            pass

        with open(self.fallback_log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    async def amg_notification_handler(self, characteristic, data):
        from impact_bridge.ble.amg_parse import parse_amg_timer_data, format_amg_event
        
        hex_data = data.hex()
        
        # Extract device ID from MAC (last 5 chars for format like DC:1A)
        device_id = self.amg_timer_mac[-5:].upper()
        
        raw_data = {
            "hex": hex_data,
            "bytes": len(data),
            "sender": str(characteristic)
        }
        
        # Parse AMG data using the new parser
        parsed_data = parse_amg_timer_data(data)
        
        if parsed_data:
            # Use structured logging for parsed data
            if self.event_detector:
                # Create a formatted string for the event detector
                event_detail = format_amg_event(parsed_data)
                self.event_detector.process_amg_string_event(device_id, event_detail, parsed_data)
            else:
                # Fallback logging with parsed data
                self.log("amg_parsed", "AMG timer parsed data", {
                    "device_id": device_id,
                    "event": format_amg_event(parsed_data),
                    "parsed": parsed_data,
                    "raw": raw_data
                })
        else:
            # Try to decode ASCII for legacy compatibility
            ascii_data = ""
            try:
                ascii_data = data.decode('ascii', errors='ignore').strip()
            except:
                pass
            
            # Use event detector if available
            if self.event_detector and ascii_data:
                self.event_detector.process_amg_data(device_id, ascii_data, raw_data)
            else:
                # Fallback logging
                self.log("amg_raw", "AMG timer raw notification", raw_data)
                if ascii_data:
                    self.log("amg_ascii", "AMG timer ASCII data", {"text": ascii_data})

    async def bt50_notification_handler(self, characteristic, data):
        # Extract device ID from MAC (last 5 chars for format like 12:E3)
        device_id = self.bt50_sensor_mac[-5:].upper()
        
        # Log raw data for fallback
        hex_data = data.hex()
        raw_data = {
            "hex": hex_data,
            "bytes": len(data),
            "sender": str(characteristic),
            "rssi": self.bt50_rssi,
        }
        
        # Always log raw data to fallback
        self.log("bt50_raw", "BT50 sensor raw notification", raw_data)

        if self.decode_enabled and len(data) >= 4:
            # enqueue for parser workers
            await self._notify_q.put((characteristic, data, time.time_ns()))

    async def connect_amg_timer(self):
        if self.event_logger:
            # Already logged by initialization
            pass
        self.log("info", "Attempting AMG timer connection", {"mac": self.amg_timer_mac})

        try:
            if self.event_logger:
                self.event_logger.ble_scanning()
            self.log("info", "Scanning for AMG timer")
            devices = await BleakScanner.discover(timeout=10.0)
            amg_device = None

            for device in devices:
                if device.address.upper() == self.amg_timer_mac.upper():
                    amg_device = device
                    break

            if not amg_device:
                self.log("error", "AMG timer not found in scan")
                return None

            if self.event_logger:
                self.event_logger.devices_located()
            self.log("info", "AMG timer found, connecting", {"name": amg_device.name, "rssi": getattr(amg_device, 'rssi', 'unknown')})
            client = BleakClient(amg_device)
            await client.connect()

            device_id = self.amg_timer_mac[-5:].upper()
            if self.event_logger:
                self.event_logger.timer_connected(device_id)
            self.log("success", "AMG timer connected", {"connected": client.is_connected, "services": len(list(client.services)) if client.services else 0})
            await client.start_notify(self.amg_notify_uuid, self.amg_notification_handler)
            self.log("success", "AMG timer notifications enabled")
            return client
        except Exception as e:
            self.log("error", "AMG timer connection failed", {"error": str(e), "type": type(e).__name__})
            return None

    async def connect_bt50_sensor(self):
        # Deprecated - use ConnectionManager for robust handling
        self.log("info", "connect_bt50_sensor is deprecated; using ConnectionManager instead", {"mac": self.bt50_sensor_mac})
        return None

    async def _check_bluetooth_health(self):
        """Check if Bluetooth adapter is healthy and reset if needed"""
        try:
            # Force reset if requested
            if self.force_bt_reset:
                self.log("info", "Force Bluetooth reset requested")
                subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'], timeout=30)
                await asyncio.sleep(10)
                self.log("info", "Bluetooth service restarted")
                return
            
            # Check if hci0 is up
            result = subprocess.run(['hciconfig', 'hci0'], capture_output=True, text=True, timeout=5)
            if 'DOWN' in result.stdout:
                self.log("warning", "Bluetooth adapter is DOWN, bringing it up")
                subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], timeout=10)
                await asyncio.sleep(2)
            
            # Quick scan test to see if BlueZ is responsive
            self.log("debug", "Testing Bluetooth responsiveness")
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                self.log("info", f"Bluetooth health check passed - found {len(devices)} devices")
            except Exception as e:
                if "Operation already in progress" in str(e):
                    self.log("warning", "BlueZ appears stuck, attempting reset")
                    subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'], timeout=30)
                    await asyncio.sleep(10)
                    self.log("info", "Bluetooth service restarted")
                else:
                    self.log("warning", "Bluetooth scan failed", {"error": str(e)})
        except Exception as e:
            self.log("error", "Bluetooth health check failed", {"error": str(e)})

    async def run(self):
        # Initialize bridge
        if self.event_logger:
            self.event_logger.bridge_initialized()
        self.log("info", "Dev Bridge starting", {"amg_mac": self.amg_timer_mac, "bt50_mac": self.bt50_sensor_mac})
        
        # Check Bluetooth health before starting
        await self._check_bluetooth_health()
        
        self.log("info", "Connecting devices sequentially...")
        # Start AMG timer (keep existing behavior)
        amg_client = await self.connect_amg_timer()
        await asyncio.sleep(1.0)

        # Start parser workers
        num_workers = 2
        for _ in range(num_workers):
            w = asyncio.create_task(self._parser_worker())
            self._parser_workers.append(w)

        # Start connection manager for BT50 sensor
        self._conn_mgr = ConnectionManager(self.bt50_sensor_mac, self.bt50_notify_uuid, self._on_notify_enqueue, logger=self.log)
        self._conn_mgr.start()

        # Log sensor connection when established
        device_id = self.bt50_sensor_mac[-5:].upper()
        if self.event_logger:
            self.event_logger.sensor_connected(device_id)
            # Wait a bit then log streaming started
            await asyncio.sleep(2.0)
            self.event_logger.sensor_streaming(device_id)

        self.log("info", "Connection phase started", {"bt50_mac": self.bt50_sensor_mac, "workers": num_workers})

        try:
            print("\n=== DEV BRIDGE ACTIVE ===")
            print("Monitoring raw data from connected devices... (CTRL+C to stop)")
            while True:
                await asyncio.sleep(1)
                if time.time() % 30 < 1:
                    status = {"workers": len(self._parser_workers)}
                    if amg_client:
                        status["amg_connected"] = amg_client.is_connected
                    self.log("status", "Device status check", status)
        except KeyboardInterrupt:
            self.log("info", "Shutdown requested")
        finally:
            # stop connection manager
            if self._conn_mgr:
                await self._conn_mgr.stop()
            # cancel parser workers
            for w in self._parser_workers:
                w.cancel()
            if amg_client and amg_client.is_connected:
                await amg_client.disconnect()
                self.log("info", "AMG timer disconnected")
            
            # Close structured logger
            if self.event_logger:
                self.event_logger.close()
            
            self.log("info", "Dev Bridge shutdown complete")

    async def _on_notify_enqueue(self, sender, data, ts_ns):
        # wrapper used by ConnectionManager
        await self._notify_q.put((sender, data, ts_ns))

    async def _parser_worker(self):
        while True:
            try:
                characteristic, data, ts_ns = await self._notify_q.get()
                try:
                    await self.process_bt50_payload(characteristic, data, ts_ns)
                except Exception as e:
                    tb = traceback.format_exc()
                    self.log("bt50_parse_error", "Worker failed to parse", {"error": str(e), "traceback": tb})
                finally:
                    self._notify_q.task_done()
            except asyncio.CancelledError:
                break

    async def process_bt50_payload(self, characteristic, data, ts_ns=None):
        # move the parsing logic here so workers can call it
        if ts_ns is None:
            ts_ns = time.time_ns()
        
        hex_data = data.hex()
        
        # Log raw payload first for debugging
        self.log("bt50_raw", "BT50 raw notification", {
            "hex": hex_data,
            "length": len(data),
            "rssi": self.bt50_rssi,
            "timestamp_ns": ts_ns
        })
        
        # Debug: log what we actually received
        self.log("debug", "process_bt50_payload called", {
            "characteristic_type": type(characteristic).__name__,
            "data_type": type(data).__name__,
            "ts_ns_type": type(ts_ns).__name__ if ts_ns else "None"
        })
        hex_data = data.hex()
        ts_ns = ts_ns or time.time_ns()
        
        try:
            # Use structured parser to extract raw integer values (no scale factor)
            raw_values = []
            corrected_values = []
            magnitude_corrected = 0.0
            parse_method = None
            
            if parse_5561 and b"\x55\x61" in data:
                self.log("debug", "Found 0x55 0x61 pattern, attempting structured parse", {"hex_preview": hex_data[:32]})
                pkt = None
                matched_offset = None
                max_offsets = 64
                for off in range(0, max_offsets):
                    try:
                        pkt = parse_5561(data if off == 0 else data[off:])
                        if pkt is not None and 'samples' in pkt and pkt['samples']:
                            matched_offset = off
                            self.log("debug", f"parse_5561 SUCCESS at offset {off}", {"samples": len(pkt['samples'])})
                            break
                    except Exception as ex:
                        self.log("debug", f"parse_5561 exception at offset {off}", {"error": str(ex)})
                        pkt = None
                        
                if matched_offset is not None and pkt and pkt['samples']:
                    parse_method = 'structured_raw'
                    sample = pkt['samples'][0]  # First sample
                    
                    # Extract RAW INTEGER values directly (no scale factor applied)
                    if 'raw' in sample:
                        vx_raw, vy_raw, vz_raw = sample['raw']  # Raw int16 values
                        raw_values = [vx_raw, vy_raw, vz_raw]
                        
                        # Apply baseline subtraction to raw values
                        vx_corrected = vx_raw - self.baseline_x
                        vy_corrected = vy_raw - self.baseline_y
                        vz_corrected = vz_raw - self.baseline_z
                        corrected_values = [vx_corrected, vy_corrected, vz_corrected]
                        
                        # Calculate corrected magnitude from raw values
                        magnitude_corrected = (vx_corrected**2 + vy_corrected**2 + vz_corrected**2)**0.5
                        
                        self.log("debug", f"BT50 RAW COUNTS: [{vx_raw},{vy_raw},{vz_raw}] Corrected[{vx_corrected:.1f},{vy_corrected:.1f},{vz_corrected:.1f}] Mag={magnitude_corrected:.1f}")
                        
                        # Check for impact using corrected magnitude
                        if magnitude_corrected > self.impact_threshold:
                            device_id = self.bt50_sensor_mac[-5:].upper()
                            impact_data = {
                                "magnitude": magnitude_corrected,
                                "threshold": self.impact_threshold,
                                "raw_values": raw_values,
                                "corrected_values": corrected_values,
                                "timestamp_ns": ts_ns
                            }
                            
                            if self.event_detector:
                                # Use structured logging for impact
                                self.event_detector.process_bt50_impact(device_id, impact_data)
                            else:
                                # Fallback logging for impact
                                self.log("bt50_impact", f"Impact detected: {magnitude_corrected:.1f} counts", impact_data)
                    else:
                        self.log("warning", "No raw values found in parsed sample", {"sample": sample})
                else:
                    self.log("debug", "parse_5561 did not match payload after offset scan", {"hex_preview": hex_data[:64]})

            # If structured parsing didn't work, fall back to previous approach
            if not raw_values:
                try:
                    values = parse_bt50_payload(data, units=self.units)
                    parse_method = 'float32_fallback'
                except Exception:
                    try:
                        n = len(data) // 4
                        if n <= 0:
                            values = []
                        else:
                            fmt = '<' + 'f' * n
                            parts = list(struct.unpack(fmt, data[:4*n]))
                            if self.units == 'm/s2':
                                parts = [v * 9.80665 for v in parts]
                            values = parts
                            parse_method = 'defensive_float32'
                    except Exception as inner_ex:
                        self.log("debug", "float32 fallback failed", {"error": str(inner_ex)})
                        values = []

                # filtering for fallback values
                if self.filter_alpha and values:
                    for i, v in enumerate(values):
                        try:
                            lp = self._lp_map.get(i)
                            if lp is None:
                                lp = Lowpass(self.filter_alpha)
                                self._lp_map[i] = lp
                            values[i] = lp.filter(v)
                        except Exception as ex_lp:
                            self.log("debug", "Lowpass filter exception, skipping filter for index", {"index": i, "error": str(ex_lp)})

                rms = compute_rms(values)
                peak = compute_peak(values)
                mag = None
                if len(values) >= 3:
                    mag = vector_magnitude(values[0], values[1], values[2])

                parsed = {
                    "timestamp_ns": ts_ns,
                    "values": values,
                    "count": len(values),
                    "units": self.units,
                    "rms": rms,
                    "peak": peak,
                    "mag": mag,
                    "rssi": self.bt50_rssi,
                    "parse_method": parse_method,
                }

                # Use event detector if available
                device_id = self.bt50_sensor_mac[-5:].upper()
                raw_data = {
                    "hex": hex_data,
                    "length": len(data),
                    "rssi": self.bt50_rssi,
                    "timestamp_ns": ts_ns
                }
                
                if self.event_detector:
                    self.event_detector.process_bt50_data(device_id, parsed, raw_data)
                else:
                    # Fallback logging
                    self.log("bt50_parsed", "BT50 parsed sample (fallback)", parsed)
            else:
                # Log successful raw count processing
                parsed = {
                    "timestamp_ns": ts_ns,
                    "raw_values": raw_values,
                    "corrected_values": corrected_values,
                    "magnitude_corrected": magnitude_corrected,
                    "threshold": self.impact_threshold,
                    "parse_method": parse_method,
                    "rssi": self.bt50_rssi,
                }
                
                # Use event detector if available
                device_id = self.bt50_sensor_mac[-5:].upper()
                raw_data = {
                    "hex": hex_data,
                    "length": len(data),
                    "rssi": self.bt50_rssi,
                    "timestamp_ns": ts_ns
                }
                
                if self.event_detector:
                    self.event_detector.process_bt50_data(device_id, parsed, raw_data)
                else:
                    # Fallback logging
                    self.log("bt50_parsed", "BT50 raw count sample", parsed)

        except Exception as e:
            tb = traceback.format_exc()
            self.log("bt50_parse_error", "Could not parse BT50 data", {"error": str(e), "traceback": tb})


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Dev Bridge")
    parser.add_argument("--log-dir", help="Directory to write logs into (default logs/dev)", default=None)
    parser.add_argument("--decode", action="store_true", help="Enable payload decoding into floats and computed metrics")
    parser.add_argument("--filter-alpha", type=float, default=0.0, help="Simple IIR filter alpha (0=no filter, 0.1 small) ")
    parser.add_argument("--units", choices=["g", "m/s2"], default="g", help="Units for parsed values")
    parser.add_argument("--reset-bluetooth", action="store_true", help="Force Bluetooth service restart before starting")
    args = parser.parse_args()

    bridge = DevBridge(log_dir=args.log_dir, decode=args.decode, filter_alpha=args.filter_alpha, units=args.units, force_bt_reset=args.reset_bluetooth)
    await bridge.run()



if __name__ == "__main__":
    print("=== Dev Bridge - Development Copy of Minimal Bridge ===")
    print("")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as e:
        print(f"Error: {e}")

