#!/usr/bin/env python3
"""
TinTown Bridge Integration with Timing Calibration

This script shows how to integrate the timing calibration system into 
the existing fixed_bridge.py implementation.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import the new timing calibration system
from src.impact_bridge.timing_calibration import RealTimeTimingCalibrator

logger = logging.getLogger(__name__)

class TimingEnhancedBridge:
    """Enhanced bridge with integrated timing calibration"""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("config/config.yaml")
        self.calibration_file = Path("timing_calibration.json")
        
        # Initialize timing calibrator with discovered parameters
        self.timing_calibrator = RealTimeTimingCalibrator(self.calibration_file)
        
        # Bridge state
        self.is_running = False
        self.device_states = {}
        self.shot_count = 0
        
        # Performance tracking
        self.total_shots = 0
        self.total_impacts = 0
        self.correlated_pairs = 0
        
        logger.info("Timing-enhanced bridge initialized")
        self._log_calibration_status()
    
    def _log_calibration_status(self):
        """Log current calibration parameters"""
        cal = self.timing_calibrator.calibration
        logger.info("=== TIMING CALIBRATION STATUS ===")
        logger.info(f"Expected delay: {cal.expected_delay_ms}ms")
        logger.info(f"Correlation window: {cal.correlation_window_ms}ms")
        logger.info(f"Delay tolerance: ±{cal.delay_tolerance_ms}ms")
        logger.info(f"Minimum magnitude: {cal.minimum_magnitude}g")
        logger.info(f"Learning rate: {cal.learning_rate}")
        logger.info(f"Sample count: {cal.sample_count}")
        logger.info("==================================")
    
    async def handle_amg_frame(self, device_id: str, frame_data: bytes, timestamp: datetime = None):
        """Enhanced AMG frame handler with timing correlation"""
        timestamp = timestamp or datetime.now()
        
        try:
            # Parse AMG frame (your existing logic)
            frame_type = int.from_bytes(frame_data[2:4], byteorder='little')
            
            if frame_type == 0x0103:  # SHOT frame
                self.shot_count += 1
                self.total_shots += 1
                
                # Extract shot number (your existing logic)
                shot_number = self.shot_count  # Or parse from frame if available
                
                logger.info(f"AMG SHOT #{shot_number} detected at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
                
                # Add to timing calibrator for correlation
                self.timing_calibrator.add_shot_event(timestamp, shot_number, device_id)
                
                # Log shot to files (your existing logic)
                await self._log_shot_event(shot_number, device_id, timestamp)
                
                # Check for immediate correlation status
                await self._check_correlation_health()
                
            elif frame_type == 0x0101:  # START frame
                logger.debug("AMG START frame (not counting as shot)")
                self.shot_count = 0  # Reset shot counter
                
            elif frame_type == 0x0104:  # STOP frame  
                logger.debug("AMG STOP frame (not counting as shot)")
                await self._log_session_summary()
                
        except Exception as e:
            logger.error(f"Error processing AMG frame: {e}")
    
    async def handle_bt50_data(self, device_id: str, raw_data: list, corrected_data: list, 
                              magnitude: float, timestamp: datetime = None):
        """Enhanced BT50 data handler with timing correlation"""
        timestamp = timestamp or datetime.now()
        
        try:
            self.total_impacts += 1
            
            # Log raw sensor data (your existing logic)
            logger.debug(f"BT50 RAW: {raw_data} Corrected: {corrected_data} Mag={magnitude:.1f}")
            
            # Check if this qualifies as an impact event
            impact_threshold = 150.0  # Your existing threshold
            
            if magnitude >= impact_threshold:
                logger.info(f"BT50 Impact detected: {magnitude:.1f}g at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
                
                # Add to timing calibrator for correlation
                self.timing_calibrator.add_impact_event(
                    timestamp=timestamp,
                    magnitude=magnitude, 
                    device_id=device_id,
                    raw_value=raw_data[0] if raw_data else magnitude
                )
                
                # Log impact to files (your existing logic)
                await self._log_impact_event(magnitude, device_id, timestamp, raw_data)
            
        except Exception as e:
            logger.error(f"Error processing BT50 data: {e}")
    
    async def _log_shot_event(self, shot_number: int, device_id: str, timestamp: datetime):
        """Log shot event to files (your existing CSV/NDJSON logging)"""
        # CSV format
        csv_data = {
            "datetime": timestamp.strftime("%m/%d/%y %I:%M:%S.%f%p")[:-4] + timestamp.strftime("%p").lower(),
            "type": "Shot",
            "device": "Timer", 
            "device_id": device_id,
            "device_position": "Bay 1",
            "details": f"Shot #{shot_number}",
            "timestamp_iso": timestamp.isoformat(),
            "seq": shot_number
        }
        
        # NDJSON format
        ndjson_data = {
            **csv_data,
            "shot_data": {
                "shot_number": shot_number,
                "device_id": device_id
            }
        }
        
        # Your existing file writing logic here
        logger.debug(f"Shot event logged: {json.dumps(ndjson_data)}")
    
    async def _log_impact_event(self, magnitude: float, device_id: str, timestamp: datetime, raw_data: list):
        """Log impact event to files (your existing CSV/NDJSON logging)"""
        # CSV format  
        csv_data = {
            "datetime": timestamp.strftime("%m/%d/%y %I:%M:%S.%f%p")[:-4] + timestamp.strftime("%p").lower(),
            "type": "Impact",
            "device": "Sensor",
            "device_id": device_id, 
            "device_position": "Plate 1",
            "details": f"Impact detected: {magnitude:.1f} (raw: {raw_data[0] if raw_data else 'N/A'}, threshold: 150)",
            "timestamp_iso": timestamp.isoformat(),
            "seq": self.total_impacts
        }
        
        # NDJSON format
        ndjson_data = {
            **csv_data,
            "impact_data": {
                "magnitude": magnitude,
                "raw_values": raw_data,
                "device_id": device_id
            }
        }
        
        # Your existing file writing logic here
        logger.debug(f"Impact event logged: {json.dumps(ndjson_data)}")
    
    async def _check_correlation_health(self):
        """Check and log timing correlation health"""
        stats = self.timing_calibrator.get_correlation_stats()
        
        # Log correlation success rate
        if stats['total_pairs'] > 0:
            success_rate = stats['success_rate'] * 100
            avg_delay = stats['avg_delay_ms']
            expected_delay = stats['expected_delay_ms']
            
            if success_rate >= 80:
                logger.info(f"✅ Correlation health: {success_rate:.1f}% success, "
                           f"avg delay {avg_delay}ms (expected {expected_delay}ms)")
            elif success_rate >= 50:
                logger.warning(f"⚠️ Correlation health: {success_rate:.1f}% success, "
                              f"avg delay {avg_delay}ms (expected {expected_delay}ms)")
            else:
                logger.error(f"❌ Correlation health: {success_rate:.1f}% success, "
                            f"timing may be misaligned!")
    
    async def _log_session_summary(self):
        """Log session summary with timing correlation statistics"""
        stats = self.timing_calibrator.get_correlation_stats()
        
        logger.info("=== SESSION SUMMARY ===")
        logger.info(f"Total shots fired: {self.total_shots}")
        logger.info(f"Total impacts detected: {self.total_impacts}")
        logger.info(f"Correlated pairs: {stats['total_pairs']}")
        logger.info(f"Correlation success rate: {stats['success_rate'] * 100:.1f}%")
        logger.info(f"Average timing delay: {stats['avg_delay_ms']}ms")
        logger.info(f"Expected timing delay: {stats['expected_delay_ms']}ms")
        logger.info(f"Calibration status: {stats['calibration_status']}")
        logger.info("=======================")
    
    async def get_bridge_status(self) -> Dict[str, Any]:
        """Get comprehensive bridge status including timing"""
        timing_stats = self.timing_calibrator.get_correlation_stats()
        
        return {
            "bridge_status": "running" if self.is_running else "stopped",
            "shot_count": self.total_shots,
            "impact_count": self.total_impacts,
            "device_states": self.device_states,
            "timing_calibration": {
                "correlation_pairs": timing_stats['total_pairs'],
                "success_rate_percent": timing_stats['success_rate'] * 100,
                "avg_delay_ms": timing_stats['avg_delay_ms'],
                "expected_delay_ms": timing_stats['expected_delay_ms'],
                "calibration_status": timing_stats['calibration_status'],
                "pending_shots": timing_stats['pending_shots'],
                "pending_impacts": timing_stats['pending_impacts']
            }
        }
    
    async def start_bridge(self):
        """Start the enhanced bridge"""
        self.is_running = True
        logger.info("🚀 Timing-enhanced bridge started")
        self._log_calibration_status()
    
    async def stop_bridge(self):
        """Stop the enhanced bridge"""
        self.is_running = False
        await self._log_session_summary()
        logger.info("🛑 Timing-enhanced bridge stopped")

# Integration example for existing fixed_bridge.py
def integrate_timing_calibration_into_existing_bridge():
    """
    Example of how to modify your existing fixed_bridge.py to include timing calibration.
    
    Replace these sections in your existing bridge:
    
    1. In your AMG frame handler, replace:
        if frame_type == 0x0103:  # SHOT
            logger.info(f"AMG SHOT #{shot_number} detected")
    
    With:
        if frame_type == 0x0103:  # SHOT
            timestamp = datetime.now()
            logger.info(f"AMG SHOT #{shot_number} detected")
            timing_calibrator.add_shot_event(timestamp, shot_number, device_id)
    
    2. In your BT50 impact detection, replace:
        if magnitude >= threshold:
            logger.info(f"Impact detected: {magnitude:.1f}g")
    
    With:
        if magnitude >= threshold:
            timestamp = datetime.now()
            logger.info(f"Impact detected: {magnitude:.1f}g")
            timing_calibrator.add_impact_event(timestamp, magnitude, device_id, raw_value)
    
    3. Add timing calibrator initialization:
        from src.impact_bridge.timing_calibration import RealTimeTimingCalibrator
        timing_calibrator = RealTimeTimingCalibrator()
    
    4. Add periodic status reporting:
        async def log_timing_status():
            stats = timing_calibrator.get_correlation_stats()
            logger.info(f"Timing correlation: {stats['success_rate']*100:.1f}% success, "
                       f"avg delay {stats['avg_delay_ms']}ms")
    """
    pass

# Example usage and testing
async def test_timing_enhanced_bridge():
    """Test the timing enhanced bridge with simulated data"""
    bridge = TimingEnhancedBridge()
    await bridge.start_bridge()
    
    # Simulate AMG shot
    shot_time = datetime.now()
    await bridge.handle_amg_frame("60:09:C3:1F:DC:1A", b"\x01\x02\x03\x01\x00\x00", shot_time)
    
    # Simulate BT50 impact with 526ms delay (our discovered timing)
    await asyncio.sleep(0.526)  # Wait 526ms
    impact_time = datetime.now()
    await bridge.handle_bt50_data(
        "F8:FE:92:31:12:E3", 
        [1900, 0, 0], 
        [-189.0, 0.0, 0.0], 
        189.0, 
        impact_time
    )
    
    # Wait for correlation processing
    await asyncio.sleep(0.1)
    
    # Check status
    status = await bridge.get_bridge_status()
    print(f"Bridge Status: {json.dumps(status, indent=2)}")
    
    await bridge.stop_bridge()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("TinTown Timing Calibration Integration")
    print("=====================================")
    print()
    print("Calibration Parameters Discovered:")
    print(f"  • Expected delay: 526ms")
    print(f"  • Correlation window: 1520ms")  
    print(f"  • Delay tolerance: ±663ms")
    print(f"  • Standard deviation: 331ms")
    print(f"  • Success rate: 100% (6/6 shots correlated)")
    print()
    print("Run test with: python src/impact_bridge/timing_integration.py")
    
    asyncio.run(test_timing_enhanced_bridge())