#!/usr/bin/env python3
"""
TinTown Real-Time Timing Calibration System

Integrates timing calibration into the live bridge system using the discovered
526ms mean delay with 331ms standard deviation.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class TimingCalibration:
    """Calibration parameters for shot-impact correlation"""
    expected_delay_ms: int = 526
    correlation_window_ms: int = 1520
    delay_tolerance_ms: int = 663
    minimum_magnitude: float = 150.0
    learning_rate: float = 0.1
    sample_count: int = 6
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'TimingCalibration':
        """Load calibration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                calibration_data = data.get('timing_calibration', {})
                return cls(
                    expected_delay_ms=calibration_data.get('expected_delay_ms', 526),
                    correlation_window_ms=calibration_data.get('correlation_window_ms', 1520),
                    delay_tolerance_ms=calibration_data.get('delay_tolerance_ms', 663),
                    minimum_magnitude=calibration_data.get('minimum_magnitude', 150.0),
                    sample_count=calibration_data.get('sample_count', 6)
                )
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load calibration from {config_path}: {e}")
            logger.info("Using default calibration parameters")
            return cls()
    
    def save_to_file(self, config_path: Path):
        """Save calibration to JSON file"""
        config_data = {
            'timing_calibration': asdict(self),
            'last_updated': datetime.now().isoformat(),
            'status': 'active'
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Calibration saved to {config_path}")

@dataclass
class ShotEvent:
    """Shot event from AMG timer"""
    timestamp: datetime
    shot_number: int
    device_id: str
    
@dataclass
class ImpactEvent:
    """Impact event from BT50 sensor"""
    timestamp: datetime
    magnitude: float
    device_id: str
    raw_value: float

@dataclass
class CorrelatedPair:
    """Correlated shot-impact pair"""
    shot: ShotEvent
    impact: ImpactEvent
    delay_ms: int
    confidence: float
    
    def is_valid(self, calibration: TimingCalibration) -> bool:
        """Check if pair meets calibration criteria"""
        return (
            0 <= self.delay_ms <= calibration.correlation_window_ms and
            self.impact.magnitude >= calibration.minimum_magnitude and
            abs(self.delay_ms - calibration.expected_delay_ms) <= calibration.delay_tolerance_ms
        )

class RealTimeTimingCalibrator:
    """Real-time timing calibration and correlation system"""
    
    def __init__(self, calibration_file: Path = None):
        self.calibration_file = calibration_file or Path("timing_calibration.json")
        self.calibration = TimingCalibration.from_file(self.calibration_file)
        
        # Event buffers
        self.pending_shots: List[ShotEvent] = []
        self.pending_impacts: List[ImpactEvent] = []
        self.correlated_pairs: List[CorrelatedPair] = []
        
        # Learning system
        self.recent_delays: List[int] = []
        self.max_buffer_size = 50
        self.max_learning_samples = 20
        
        logger.info(f"Timing calibrator initialized")
        logger.info(f"Expected delay: {self.calibration.expected_delay_ms}ms")
        logger.info(f"Correlation window: {self.calibration.correlation_window_ms}ms")
        logger.info(f"Delay tolerance: ±{self.calibration.delay_tolerance_ms}ms")
    
    def add_shot_event(self, timestamp: datetime, shot_number: int, device_id: str):
        """Add a new shot event for correlation"""
        shot = ShotEvent(timestamp=timestamp, shot_number=shot_number, device_id=device_id)
        self.pending_shots.append(shot)
        
        logger.debug(f"Shot #{shot_number} recorded at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # Cleanup old shots outside correlation window
        cutoff_time = timestamp - timedelta(milliseconds=self.calibration.correlation_window_ms)
        self.pending_shots = [s for s in self.pending_shots if s.timestamp >= cutoff_time]
        
        # Try to correlate with pending impacts
        asyncio.create_task(self._correlate_events())
    
    def add_impact_event(self, timestamp: datetime, magnitude: float, device_id: str, raw_value: float = None):
        """Add a new impact event for correlation"""
        if magnitude < self.calibration.minimum_magnitude:
            return  # Skip weak impacts
            
        impact = ImpactEvent(
            timestamp=timestamp, 
            magnitude=magnitude, 
            device_id=device_id,
            raw_value=raw_value or magnitude
        )
        self.pending_impacts.append(impact)
        
        logger.debug(f"Impact {magnitude:.1f}g recorded at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # Cleanup old impacts outside correlation window
        cutoff_time = timestamp - timedelta(milliseconds=self.calibration.correlation_window_ms)
        self.pending_impacts = [i for i in self.pending_impacts if i.timestamp >= cutoff_time]
        
        # Try to correlate with pending shots
        asyncio.create_task(self._correlate_events())
    
    async def _correlate_events(self):
        """Correlate pending shots with impacts"""
        new_pairs = []
        used_impacts = set()
        
        for shot in self.pending_shots:
            best_impact = None
            best_delay = float('inf')
            best_index = -1
            
            # Look for impacts after this shot within the correlation window
            window_end = shot.timestamp + timedelta(milliseconds=self.calibration.correlation_window_ms)
            
            for i, impact in enumerate(self.pending_impacts):
                if i in used_impacts:
                    continue
                
                # Impact must be after shot and within window
                if impact.timestamp < shot.timestamp or impact.timestamp > window_end:
                    continue
                
                delay_ms = (impact.timestamp - shot.timestamp).total_seconds() * 1000
                
                # Prefer impacts closer to expected delay
                delay_difference = abs(delay_ms - self.calibration.expected_delay_ms)
                
                if delay_difference < best_delay:
                    best_delay = delay_difference
                    best_impact = impact
                    best_index = i
            
            # Create correlated pair if we found a good match
            if best_impact and best_index >= 0:
                actual_delay = int((best_impact.timestamp - shot.timestamp).total_seconds() * 1000)
                confidence = self._calculate_confidence(actual_delay)
                
                pair = CorrelatedPair(
                    shot=shot,
                    impact=best_impact,
                    delay_ms=actual_delay,
                    confidence=confidence
                )
                
                if pair.is_valid(self.calibration):
                    new_pairs.append(pair)
                    used_impacts.add(best_index)
                    self.correlated_pairs.append(pair)
                    
                    logger.debug(f"✅ Correlated Shot #{shot.shot_number} → Impact {best_impact.magnitude:.1f}g "
                               f"(delay: {actual_delay}ms, confidence: {confidence:.2f})")
                    
                    # Update learning system
                    await self._update_calibration(actual_delay)
                # Note: Removed overly strict validation warning - correlations like 90ms vs 83ms expected are actually excellent
        
        # Remove successfully correlated shots and impacts
        for pair in new_pairs:
            try:
                self.pending_shots.remove(pair.shot)
            except ValueError:
                pass
        
        for i in sorted(used_impacts, reverse=True):
            if i < len(self.pending_impacts):
                del self.pending_impacts[i]
        
        # Cleanup old buffers
        await self._cleanup_old_data()
    
    def _calculate_confidence(self, delay_ms: int) -> float:
        """Calculate confidence based on how close delay is to expected"""
        delay_difference = abs(delay_ms - self.calibration.expected_delay_ms)
        max_difference = self.calibration.delay_tolerance_ms
        
        if delay_difference == 0:
            return 1.0
        elif delay_difference <= max_difference:
            return 1.0 - (delay_difference / max_difference) * 0.5
        else:
            return max(0.0, 0.5 - (delay_difference - max_difference) / max_difference)
    
    async def _update_calibration(self, actual_delay: int):
        """Update calibration based on observed delays (adaptive learning)"""
        self.recent_delays.append(actual_delay)
        
        # Keep only recent samples for learning
        if len(self.recent_delays) > self.max_learning_samples:
            self.recent_delays = self.recent_delays[-self.max_learning_samples:]
        
        # Update expected delay with exponential moving average
        if len(self.recent_delays) >= 3:
            recent_mean = sum(self.recent_delays) / len(self.recent_delays)
            old_expected = self.calibration.expected_delay_ms
            
            # Apply learning rate
            new_expected = int(
                old_expected * (1 - self.calibration.learning_rate) + 
                recent_mean * self.calibration.learning_rate
            )
            
            if abs(new_expected - old_expected) > 5:  # Only update if significant change
                self.calibration.expected_delay_ms = new_expected
                logger.info(f"📊 Updated expected delay: {old_expected}ms → {new_expected}ms "
                           f"(based on {len(self.recent_delays)} recent samples)")
                
                # Save updated calibration
                self.calibration.sample_count += 1
                self.calibration.save_to_file(self.calibration_file)
    
    async def _cleanup_old_data(self):
        """Remove old correlation data"""
        # Keep only recent pairs for statistics
        cutoff_time = datetime.now() - timedelta(minutes=10)
        self.correlated_pairs = [
            pair for pair in self.correlated_pairs 
            if pair.shot.timestamp >= cutoff_time
        ]
        
        # Limit buffer sizes
        if len(self.pending_shots) > self.max_buffer_size:
            self.pending_shots = self.pending_shots[-self.max_buffer_size:]
        
        if len(self.pending_impacts) > self.max_buffer_size:
            self.pending_impacts = self.pending_impacts[-self.max_buffer_size:]
    
    def get_correlation_stats(self) -> dict:
        """Get current correlation statistics"""
        if not self.correlated_pairs:
            return {
                'total_pairs': 0,
                'success_rate': 0.0,
                'avg_delay_ms': self.calibration.expected_delay_ms,
                'calibration_status': 'no_data'
            }
        
        recent_pairs = [
            pair for pair in self.correlated_pairs 
            if pair.shot.timestamp >= datetime.now() - timedelta(minutes=5)
        ]
        
        if recent_pairs:
            avg_delay = sum(pair.delay_ms for pair in recent_pairs) / len(recent_pairs)
            avg_confidence = sum(pair.confidence for pair in recent_pairs) / len(recent_pairs)
        else:
            avg_delay = self.calibration.expected_delay_ms
            avg_confidence = 0.0
        
        return {
            'total_pairs': len(self.correlated_pairs),
            'recent_pairs': len(recent_pairs),
            'success_rate': len(recent_pairs) / max(len(self.pending_shots) + len(recent_pairs), 1),
            'avg_delay_ms': int(avg_delay),
            'avg_confidence': avg_confidence,
            'expected_delay_ms': self.calibration.expected_delay_ms,
            'calibration_status': 'active' if recent_pairs else 'learning',
            'pending_shots': len(self.pending_shots),
            'pending_impacts': len(self.pending_impacts)
        }

# Example integration with existing bridge
class TimingAwareBridge:
    """Example of how to integrate timing calibrator into existing bridge"""
    
    def __init__(self):
        self.timing_calibrator = RealTimeTimingCalibrator()
        logger.info("Timing-aware bridge initialized")
    
    async def handle_amg_shot(self, shot_number: int, device_id: str, timestamp: datetime = None):
        """Handle AMG timer shot event"""
        timestamp = timestamp or datetime.now()
        
        # Add to timing calibrator
        self.timing_calibrator.add_shot_event(timestamp, shot_number, device_id)
        
        # Your existing shot handling logic here
        logger.info(f"AMG Shot #{shot_number} processed")
    
    async def handle_bt50_impact(self, magnitude: float, device_id: str, raw_value: float, timestamp: datetime = None):
        """Handle BT50 sensor impact event"""
        timestamp = timestamp or datetime.now()
        
        # Add to timing calibrator
        self.timing_calibrator.add_impact_event(timestamp, magnitude, device_id, raw_value)
        
        # Your existing impact handling logic here
        if magnitude >= 150:  # Your threshold
            logger.info(f"BT50 Impact detected: {magnitude:.1f}g")
    
    async def get_timing_status(self) -> dict:
        """Get current timing calibration status"""
        return self.timing_calibrator.get_correlation_stats()

# Example usage
async def main():
    """Example of using the timing calibration system"""
    bridge = TimingAwareBridge()
    
    # Simulate some shot and impact events
    base_time = datetime.now()
    
    # Shot 1 with quick impact (99ms delay like we observed)
    await bridge.handle_amg_shot(1, "Timer", base_time)
    await asyncio.sleep(0.1)  # 100ms
    await bridge.handle_bt50_impact(194.9, "Sensor", 1900.0, base_time + timedelta(milliseconds=99))
    
    # Shot 2 with long delay (880ms like we observed)  
    await bridge.handle_amg_shot(2, "Timer", base_time + timedelta(seconds=2))
    await asyncio.sleep(0.9)  # 900ms
    await bridge.handle_bt50_impact(157.6, "Sensor", 1850.0, base_time + timedelta(seconds=2, milliseconds=880))
    
    # Get timing status
    await asyncio.sleep(0.1)
    stats = await bridge.get_timing_status()
    print(f"Timing Stats: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())