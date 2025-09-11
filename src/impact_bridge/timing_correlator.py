"""
Enhanced Shot Detection with Timing Correlation

Extends the existing shot detection module to include real-time timing correlation
between AMG timer events and BT50 sensor impacts.

Features:
- Real-time shot-impact pairing
- Adaptive timing windows
- Correlation statistics
- Calibration learning mode
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Deque
from collections import deque
import statistics
import logging
from dataclasses import dataclass

from .shot_detector import ShotDetector  # Import existing detector


@dataclass
class TimingEvent:
    """Represents a timestamped event."""
    timestamp: datetime
    event_type: str  # 'shot' or 'impact'
    device_id: str
    magnitude: float = None
    shot_number: int = None
    details: str = ""


@dataclass
class CorrelatedPair:
    """Represents a correlated shot-impact pair."""
    shot: TimingEvent
    impact: TimingEvent
    delay_ms: int
    confidence: float
    
    @property
    def delay_seconds(self) -> float:
        return self.delay_ms / 1000.0


class TimingCorrelator:
    """Handles real-time correlation between timer and sensor events."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Correlation parameters
        self.correlation_window_ms = self.config.get('correlation_window_ms', 1000)
        self.expected_delay_ms = self.config.get('expected_delay_ms', 450)  # From handoff notes
        self.delay_tolerance_ms = self.config.get('delay_tolerance_ms', 200)
        self.min_magnitude = self.config.get('min_magnitude', 0.1)
        
        # Event buffers (ring buffers for memory efficiency)
        self.shot_events: Deque[TimingEvent] = deque(maxlen=50)
        self.impact_events: Deque[TimingEvent] = deque(maxlen=200)
        self.correlations: Deque[CorrelatedPair] = deque(maxlen=100)
        
        # Adaptive learning
        self.learning_mode = self.config.get('learning_mode', True)
        self.min_correlations_for_learning = 5
        
        # Statistics
        self.stats = {
            'shots_received': 0,
            'impacts_received': 0,
            'pairs_correlated': 0,
            'correlation_rate': 0.0,
            'avg_delay_ms': 0.0,
            'last_updated': datetime.now()
        }
        
        self.logger = logging.getLogger(__name__)
    
    async def process_shot_event(self, device_id: str, shot_number: int, timestamp: datetime = None) -> Optional[CorrelatedPair]:
        """Process a new shot event and attempt correlation."""
        if timestamp is None:
            timestamp = datetime.now()
        
        shot_event = TimingEvent(
            timestamp=timestamp,
            event_type='shot',
            device_id=device_id,
            shot_number=shot_number,
            details=f"Shot #{shot_number}"
        )
        
        self.shot_events.append(shot_event)
        self.stats['shots_received'] += 1
        
        self.logger.info(f"📝 String: Timer {device_id} - Shot #{shot_number}")
        
        # Attempt immediate correlation with recent impacts
        correlation = await self._correlate_shot(shot_event)
        
        if correlation:
            self.logger.info(f"📝 Impact Correlated: Shot #{shot_number} → Impact {correlation.impact.magnitude:.3f}g ({correlation.delay_ms}ms delay)")
            return correlation
        
        return None
    
    async def process_impact_event(self, device_id: str, magnitude: float, timestamp: datetime = None) -> Optional[CorrelatedPair]:
        """Process a new impact event and attempt correlation."""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Filter by minimum magnitude
        if magnitude < self.min_magnitude:
            return None
        
        impact_event = TimingEvent(
            timestamp=timestamp,
            event_type='impact',
            device_id=device_id,
            magnitude=magnitude,
            details=f"Impact {magnitude:.3f}g"
        )
        
        self.impact_events.append(impact_event)
        self.stats['impacts_received'] += 1
        
        self.logger.info(f"📝 Impact Detected: Sensor {device_id} Mag = {magnitude:.0f} [{magnitude:.3f}g]")
        
        # Attempt correlation with recent shots
        correlation = await self._correlate_impact(impact_event)
        
        if correlation:
            self.logger.info(f"📝 Impact Correlated: Shot #{correlation.shot.shot_number} → Impact {magnitude:.3f}g ({correlation.delay_ms}ms delay)")
            return correlation
        
        return None
    
    async def _correlate_shot(self, shot_event: TimingEvent) -> Optional[CorrelatedPair]:
        """Correlate a shot with future impacts within the timing window."""
        # Look for impacts that occur after this shot within the correlation window
        window_end = shot_event.timestamp + timedelta(milliseconds=self.correlation_window_ms)
        
        # Check existing impacts that might correlate
        for impact in reversed(self.impact_events):
            if impact.timestamp < shot_event.timestamp:
                continue
            if impact.timestamp > window_end:
                continue
            if hasattr(impact, 'correlated') and impact.correlated:
                continue
                
            delay_ms = int((impact.timestamp - shot_event.timestamp).total_seconds() * 1000)
            confidence = self._calculate_confidence(delay_ms, impact.magnitude)
            
            if confidence > 0.5:  # Minimum confidence threshold
                correlation = CorrelatedPair(
                    shot=shot_event,
                    impact=impact,
                    delay_ms=delay_ms,
                    confidence=confidence
                )
                
                # Mark events as correlated
                impact.correlated = True
                shot_event.correlated = True
                
                await self._register_correlation(correlation)
                return correlation
        
        return None
    
    async def _correlate_impact(self, impact_event: TimingEvent) -> Optional[CorrelatedPair]:
        """Correlate an impact with recent shots."""
        # Look for shots that occurred before this impact within the correlation window
        window_start = impact_event.timestamp - timedelta(milliseconds=self.correlation_window_ms)
        
        best_correlation = None
        best_confidence = 0.0
        
        for shot in reversed(self.shot_events):
            if shot.timestamp > impact_event.timestamp:
                continue
            if shot.timestamp < window_start:
                break
            if hasattr(shot, 'correlated') and shot.correlated:
                continue
                
            delay_ms = int((impact_event.timestamp - shot.timestamp).total_seconds() * 1000)
            confidence = self._calculate_confidence(delay_ms, impact_event.magnitude)
            
            if confidence > best_confidence and confidence > 0.5:
                best_confidence = confidence
                best_correlation = CorrelatedPair(
                    shot=shot,
                    impact=impact_event,
                    delay_ms=delay_ms,
                    confidence=confidence
                )
        
        if best_correlation:
            # Mark events as correlated
            best_correlation.shot.correlated = True
            best_correlation.impact.correlated = True
            
            await self._register_correlation(best_correlation)
            return best_correlation
        
        return None
    
    def _calculate_confidence(self, delay_ms: int, magnitude: float) -> float:
        """Calculate correlation confidence based on timing and magnitude."""
        # Timing confidence (closer to expected delay = higher confidence)
        timing_diff = abs(delay_ms - self.expected_delay_ms)
        timing_confidence = max(0, 1.0 - (timing_diff / self.delay_tolerance_ms))
        
        # Magnitude confidence (higher magnitude = higher confidence)
        magnitude_confidence = min(1.0, magnitude / 1.0)  # Normalize around 1g
        
        # Combined confidence
        confidence = (timing_confidence * 0.7) + (magnitude_confidence * 0.3)
        return max(0.0, min(1.0, confidence))
    
    async def _register_correlation(self, correlation: CorrelatedPair):
        """Register a new correlation and update statistics."""
        self.correlations.append(correlation)
        self.stats['pairs_correlated'] += 1
        
        # Update statistics
        delays = [c.delay_ms for c in self.correlations]
        self.stats['avg_delay_ms'] = statistics.mean(delays)
        self.stats['correlation_rate'] = (self.stats['pairs_correlated'] / max(1, self.stats['shots_received'])) * 100
        self.stats['last_updated'] = datetime.now()
        
        # Adaptive learning
        if self.learning_mode and len(self.correlations) >= self.min_correlations_for_learning:
            await self._update_timing_parameters()
    
    async def _update_timing_parameters(self):
        """Update timing parameters based on recent correlations."""
        if len(self.correlations) < 3:
            return
        
        # Analyze recent correlations (last 10)
        recent_correlations = list(self.correlations)[-10:]
        recent_delays = [c.delay_ms for c in recent_correlations]
        
        new_expected_delay = int(statistics.mean(recent_delays))
        new_tolerance = int(statistics.stdev(recent_delays) * 2) if len(recent_delays) > 1 else self.delay_tolerance_ms
        new_window = new_expected_delay + (new_tolerance * 2)
        
        # Only update if changes are significant
        if abs(new_expected_delay - self.expected_delay_ms) > 50:
            old_delay = self.expected_delay_ms
            self.expected_delay_ms = new_expected_delay
            self.logger.info(f"🔧 Adapted expected delay: {old_delay}ms → {new_expected_delay}ms")
        
        if abs(new_window - self.correlation_window_ms) > 100:
            old_window = self.correlation_window_ms
            self.correlation_window_ms = new_window
            self.logger.info(f"🔧 Adapted correlation window: {old_window}ms → {new_window}ms")
    
    def get_correlation_statistics(self) -> Dict:
        """Get current correlation statistics."""
        if not self.correlations:
            return self.stats
        
        delays = [c.delay_ms for c in self.correlations]
        confidences = [c.confidence for c in self.correlations]
        
        return {
            **self.stats,
            'delay_stats': {
                'min_ms': min(delays),
                'max_ms': max(delays),
                'mean_ms': statistics.mean(delays),
                'median_ms': statistics.median(delays),
                'stdev_ms': statistics.stdev(delays) if len(delays) > 1 else 0
            },
            'confidence_stats': {
                'min': min(confidences),
                'max': max(confidences),
                'mean': statistics.mean(confidences)
            },
            'current_parameters': {
                'correlation_window_ms': self.correlation_window_ms,
                'expected_delay_ms': self.expected_delay_ms,
                'delay_tolerance_ms': self.delay_tolerance_ms
            }
        }
    
    def export_calibration_config(self) -> Dict:
        """Export current timing parameters as calibration config."""
        return {
            'timing_correlation': {
                'correlation_window_ms': self.correlation_window_ms,
                'expected_delay_ms': self.expected_delay_ms,
                'delay_tolerance_ms': self.delay_tolerance_ms,
                'min_magnitude': self.min_magnitude,
                'learning_mode': self.learning_mode,
                'calibrated_from_samples': len(self.correlations),
                'calibration_date': datetime.now().isoformat()
            }
        }


