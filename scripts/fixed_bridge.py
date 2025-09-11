#!/usr/bin/env python3
"""
Fixed Dev Bridge - Uses corrected BT50 parser with 1mg scale factor
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bleak import BleakClient, BleakScanner
import struct
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Setup dual logging - both to systemd and console log file
def setup_dual_logging():
    """Setup logging to both systemd journal and a dedicated console log file"""
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / 'logs' / 'console'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create console log file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    console_log_file = log_dir / f'bridge_console_{timestamp}.log'
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler (for systemd journal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    
    # File handler (for complete console log)
    file_handler = logging.FileHandler(console_log_file)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return console_log_file

# Initialize dual logging
console_log_path = setup_dual_logging()
logger = logging.getLogger(__name__)

# Import the corrected parser, shot detector, timing calibration, and enhanced impact detection
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    from impact_bridge.shot_detector import ShotDetector
    from impact_bridge.timing_calibration import RealTimeTimingCalibrator
    from impact_bridge.enhanced_impact_detection import EnhancedImpactDetector
    from impact_bridge.statistical_timing_calibration import statistical_calibrator
    from impact_bridge.dev_config import dev_config
    print("✓ Successfully imported corrected parse_5561 with 1mg scale factor")
    print("✓ Successfully imported ShotDetector")
    print("✓ Successfully imported RealTimeTimingCalibrator")
    print("✓ Successfully imported EnhancedImpactDetector")
    print("✓ Successfully imported Statistical Timing Calibrator")
    print("✓ Successfully imported development configuration")
    PARSER_AVAILABLE = True
    TIMING_AVAILABLE = True
    ENHANCED_DETECTION_AVAILABLE = True
    STATISTICAL_TIMING_AVAILABLE = True
    DEV_CONFIG_AVAILABLE = True
except Exception as e:
    print(f"⚠ Parser/Timing/Enhanced detection import failed: {e}")
    PARSER_AVAILABLE = False
    TIMING_AVAILABLE = False
    ENHANCED_DETECTION_AVAILABLE = False
    STATISTICAL_TIMING_AVAILABLE = False
    DEV_CONFIG_AVAILABLE = False
    dev_config = None
    statistical_calibrator = None

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
        # Use global dual logger
        self.logger = logger
        
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
        
        # AMG Timer start beep tracking for splits
        self.start_beep_time = None
        self.previous_shot_time = None
        self.impact_counter = 0
        self.shot_counter = 0
        self.last_projection = None
        self.current_string_number = 1  # Default string number
        
        # Shot detector (will be initialized after calibration)
        self.shot_detector = None
        
        # Timing calibrator for shot-impact correlation
        if TIMING_AVAILABLE:
            self.timing_calibrator = RealTimeTimingCalibrator(Path("latest_timing_calibration.json"))
            print("✓ Timing calibrator initialized with 526ms expected delay")
        else:
            self.timing_calibrator = None
            print("⚠ Timing calibrator not available")
        
        # Development configuration setup
        if DEV_CONFIG_AVAILABLE and dev_config:
            dev_config.print_config_summary()
            self.dev_config = dev_config
        else:
            self.dev_config = None
            self.logger.warning("Development configuration not available")
        
        # Enhanced impact detector with onset timing
        if ENHANCED_DETECTION_AVAILABLE:
            # Use development configuration for thresholds if available
            if self.dev_config and self.dev_config.is_enhanced_impact_enabled():
                peak_threshold = self.dev_config.get_peak_threshold()
                onset_threshold = self.dev_config.get_onset_threshold()
                lookback_samples = self.dev_config.get_lookback_samples()
                print(f"✓ Using development config for enhanced impact detection")
            else:
                peak_threshold = 150.0
                onset_threshold = 30.0
                lookback_samples = 10
                
            self.enhanced_impact_detector = EnhancedImpactDetector(
                threshold=peak_threshold,
                onset_threshold=onset_threshold,
                lookback_samples=lookback_samples
            )
            print("✓ Enhanced impact detector initialized (onset detection enabled)")
        else:
            self.enhanced_impact_detector = None
            print("⚠ Enhanced impact detector not available")
        
        # Ensure log directories exist
        Path("logs/main").mkdir(parents=True, exist_ok=True)
        Path("logs/debug").mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup comprehensive logging - both console and debug file"""
        timestamp = datetime.now()
        debug_file = f"logs/debug/bridge_debug_{timestamp.strftime('%Y%m%d_%H%M%S')}.log"
        
        # Create formatters with millisecond precision
        class MillisecondFormatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                ct = self.converter(record.created)
                ms = int((record.created - int(record.created)) * 1000)
                s = time.strftime('%H:%M:%S', ct)
                return f"{s}.{ms:03d}"
        
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
            
            # Log calibration results - separate completion from details
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
        
    def log_event(self, event_type, device, device_id, position, details, timestamp=None):
        """Log structured events"""
        if timestamp is None:
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
            
            # Log raw hex data in tabular format for pattern analysis
            if len(data) >= 14:
                hex_row = ' '.join(f'{b:02x}' for b in data[:14])
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                self.logger.info(f"AMG_HEX [{timestamp}] {frame_name:5s}: {hex_row}")
                # Also log byte positions for reference (only occasionally)
                if not hasattr(self, '_hex_header_logged') or not self._hex_header_logged:
                    self.logger.info(f"AMG_HEX [HEADER  ] BYTE#:  0  1  2  3  4  5  6  7  8  9 10 11 12 13")
                    self._hex_header_logged = True
            
            self.logger.debug(f"AMG frame type: {frame_header:02x}{frame_type:02x} = {frame_name}")
            
            # Handle START beep (frame type 0x05)
            if frame_header == 0x01 and frame_type == 0x05:
                self.start_beep_time = datetime.now()
                
                # Use byte 13 as string number (per official AMG project documentation)
                if len(data) >= 14:
                    self.current_string_number = data[13]  # Bytes 12-13 = series/batch (string number)
                    
                    # Extract additional timing data per AMG protocol
                    time_cs = (data[4] << 8) | data[5]  # Bytes 4-5: main time (centiseconds)
                    split_cs = (data[6] << 8) | data[7]  # Bytes 6-7: split time (centiseconds) 
                    first_cs = (data[8] << 8) | data[9]  # Bytes 8-9: first shot time (centiseconds)
                    
                    self.logger.info(f"📝 Status: Timer DC:1A - Start Beep for String #{self.current_string_number} at {self.start_beep_time.strftime('%H:%M:%S.%f')[:-3]}")
                    self.logger.info(f"📊 AMG Timing - Time: {time_cs/100:.2f}s, Split: {split_cs/100:.2f}s, First: {first_cs/100:.2f}s")
                else:
                    self.current_string_number = 1
                    self.logger.info(f"📝 Status: Timer DC:1A - Start Beep for String #{self.current_string_number} at {self.start_beep_time.strftime('%H:%M:%S.%f')[:-3]}")
                
                # Reset counters for new string
                self.impact_counter = 0
                self.previous_shot_time = None
                # Initialize shot counter for new string
                self.shot_counter = 0
                
                self.log_event("Status", "Timer", "DC:1A", "Bay 1", f"Start Beep for String #{self.current_string_number} at {self.start_beep_time.strftime('%H:%M:%S.%f')[:-3]}", self.start_beep_time)
            
            # Handle shots with split timing (frame type 0x03)
            elif frame_header == 0x01 and frame_type == 0x03 and len(data) >= 14:
                # Use byte 2 for shot number and byte 13 for string number (per AMG project)
                shot_number = data[2]
                string_number = data[13]  # Bytes 12-13 = series/batch (string number)
                reception_timestamp = datetime.now()
                
                # Extract timing data per AMG protocol
                time_cs = (data[4] << 8) | data[5]        # Bytes 4-5: main time (centiseconds)
                split_cs = (data[6] << 8) | data[7]       # Bytes 6-7: split time (centiseconds)
                first_cs = (data[8] << 8) | data[9]       # Bytes 8-9: first shot time (centiseconds)
                
                timer_split_seconds = time_cs / 100.0
                timer_split_ms = time_cs * 10
                split_seconds = split_cs / 100.0
                first_seconds = first_cs / 100.0
                
                # Calculate actual shot timestamp based on start beep + timer split
                actual_shot_timestamp = reception_timestamp
                if self.start_beep_time:
                    actual_shot_timestamp = self.start_beep_time + timedelta(milliseconds=timer_split_ms)
                
                # Calculate time from previous shot for split timing
                shot_split_seconds = 0.0
                if hasattr(self, 'previous_shot_time') and self.previous_shot_time:
                    shot_split_seconds = (actual_shot_timestamp - self.previous_shot_time).total_seconds()
                
                self.logger.info(f"🎯 String {string_number}, Shot #{shot_number} recorded at {actual_shot_timestamp.strftime('%H:%M:%S.%f')[:-3]} {{{timer_split_seconds:.2f}s(from start), {shot_split_seconds:.2f}s(from previous shot; split)}}")
                self.logger.info(f"📊 AMG Timing - Time: {timer_split_seconds:.2f}s, Split: {split_seconds:.2f}s, First: {first_seconds:.2f}s")
                
                # Store for next split calculation
                self.previous_shot_time = actual_shot_timestamp
                self.shot_counter = shot_number  # Track shot number within string
                
                # Log with actual timer split values
                shot_details = f"Shot #{shot_number}, timer split: {timer_split_seconds:.2f}s ({timer_split_ms:.0f}ms)"
                
                self.log_event("String", "Timer", "DC:1A", "Bay 1", shot_details, actual_shot_timestamp)
                
                # Add ACTUAL shot timestamp (not reception time) to timing calibrator
                if self.timing_calibrator:
                    self.timing_calibrator.add_shot_event(actual_shot_timestamp, shot_number, "DC:1A")
                    self.logger.debug(f"Shot #{shot_number} added to timing calibrator with timer split: {timer_split_seconds:.2f}s")
                
                # Generate statistical timing projection for impact
                if STATISTICAL_TIMING_AVAILABLE and statistical_calibrator:
                    projected_impact_time, timing_metadata = statistical_calibrator.project_impact_time(
                        actual_shot_timestamp, confidence_level="median"
                    )
                    
                    # Log projected impact timing with confidence intervals
                    confidence_range = timing_metadata["confidence_intervals"]["68_percent"]
                    # Store projection metadata for impact correlation
                    self.last_projection = {
                        'shot_number': shot_number,
                        'shot_time': actual_shot_timestamp,
                        'projected_time': projected_impact_time,
                        'metadata': timing_metadata
                    }
                    
                    # Log projection details to debug
                    self.logger.debug(f"Statistical projection metadata: {json.dumps(timing_metadata, indent=2)}")
                    
                    # Add projection event to logs
                    projection_details = (f"Impact projected at {projected_impact_time.strftime('%H:%M:%S.%f')[:-3]}, "
                                        f"offset: {timing_metadata['offset_used_ms']}ms, "
                                        f"uncertainty: ±{timing_metadata['uncertainty_ms']}ms")
                    self.log_event("Projection", "Statistical", "BT50", "Bay 1", projection_details, projected_impact_time)
            
            # Handle STOP frame (frame type 0x08) 
            elif frame_header == 0x01 and frame_type == 0x08:
                reception_timestamp = datetime.now()
                
                # Extract string number and timing data per AMG protocol
                if len(data) >= 14:
                    string_number = data[13]  # Bytes 12-13 = series/batch (string number)
                    time_cs = (data[4] << 8) | data[5]        # Bytes 4-5: main time (centiseconds)
                    split_cs = (data[6] << 8) | data[7]       # Bytes 6-7: split time (centiseconds)
                    first_cs = (data[8] << 8) | data[9]       # Bytes 8-9: first shot time (centiseconds)
                    
                    timer_seconds = time_cs / 100.0
                    split_seconds = split_cs / 100.0
                    first_seconds = first_cs / 100.0
                else:
                    string_number = getattr(self, 'current_string_number', 1)
                    timer_seconds = 0
                    split_seconds = 0
                    first_seconds = 0
                
                # Calculate total string time if start beep available
                total_info = ""
                if self.start_beep_time:
                    total_ms = (reception_timestamp - self.start_beep_time).total_seconds() * 1000
                    total_info = f" (total: {total_ms:.0f}ms)"
                
                self.logger.info(f"📝 Status: Timer DC:1A - String #{string_number} Stop{total_info}")
                if len(data) >= 14:
                    self.logger.info(f"📊 AMG Final - Time: {timer_seconds:.2f}s, Split: {split_seconds:.2f}s, First: {first_seconds:.2f}s")
                
                stop_details = f"String #{current_string} Stop"
                if self.start_beep_time:
                    stop_details += f", total time: {total_ms:.0f}ms"
                
                # Use reception timestamp for STOP since no timer data available
                self.log_event("Status", "Timer", "DC:1A", "Bay 1", stop_details, reception_timestamp)
                
                # Reset for next string
                self.start_beep_time = None
                self.impact_counter = 0
                self.shot_counter = 0
                self.previous_shot_time = None
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
                
                # Enhanced sample logging for impact analysis (development mode)
                current_time = datetime.now()
                
                # Development mode sample logging
                if self.dev_config and self.dev_config.is_sample_logging_enabled():
                    if self.dev_config.should_log_all_samples() or (self.dev_config.should_log_impact_samples() and magnitude_corrected > 25.0):
                        self.logger.debug(f"BT50 sample: {current_time.strftime('%H:%M:%S.%f')[:-3]} vx_raw={vx_raw}, vy_raw={vy_raw}, vz_raw={vz_raw}, magnitude={magnitude_corrected:.1f}")
                elif not self.dev_config:  # Fallback if no dev config
                    self.logger.debug(f"BT50 sample: {current_time.strftime('%H:%M:%S.%f')[:-3]} vx_raw={vx_raw}, vy_raw={vy_raw}, vz_raw={vz_raw}, magnitude={magnitude_corrected:.1f}")
                
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
                
                # Enhanced impact detection with onset timing
                if self.enhanced_impact_detector:
                    timestamp = datetime.now()
                    impact_event = self.enhanced_impact_detector.process_sample(
                        timestamp=timestamp,
                        raw_values=[vx_raw, vy_raw, vz_raw],
                        corrected_values=[vx_corrected, vy_corrected, vz_corrected],
                        magnitude=magnitude_corrected
                    )
                    
                    if impact_event:
                        # Calculate timing from start and from shot
                        time_from_start = 0.0
                        time_from_shot = 0.0
                        impact_number = getattr(self, 'impact_counter', 0) + 1
                        setattr(self, 'impact_counter', impact_number)
                        
                        if self.start_beep_time:
                            time_from_start = (impact_event.onset_timestamp - self.start_beep_time).total_seconds()
                        
                        if hasattr(self, 'last_projection') and self.last_projection:
                            time_from_shot = (impact_event.onset_timestamp - self.last_projection['shot_time']).total_seconds()
                            shot_number = self.last_projection['shot_number']
                            confidence_range = self.last_projection['metadata']['confidence_intervals']['68_percent']
                            uncertainty = self.last_projection['metadata']['uncertainty_ms']
                        else:
                            shot_number = "?"
                            confidence_range = "N/A"
                            uncertainty = 94
                        
                        # Use extracted string number or default to 1
                        current_string = getattr(self, 'current_string_number', 1)
                        
                        # Consolidated impact logging
                        self.logger.info(f"💥String {current_string}, Impact #{impact_number}: {time_from_start:.2f}s(from start), {time_from_shot:.3f}s(from shot)")
                        
                        # Extract additional details from impact event
                        onset_to_peak_ms = getattr(impact_event, '_onset_to_peak_ms', 0)
                        duration_ms = getattr(impact_event, '_duration_ms', impact_event.duration_ms)
                        sample_count = getattr(impact_event, '_sample_count', 0)
                        confidence = getattr(impact_event, '_confidence', impact_event.confidence)
                        
                        self.logger.info(f"📊String {current_string}, Impact #{impact_number}: {{Details Onset: {impact_event.onset_timestamp.strftime('%H:%M:%S.%f')[:-3]} ({impact_event.onset_magnitude:.1f}g), Peak: {impact_event.peak_timestamp.strftime('%H:%M:%S.%f')[:-3]} ({impact_event.peak_magnitude:.1f}g), Onset→Peak: {onset_to_peak_ms:.1f}ms, Duration: {duration_ms:.1f}ms, Samples: {sample_count}, Confidence: {confidence:.2f}, Offset (±{uncertainty:.0f}ms, 68% CI: {confidence_range})}}")
                        
                        # Log event to structured logs
                        self.log_event("Impact", "Sensor", "12:E3", "Plate 1", 
                                     f"Enhanced impact: onset {impact_event.onset_magnitude:.1f}g → peak {impact_event.peak_magnitude:.1f}g, "
                                     f"duration {duration_ms:.1f}ms, confidence {confidence:.2f}")
                        
                        # Add ONSET timestamp to timing calibrator (key improvement!)
                        if self.timing_calibrator:
                            self.timing_calibrator.add_impact_event(
                                timestamp=impact_event.onset_timestamp,  # Use onset, not peak!
                                magnitude=impact_event.peak_magnitude,
                                device_id="12:E3",
                                raw_value=vx_raw
                            )
                            self.logger.debug(f"Impact onset {impact_event.onset_magnitude:.1f}g added to timing calibrator")
                        
                        # Statistical timing analysis for this impact
                        if STATISTICAL_TIMING_AVAILABLE and statistical_calibrator:
                            # Check if we have recent shots to correlate with
                            recent_shots = []
                            if hasattr(self, 'timing_calibrator') and self.timing_calibrator:
                                recent_shots = getattr(self.timing_calibrator, 'shot_events', [])
                                # Get shots from last 5 seconds
                                cutoff_time = impact_event.onset_timestamp - timedelta(seconds=5)
                                recent_shots = [shot for shot in recent_shots if shot['timestamp'] > cutoff_time]
                            
                            # Analyze timing accuracy for most recent shot if available
                            if recent_shots:
                                latest_shot = max(recent_shots, key=lambda x: x['timestamp'])
                                timing_analysis = statistical_calibrator.analyze_timing_accuracy(
                                    amg_time=latest_shot['timestamp'],
                                    actual_impact_time=impact_event.onset_timestamp
                                )
                                
                                # Log statistical analysis
                                confidence_level = timing_analysis['confidence_level_achieved']
                                prediction_error = timing_analysis['prediction_error_ms']
                                actual_delay = timing_analysis['actual_delay_ms']
                                
                                # Timing analysis will be included in the consolidated impact log above
                                
                                # Log detailed analysis to debug
                                self.logger.debug(f"Statistical timing analysis: {json.dumps(timing_analysis, indent=2)}")
                                
                                # Add analysis event to logs
                                analysis_details = (f"Actual delay: {actual_delay:.0f}ms, "
                                                  f"prediction error: {prediction_error:+.0f}ms, "
                                                  f"confidence: {confidence_level}")
                                self.log_event("Analysis", "Statistical", "Timing", "Correlation", 
                                             analysis_details, impact_event.onset_timestamp)
                
                # Fallback: Legacy impact detection (if enhanced detection not available)
                elif magnitude_corrected > IMPACT_THRESHOLD:
                    timestamp = datetime.now()
                    
                    # Log clean impact message with corrected values only
                    self.logger.info(f"📝 Legacy Impact: Sensor 12:E3 Mag = {magnitude_corrected:.0f} [{vx_corrected:.0f}, {vy_corrected:.0f}, {vz_corrected:.0f}] at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
                    self.log_event("Impact", "Sensor", "12:E3", "Plate 1", 
                                 f"Legacy impact: Mag={magnitude_corrected:.1f} corrected[{vx_corrected:.1f},{vy_corrected:.1f},{vz_corrected:.1f}] (threshold: {IMPACT_THRESHOLD})")
                    
                    # Add to timing calibrator for correlation (using peak timestamp)
                    if self.timing_calibrator:
                        self.timing_calibrator.add_impact_event(timestamp, magnitude_corrected, "12:E3", vx_raw)
                        self.logger.debug(f"Legacy impact {magnitude_corrected:.1f}g added to timing calibrator")
                
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
        
        # Final ready status - only if both devices connected successfully
        if (self.amg_client and self.amg_client.is_connected and 
            self.bt50_client and self.bt50_client.is_connected and 
            self.calibration_complete):
            self.logger.info("-----------------------------🎯Bridge ready for String🎯-----------------------------")
            self.log_event("Status", "Bridge", "MCU1", "Bay 1", "Bridge ready for String - All systems operational")

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
        
        # Report timing correlation statistics
        if self.timing_calibrator:
            timing_stats = self.timing_calibrator.get_correlation_stats()
            self.logger.info("=== TIMING CORRELATION STATISTICS ===")
            self.logger.info(f"Total correlated pairs: {timing_stats['total_pairs']}")
            self.logger.info(f"Correlation success rate: {timing_stats['success_rate']*100:.1f}%")
            self.logger.info(f"Average timing delay: {timing_stats['avg_delay_ms']}ms")
            self.logger.info(f"Expected timing delay: {timing_stats['expected_delay_ms']}ms")
            self.logger.info(f"Calibration status: {timing_stats['calibration_status']}")
            if timing_stats['pending_shots'] > 0 or timing_stats['pending_impacts'] > 0:
                self.logger.info(f"Pending events: {timing_stats['pending_shots']} shots, {timing_stats['pending_impacts']} impacts")
            self.logger.info("=====================================")
        else:
            self.logger.info("Timing calibrator not initialized - no correlation statistics")
        
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
        
        # Announce startup and log file location
        self.logger.info("🎯 TinTown Bridge v2.0 - Starting...")
        self.logger.info(f"📋 Complete console log: {console_log_path}")
        self.logger.info("💡 Use 'tail -f' on this log file to see ALL events including AMG beeps")
        
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