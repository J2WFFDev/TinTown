#!/usr/bin/env python3
"""
Fixed Dev Bridge - Uses corrected BT50 pars    def setup_logging(self):
        "        # Create formatters
        console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Add millisecond precision to console formatter
        original_formatTime = console_formatter.formatTime
        def formatTime_ms(record, datefmt=None):
            ct = time.localtime(record.created)
            ms = int((record.created - int(record.created)) * 1000)
            s = time.strftime('%H:%M:%S', ct)
            return f"{s}.{ms:03d}"
        console_formatter.formatTime = formatTime_msetup comprehensive logging - both console and debug file"""
        timestamp = datetime.now()
        debug_file = f"logs/debug/bridge_debug_{timestamp.strftime('%Y%m%d_%H%M%S')}.log"
        
        # Custom formatter for millisecond precision
        class MillisecondFormatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                ct = self.converter(record.created)
                ms = int((record.created - int(record.created)) * 1000)
                s = time.strftime('%H:%M:%S', ct)
                return f"{s}.{ms:03d}"
        
        # Create formatters
        console_formatter = MillisecondFormatter('[%(asctime)s] %(levelname)s: %(message)s')
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
        self.logger.info(f"Debug logging enabled: {debug_file}")1mg scale factor
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

# Import the corrected parser and shot detector
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    from impact_bridge.shot_detector import ShotDetector
    print("✓ Successfully imported corrected parse_5561 with 1mg scale factor")
    print("✓ Successfully imported ShotDetector")
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

# Impact threshold - Raw count changes (based on stationary variation analysis)
# Normal variation: ~57 counts, so threshold = 3x normal variation
IMPACT_THRESHOLD = 150  # Raw counts - Detect changes > 150 counts from baseline

# Calibration settings
CALIBRATION_SAMPLES = 100  # Number of samples to collect for baseline calibration