class EnhancedShotDetector(ShotDetector):
    """Enhanced shot detector with timing correlation capabilities."""
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.timing_correlator = TimingCorrelator(config.get('timing_correlation', {}) if config else {})
        self.logger = logging.getLogger(__name__)
    
    async def process_timer_data(self, device_id: str, amg_data: Dict) -> Optional[CorrelatedPair]:
        """Process AMG timer data and correlate with impacts."""
        if 'shot_number' in amg_data:
            shot_number = amg_data['shot_number']
            timestamp = datetime.now()
            
            correlation = await self.timing_correlator.process_shot_event(
                device_id=device_id,
                shot_number=shot_number,
                timestamp=timestamp
            )
            
            return correlation
        
        return None
    
    async def process_sensor_data(self, device_id: str, sensor_data: List[float]) -> Optional[CorrelatedPair]:
        """Process sensor data, detect impacts, and correlate with shots."""
        # Use existing shot detection
        impact_detected = self.detect_shot(sensor_data)
        
        if impact_detected:
            # Calculate magnitude
            magnitude = self.calculate_magnitude(sensor_data)
            timestamp = datetime.now()
            
            correlation = await self.timing_correlator.process_impact_event(
                device_id=device_id,
                magnitude=magnitude,
                timestamp=timestamp
            )
            
            return correlation
        
        return None
    
    def calculate_magnitude(self, sensor_data: List[float]) -> float:
        """Calculate impact magnitude from sensor data."""
        if not sensor_data:
            return 0.0
        
        # Use RMS or peak magnitude
        rms = (sum(x**2 for x in sensor_data) / len(sensor_data)) ** 0.5
        peak = max(abs(x) for x in sensor_data)
        
        # Return the larger of RMS or peak for significance
        return max(rms, peak)
    
    def get_timing_statistics(self) -> Dict:
        """Get timing correlation statistics."""
        return self.timing_correlator.get_correlation_statistics()
    
    async def calibrate_timing(self, duration_seconds: int = 60) -> Dict:
        """Run timing calibration mode for specified duration."""
        self.logger.info(f"🔧 Starting timing calibration mode for {duration_seconds} seconds...")
        
        # Enable learning mode
        self.timing_correlator.learning_mode = True
        
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=duration_seconds)
        
        initial_stats = self.timing_correlator.get_correlation_statistics()
        
        while datetime.now() < end_time:
            await asyncio.sleep(1)  # Check every second
        
        final_stats = self.timing_correlator.get_correlation_statistics()
        
        calibration_result = {
            'calibration_duration_seconds': duration_seconds,
            'initial_parameters': initial_stats.get('current_parameters', {}),
            'final_parameters': final_stats.get('current_parameters', {}),
            'correlations_captured': final_stats['pairs_correlated'] - initial_stats.get('pairs_correlated', 0),
            'final_correlation_rate': final_stats['correlation_rate'],
            'config': self.timing_correlator.export_calibration_config()
        }
        
        self.logger.info(f"🔧 Calibration complete. Captured {calibration_result['correlations_captured']} correlations.")
        self.logger.info(f"🔧 Final correlation rate: {final_stats['correlation_rate']:.1f}%")
        
        return calibration_result