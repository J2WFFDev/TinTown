#!/usr/bin/env python3
"""
Fixed Dev Bridge - Uses corrected BT50 parser with 1mg scale factor
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from bleak import BleakClient, BleakScanner
import struct
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the corrected parser directly
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    print("✓ Successfully imported corrected parse_5561 with 1mg scale factor")
    PARSER_AVAILABLE = True
except Exception as e:
    print(f"⚠ Parser import failed: {e}")
    PARSER_AVAILABLE = False

# Device MACs
AMG_TIMER_MAC = "60:09:C3:1F:DC:1A"
BT50_SENSOR_MAC = "F8:FE:92:31:12:E3"

# BLE UUIDs
AMG_TIMER_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
BT50_SENSOR_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"

# Raw count baseline - use integer values directly from sensor (from calibration 20250909_174244)
BASELINE_X = 2089  # Raw counts - X-axis baseline when vertical (most common value: 108/300 samples)
BASELINE_Y = 0     # Raw counts - Y-axis baseline  
BASELINE_Z = 0     # Raw counts - Z-axis baseline

# Impact threshold - Raw count changes (based on stationary variation analysis)
# Normal variation: 2070-2127 (57 counts), so threshold = 3x normal variation
IMPACT_THRESHOLD = 150  # Raw counts - Detect changes > 150 counts from baseline from baseline

class FixedBridge:
    def __init__(self):
        self.amg_client = None
        self.bt50_client = None
        self.running = False
        self.session_id = int(time.time())
        
        # Ensure log directories exist
        Path("logs/main").mkdir(parents=True, exist_ok=True)
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup comprehensive logging - both console and debug file"""
        timestamp = datetime.now()
        debug_file = f"logs/debug/bridge_debug_{timestamp.strftime('%Y%m%d_%H%M%S')}.log"
        
        # Create formatters
        console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Console handler for INFO+
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler for ALL debug info
        file_handler = logging.FileHandler(debug_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        self.logger = logging.getLogger("FixedBridge")
        self.logger.info(f"Debug logging enabled: {debug_file}")
        
    def log_event(self, event_type, device, device_id, position, details):
        """Log structured events"""
        timestamp = datetime.now()
        
        # CSV format
        csv_line = f'{timestamp.strftime("%m/%d/%y %I:%M:%S.%f")[:-4]}{timestamp.strftime("%p").lower()},{event_type},{device},{device_id},{position},"{details}"\n'
        
        csv_file = f"logs/main/bridge_main_{timestamp.strftime('%Y%m%d')}.csv"
        with open(csv_file, 'a') as f:
            f.write(csv_line)
            
        # NDJSON format
        json_data = {
            "datetime": timestamp.strftime("%m/%d/%y %I:%M:%S.%f")[:-4] + timestamp.strftime("%p").lower(),
            "type": event_type,
            "device": device,
            "device_id": device_id,
            "device_position": position,
            "details": details,
            "timestamp_iso": timestamp.isoformat(),
            "seq": int(time.time())
        }
        
        ndjson_file = f"logs/main/bridge_main_{timestamp.strftime('%Y%m%d')}.ndjson"
        with open(ndjson_file, 'a') as f:
            f.write(json.dumps(json_data) + '\n')
            
        print(f"📝 {event_type}: {device} {device_id} - {details}")

    async def amg_notification_handler(self, characteristic, data):
        """Handle AMG timer notifications with complete frame capture"""
        hex_data = data.hex()
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Enhanced logging for complete frame analysis
        self.logger.info(f"AMG notification: {hex_data}")
        self.logger.debug(f"AMG raw bytes: {list(data)} (length: {len(data)} bytes)")
        
        # Check if we have expected 32-byte frame
        if len(data) < 32:
            self.logger.warning(f"AMG frame shorter than expected 32 bytes: {len(data)} bytes")
        elif len(data) > 32:
            self.logger.warning(f"AMG frame longer than expected 32 bytes: {len(data)} bytes")
        
        # Enhanced frame type analysis
        if len(data) >= 2:
            frame_header = data[0]
            frame_type = data[1]
            frame_type_names = {0x03: "SHOT", 0x05: "START", 0x08: "STOP"}
            frame_name = frame_type_names.get(frame_type, f"UNKNOWN({frame_type:02x})")
            
            self.logger.info(f"AMG frame type: {frame_header:02x}{frame_type:02x} = {frame_name}")
            
            # Only log shots for frame type 0x03
            if frame_header == 0x01 and frame_type == 0x03 and len(data) >= 3:
                shot_number = data[2]
                self.logger.info(f"AMG SHOT #{shot_number} detected")
                self.log_event("String", "Timer", "DC:1A", "Bay 1", f"Shot #{shot_number} (frame: {hex_data})")
            else:
                self.logger.debug(f"AMG {frame_name} frame (not counting as shot)")
        else:
            self.logger.warning(f"AMG frame too short for type analysis: {len(data)} bytes")

    async def bt50_notification_handler(self, characteristic, data):
        """Handle BT50 sensor notifications with RAW VALUES (no scale factor)"""
        hex_data = data.hex()
        
        # Log raw data
        self.logger.debug(f"BT50 raw: {hex_data[:64]}...")
        
        if not PARSER_AVAILABLE:
            self.logger.warning("Parser not available, skipping impact detection")
            return
            
        # Use parser but extract raw integer values directly
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Get RAW INTEGER values directly (no scale factor applied)
                sample = result['samples'][0]  # First sample
                vx_raw, vy_raw, vz_raw = sample['raw']  # Raw int16 values
                
                # Apply baseline subtraction to raw values
                vx_corrected = vx_raw - BASELINE_X
                vy_corrected = vy_raw - BASELINE_Y
                vz_corrected = vz_raw - BASELINE_Z
                
                # Calculate corrected magnitude from raw values
                magnitude_corrected = (vx_corrected**2 + vy_corrected**2 + vz_corrected**2)**0.5
                magnitude_raw = (vx_raw**2 + vy_raw**2 + vz_raw**2)**0.5
                
                self.logger.info(f"BT50 RAW: [{vx_raw},{vy_raw},{vz_raw}] Corrected[{vx_corrected:.1f},{vy_corrected:.1f},{vz_corrected:.1f}] Mag={magnitude_corrected:.1f}")
                
                # Check for impact using corrected magnitude
                if magnitude_corrected > IMPACT_THRESHOLD:
                    self.log_event("Impact", "Sensor", "12:E3", "Plate 1", 
                                 f"Impact detected: {magnitude_corrected:.1f} (raw: {magnitude_raw:.1f}, threshold: {IMPACT_THRESHOLD})")
                
        except Exception as e:
            self.logger.error(f"BT50 parsing failed: {e}")

    async def connect_devices(self):
        """Connect to both devices"""
        self.log_event("Status", "Bridge", "MCU1", "Bay 1", "Bridge Initialized")
        
        try:
            # Connect AMG Timer
            self.logger.info("Connecting to AMG timer...")
            self.amg_client = BleakClient(AMG_TIMER_MAC)
            await self.amg_client.connect()
            self.log_event("Status", "Timer", "DC:1A", "Bay 1", "Connected")
            
            # Enable notifications
            await self.amg_client.start_notify(AMG_TIMER_UUID, self.amg_notification_handler)
            self.logger.info("AMG timer notifications enabled")
            
        except Exception as e:
            self.logger.error(f"AMG timer connection failed: {e}")
            
        try:
            # Connect BT50 Sensor
            self.logger.info("Connecting to BT50 sensor...")
            self.bt50_client = BleakClient(BT50_SENSOR_MAC)
            await self.bt50_client.connect()
            self.log_event("Status", "Sensor", "12:E3", "Plate 1", "Connected")
            
            # Enable notifications
            await self.bt50_client.start_notify(BT50_SENSOR_UUID, self.bt50_notification_handler)
            self.log_event("Status", "Sensor", "12:E3", "Plate 1", "Sensor data streaming")
            self.logger.info("BT50 sensor notifications enabled")
            
        except Exception as e:
            self.logger.error(f"BT50 sensor connection failed: {e}")

    async def cleanup(self):
        """Proper cleanup of BLE connections"""
        self.logger.info("Cleaning up connections...")
        
        if self.amg_client and self.amg_client.is_connected:
            try:
                await self.amg_client.stop_notify(AMG_TIMER_UUID)
                await self.amg_client.disconnect()
                self.log_event("Status", "Timer", "DC:1A", "Bay 1", "Disconnected")
            except Exception as e:
                self.logger.error(f"AMG cleanup error: {e}")
                
        if self.bt50_client and self.bt50_client.is_connected:
            try:
                await self.bt50_client.stop_notify(BT50_SENSOR_UUID)
                await self.bt50_client.disconnect()
                self.log_event("Status", "Sensor", "12:E3", "Plate 1", "Disconnected")
            except Exception as e:
                self.logger.error(f"BT50 cleanup error: {e}")
                
        self.logger.info("Cleanup complete")

    async def run(self):
        """Main run loop with proper cleanup"""
        self.running = True
        
        try:
            await self.connect_devices()
            
            print("\n=== RAW COUNT BRIDGE ACTIVE ===")
            print("Using RAW integer counts from BT50 sensor (no scale factor)")
            print("Simple subtraction approach: Raw - Baseline = Change")
            print(f"Baseline: X={BASELINE_X}, Y={BASELINE_Y}, Z={BASELINE_Z} (raw counts - from calibration 20250909_172256)")
            print(f"Impact threshold: {IMPACT_THRESHOLD} counts (change from baseline)")
            print("Sensor should be taped vertically for orientation test")
            print("Press CTRL+C to stop\n")
            
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping bridge...")
            self.running = False
        except Exception as e:
            self.logger.error(f"Bridge error: {e}")
            self.running = False
        finally:
            await self.cleanup()

async def main():
    bridge = FixedBridge()
    await bridge.run()

if __name__ == "__main__":
    asyncio.run(main())