class FixedBridge:
    def __init__(self):
        self.amg_client = None
        self.bt50_client = None
        self.running = False
        self.session_id = int(time.time())
        
        # Dynamic baseline values (set during startup calibration)
        self.baseline_x = None
        self.baseline_y = None  
        self.baseline_z = None
        self.calibration_complete = False
        
        # Calibration data collection
        self.calibration_samples = []
        self.collecting_calibration = False
        
        # Shot detector (will be initialized after calibration)
        self.shot_detector = None
        
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
        console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S.%f')
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
    
    async def calibration_notification_handler(self, characteristic, data):
        """Collect calibration samples during startup"""
        if not self.collecting_calibration:
            return
            
        # For calibration, parse data even if shot_detector import failed
        try:
            if PARSER_AVAILABLE:
                # Use the imported parser
                result = parse_5561(data)
                if result and result['samples']:
                    # Collect raw values from all samples in this notification
                    for sample in result['samples']:
                        vx_raw, vy_raw, vz_raw = sample['raw']
                        self.calibration_samples.append({
                            'vx_raw': vx_raw,
                            'vy_raw': vy_raw,
                            'vz_raw': vz_raw,
                            'timestamp': time.time()
                        })
                        
                        if len(self.calibration_samples) >= CALIBRATION_SAMPLES:
                            self.collecting_calibration = False
                            break
            else:
                # Fallback: manually parse WitMotion 5561 frames for calibration
                if len(data) >= 44 and data[0] == 0x55 and data[1] == 0x61:
                    # Extract first sample from 5561 frame
                    vx_raw = struct.unpack('<h', data[14:16])[0]
                    vy_raw = struct.unpack('<h', data[16:18])[0] 
                    vz_raw = struct.unpack('<h', data[18:20])[0]
                    
                    self.calibration_samples.append({
                        'vx_raw': vx_raw,
                        'vy_raw': vy_raw,
                        'vz_raw': vz_raw,
                        'timestamp': time.time()
                    })
                    
                    if len(self.calibration_samples) >= CALIBRATION_SAMPLES:
                        self.collecting_calibration = False
                        
        except Exception as e:
            self.logger.error(f"Calibration data collection failed: {e}")
    
    async def perform_startup_calibration(self):
        """Perform automatic startup calibration to establish fresh zero baseline"""
        self.logger.info("🎯 Starting automatic calibration...")
        print("🎯 Performing startup calibration...")
        print("📋 Please ensure sensor is STATIONARY during calibration")
        print("⏱️  Collecting 100+ samples for baseline establishment...")
        
        # Reset calibration state
        self.calibration_samples = []
        self.collecting_calibration = True
        
        # Start calibration notifications
        try:
            await self.bt50_client.start_notify(BT50_SENSOR_UUID, self.calibration_notification_handler)
            
            # Wait for calibration to complete
            start_time = time.time()
            timeout = 30  # 30 second timeout
            
            while self.collecting_calibration:
                await asyncio.sleep(0.1)
                print(f"\r📊 Collected {len(self.calibration_samples)}/{CALIBRATION_SAMPLES} samples...", end='', flush=True)
                
                if time.time() - start_time > timeout:
                    self.logger.error("Calibration timeout - insufficient data")
                    print(f"\n❌ Calibration timeout after {timeout}s")
                    return False
            
            print()  # New line after progress
            
            # Process calibration data
            if len(self.calibration_samples) < CALIBRATION_SAMPLES:
                self.logger.error(f"Insufficient calibration samples: {len(self.calibration_samples)}")
                print(f"❌ Insufficient samples collected: {len(self.calibration_samples)}")
                return False
                
            # Calculate baseline averages
            vx_values = [s['vx_raw'] for s in self.calibration_samples]
            vy_values = [s['vy_raw'] for s in self.calibration_samples]
            vz_values = [s['vz_raw'] for s in self.calibration_samples]
            
            self.baseline_x = int(sum(vx_values) / len(vx_values))
            self.baseline_y = int(sum(vy_values) / len(vy_values))
            self.baseline_z = int(sum(vz_values) / len(vz_values))
            
            # Calculate noise characteristics
            import statistics
            noise_x = statistics.stdev(vx_values) if len(set(vx_values)) > 1 else 0
            noise_y = statistics.stdev(vy_values) if len(set(vy_values)) > 1 else 0
            noise_z = statistics.stdev(vz_values) if len(set(vz_values)) > 1 else 0
            
            # Initialize shot detector with calibrated baseline (if available)
            if PARSER_AVAILABLE:
                self.shot_detector = ShotDetector(
                    baseline_x=self.baseline_x,
                    threshold=IMPACT_THRESHOLD,
                    min_duration=6,
                    max_duration=11,
                    min_interval_seconds=1.0
                )
            else:
                self.logger.warning("Shot detector not available - impact detection disabled")
                self.shot_detector = None
            
            self.calibration_complete = True
            
            # Log calibration results with proper separation
            self.logger.info(f"Calibration complete: X={self.baseline_x}, Y={self.baseline_y}, Z={self.baseline_z}")
            self.logger.info("✅ Calibration completed successfully!")
            self.logger.info(f"📊 Baseline established: X={self.baseline_x}, Y={self.baseline_y}, Z={self.baseline_z}")
            self.logger.info(f"📈 Noise levels: X=±{noise_x:.1f}, Y=±{noise_y:.1f}, Z=±{noise_z:.1f}")
            self.logger.info(f"🎯 Impact threshold: {IMPACT_THRESHOLD} counts from baseline")
            
            # Log calibration event
            self.log_event("Calibration", "Sensor", "12:E3", "Plate 1", 
                         f"Baseline established: X={self.baseline_x}, Y={self.baseline_y}, Z={self.baseline_z} "
                         f"(noise: ±{noise_x:.1f}, ±{noise_y:.1f}, ±{noise_z:.1f})")
            
            # Switch back to normal notification handler
            await self.bt50_client.stop_notify(BT50_SENSOR_UUID)
            await self.bt50_client.start_notify(BT50_SENSOR_UUID, self.bt50_notification_handler)
            
            # Show listening status
            self.logger.info("📝 Status: Sensor 12:E3 - Listening")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            print(f"❌ Calibration failed: {e}")
            return False
        
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
            
        # Only print detailed log events to debug level (not console)
        self.logger.debug(f"Event logged: {event_type}: {device} {device_id} - {details}")

    async def amg_notification_handler(self, characteristic, data):
        """Handle AMG timer notifications with complete frame capture"""
        hex_data = data.hex()
        
        # Log raw hex to debug only
        self.logger.debug(f"AMG notification: {hex_data}")
        self.logger.debug(f"AMG raw bytes: {list(data)} (length: {len(data)} bytes)")
        
        # AMG frames are typically 14 bytes, not 32
        expected_frame_size = 14
        if len(data) != expected_frame_size:
            self.logger.debug(f"AMG frame size: {len(data)} bytes (expected: {expected_frame_size})")
        
        # Enhanced frame type analysis
        if len(data) >= 2:
            frame_header = data[0]
            frame_type = data[1]
            frame_type_names = {0x03: "SHOT", 0x05: "START", 0x08: "STOP"}
            frame_name = frame_type_names.get(frame_type, f"UNKNOWN({frame_type:02x})")
            
            self.logger.debug(f"AMG frame type: {frame_header:02x}{frame_type:02x} = {frame_name}")
            
            # Only log shots for frame type 0x03
            if frame_header == 0x01 and frame_type == 0x03 and len(data) >= 3:
                shot_number = data[2]
                self.logger.info(f"📝 String: Timer DC:1A - Shot #{shot_number}")
                self.log_event("String", "Timer", "DC:1A", "Bay 1", f"Shot #{shot_number}")
            elif frame_header == 0x01 and frame_type == 0x05:
                self.logger.info("📝 Status: Timer DC:1A - Start")
            elif frame_header == 0x01 and frame_type == 0x08:
                self.logger.info("📝 Status: Timer DC:1A - Stop")
            else:
                self.logger.debug(f"AMG {frame_name} frame (not logged to console)")
        else:
            self.logger.warning(f"AMG frame too short for type analysis: {len(data)} bytes")

    async def bt50_notification_handler(self, characteristic, data):
        """Handle BT50 sensor notifications with RAW VALUES and shot detection"""
        hex_data = data.hex()
        
        # Log raw data to debug only
        self.logger.debug(f"BT50 raw: {hex_data[:64]}...")
        
        if not PARSER_AVAILABLE:
            self.logger.warning("Parser not available, skipping impact detection")
            return
            
        if not self.calibration_complete:
            self.logger.warning("Calibration not complete, skipping detection")
            return
            
        # Use parser but extract raw integer values directly
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Get RAW INTEGER values directly (no scale factor applied)
                sample = result['samples'][0]  # First sample
                vx_raw, vy_raw, vz_raw = sample['raw']  # Raw int16 values
                
                # Apply dynamic baseline subtraction to raw values
                vx_corrected = vx_raw - self.baseline_x
                vy_corrected = vy_raw - self.baseline_y
                vz_corrected = vz_raw - self.baseline_z
                
                # Calculate corrected magnitude from raw values
                magnitude_corrected = (vx_corrected**2 + vy_corrected**2 + vz_corrected**2)**0.5
                magnitude_raw = (vx_raw**2 + vy_raw**2 + vz_raw**2)**0.5
                
                # Log detailed RAW data to debug only
                self.logger.debug(f"BT50 RAW: [{vx_raw},{vy_raw},{vz_raw}] Corrected[{vx_corrected:.1f},{vy_corrected:.1f},{vz_corrected:.1f}] Mag={magnitude_corrected:.1f}")
                
                # Show processing status every 50 samples (debug)
                if hasattr(self, '_sample_count'):
                    self._sample_count += 1
                else:
                    self._sample_count = 1
                    
                if self._sample_count % 50 == 0:
                    self.logger.debug(f"BT50 processing: sample #{self._sample_count}, current magnitude: {magnitude_corrected:.1f}")
                
                # Run shot detection on X-axis raw values (if available)
                if self.shot_detector:
                    shot_event = self.shot_detector.process_sample(vx_raw)
                    if shot_event:
                        # Shot detected! Log detailed information
                        self.logger.info(f"🎯 SHOT DETECTED #{shot_event.shot_id}: duration {shot_event.duration_ms:.0f}ms, deviation {shot_event.max_deviation} counts")
                        
                        self.log_event("Shot", "Sensor", "12:E3", "Plate 1", 
                                     f"Shot #{shot_event.shot_id}: duration {shot_event.duration_samples} samples ({shot_event.duration_ms:.0f}ms), "
                                     f"max deviation {shot_event.max_deviation} counts, X-range [{min(shot_event.x_values)}-{max(shot_event.x_values)}]")
                
                # Check for impact using corrected magnitude (legacy detection)
                if magnitude_corrected > IMPACT_THRESHOLD:
                    # Log clean impact message with corrected values only
                    self.logger.info(f"📝 Impact Detected: Sensor 12:E3 Mag = {magnitude_corrected:.0f} [{vx_corrected:.0f}, {vy_corrected:.0f}, {vz_corrected:.0f}]")
                    self.log_event("Impact", "Sensor", "12:E3", "Plate 1", 
                                 f"Impact detected: Mag={magnitude_corrected:.1f} corrected[{vx_corrected:.1f},{vy_corrected:.1f},{vz_corrected:.1f}] (threshold: {IMPACT_THRESHOLD})")
                
        except Exception as e:
            self.logger.error(f"BT50 parsing failed: {e}")

    async def reset_ble(self):
        """Reset BLE connections before starting"""
        self.logger.info("🔄 Starting BLE reset")
        
        try:
            import subprocess
            
            # Simple disconnect commands
            devices = [BT50_SENSOR_MAC, AMG_TIMER_MAC]
            for mac in devices:
                try:
                    subprocess.run(['bluetoothctl', 'disconnect', mac], 
                                  capture_output=True, text=True, timeout=3)
                    self.logger.debug(f"Attempted disconnect of {mac}")
                except Exception as e:
                    self.logger.debug(f"Disconnect {mac} failed: {e}")
            
            # Quick adapter cycle
            try:
                subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], 
                             capture_output=True, timeout=2)
                await asyncio.sleep(0.5)
                subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], 
                             capture_output=True, timeout=2)
                self.logger.info("🔧 Reset Bluetooth adapter")
            except Exception as e:
                self.logger.warning(f"Adapter reset failed: {e}")
            
            # Brief wait for stabilization
            await asyncio.sleep(1)
            self.logger.info("✓ BLE reset complete")
            
        except Exception as e:
            self.logger.error(f"BLE reset failed: {e}")
            print(f"⚠ BLE reset failed: {e}")

    async def connect_devices(self):
        """Connect to both devices"""
        # Perform automatic BLE reset first
        await self.reset_ble()
        
        self.logger.info("📝 Status: Bridge MCU1 - Bridge Initialized")
        self.log_event("Status", "Bridge", "MCU1", "Bay 1", "Bridge Initialized")
        
        try:
            # Connect AMG Timer
            self.logger.info("Connecting to AMG timer...")
            self.amg_client = BleakClient(AMG_TIMER_MAC)
            await self.amg_client.connect()
            self.logger.info("📝 Status: Timer DC:1A - Connected")
            self.log_event("Status", "Timer", "DC:1A", "Bay 1", "Connected")
            
            # Enable notifications
            await self.amg_client.start_notify(AMG_TIMER_UUID, self.amg_notification_handler)
            self.logger.info("AMG timer and shot notifications enabled")
            
        except Exception as e:
            self.logger.error(f"AMG timer connection failed: {e}")
            
        try:
            # Connect BT50 Sensor
            self.logger.info("Connecting to BT50 sensor...")
            self.bt50_client = BleakClient(BT50_SENSOR_MAC)
            await self.bt50_client.connect()
            self.logger.info("📝 Status: Sensor 12:E3 - Connected")
            self.log_event("Status", "Sensor", "12:E3", "Plate 1", "Connected")
            
            # Wait for connection to stabilize before calibration
            await asyncio.sleep(1.0)
            
            # Perform startup calibration
            calibration_success = await self.perform_startup_calibration()
            if not calibration_success:
                self.logger.error("Startup calibration failed - cannot proceed")
                print("❌ Bridge startup failed due to calibration error")
                return
            
            # Calibration handles the listening status message
            self.logger.info("BT50 sensor and impact notifications enabled")
            
        except Exception as e:
            self.logger.error(f"BT50 sensor connection failed: {e}")

    async def cleanup(self):
        """Proper cleanup of BLE connections"""
        self.logger.info("Cleaning up connections...")
        
        # Log shot detection statistics
        if self.shot_detector:
            stats = self.shot_detector.get_stats()
            self.logger.info(f"Shot detection summary: {stats['total_shots']} shots detected "
                            f"from {stats['total_samples']} samples ({stats['shots_per_minute']:.1f}/min)")
            
            recent_shots = self.shot_detector.get_recent_shots()
            if recent_shots:
                self.logger.info("Recent shots:")
                for shot in recent_shots:
                    self.logger.info(f"  Shot #{shot.shot_id}: {shot.timestamp_str}, "
                                   f"{shot.duration_samples} samples, {shot.max_deviation} counts")
        else:
            self.logger.info("Shot detector not initialized - no statistics available")
        
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
            
            print("\n=== AUTOMATIC CALIBRATION BRIDGE WITH SHOT DETECTION ===")
            print("✨ Dynamic baseline calibration - establishes fresh zero on every startup")
            print("🎯 Shot Detection: 150 count threshold, 6-11 sample duration, 1s interval")
            print(f"📊 Current baseline: X={self.baseline_x}, Y={self.baseline_y}, Z={self.baseline_z} (auto-calibrated)")
            print(f"⚡ Impact threshold: {IMPACT_THRESHOLD} counts from dynamic baseline")
            print("🔄 Baseline automatically corrects for any sensor orientation")
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