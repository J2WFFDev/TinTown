#!/usr/bin/env python3
"""
Enhanced Impact Detection with Onset Timing

This module improves impact detection by identifying the START of impact events,
not just peak magnitude, providing more accurate timing correlation.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

@dataclass
class SamplePoint:
    """Individual sensor sample with timestamp"""
    timestamp: datetime
    raw_values: List[int]  # [x, y, z] raw values
    corrected_values: List[float]  # [x, y, z] baseline-corrected values
    magnitude: float
    
@dataclass
class ImpactEvent:
    """Enhanced impact event with onset detection"""
    onset_timestamp: datetime  # When impact actually started
    peak_timestamp: datetime   # When maximum magnitude occurred
    onset_magnitude: float     # Magnitude when impact was first detected
    peak_magnitude: float      # Maximum magnitude during impact
    duration_ms: float         # Duration from onset to return to baseline
    sample_count: int          # Number of samples in impact sequence
    confidence: float          # Detection confidence (0.0-1.0)
    
    # Sample progression for analysis
    onset_samples: List[SamplePoint]   # Samples leading to onset detection
    peak_samples: List[SamplePoint]    # Samples around peak
    
class EnhancedImpactDetector:
    """Enhanced impact detection with onset timing"""
    
    def __init__(self, threshold: float = 150.0, onset_threshold: float = 30.0, 
                 lookback_samples: int = 10, minimum_duration_samples: int = 3):
        self.threshold = threshold  # Peak detection threshold
        self.onset_threshold = onset_threshold  # Onset detection threshold (lower)
        self.lookback_samples = lookback_samples  # How far to look back for onset
        self.minimum_duration_samples = minimum_duration_samples
        
        # Sample history for onset detection
        self.sample_history: List[SamplePoint] = []
        self.max_history = 20  # Keep last N samples
        
        # Impact state tracking
        self.in_impact = False
        self.current_impact_samples: List[SamplePoint] = []
        self.impact_start_index = -1
        
        logger.info(f"Enhanced impact detector initialized:")
        logger.info(f"  Peak threshold: {threshold}g")
        logger.info(f"  Onset threshold: {onset_threshold}g") 
        logger.info(f"  Lookback samples: {lookback_samples}")
        
    def process_sample(self, timestamp: datetime, raw_values: List[int], 
                      corrected_values: List[float], magnitude: float) -> Optional[ImpactEvent]:
        """Process a new sample and detect impact events with onset timing"""
        
        # Create sample point
        sample = SamplePoint(
            timestamp=timestamp,
            raw_values=raw_values.copy(),
            corrected_values=corrected_values.copy(),
            magnitude=magnitude
        )
        
        # Add to history (always maintain sample history)
        self.sample_history.append(sample)
        if len(self.sample_history) > self.max_history:
            self.sample_history.pop(0)
        
        # Impact detection logic: Look for ONSET first, not peak!
        if not self.in_impact:
            # Check for impact ONSET (lower threshold)
            if magnitude >= self.onset_threshold:
                return self._start_impact_detection(sample)
        else:
            # Already in impact, continue tracking
            self.current_impact_samples.append(sample)
            
            # Check for impact end (return to baseline)
            if magnitude < self.onset_threshold:
                return self._end_impact_detection(sample)
        
        return None
    
    def _start_impact_detection(self, onset_sample: SamplePoint) -> Optional[ImpactEvent]:
        """Start impact detection when onset threshold is crossed"""
        self.in_impact = True
        self.current_impact_samples = [onset_sample]  # Start with onset sample
        
        # Record the index of the onset sample in history
        self.impact_start_index = len(self.sample_history) - 1
        
        logger.debug(f"🎯 Impact onset detected: {onset_sample.magnitude:.1f}g at "
                    f"{onset_sample.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        return None  # Don't return event yet, continue tracking until end
    

    
    def _end_impact_detection(self, end_sample: SamplePoint) -> Optional[ImpactEvent]:
        """End impact detection and create impact event"""
        self.in_impact = False
        
        if len(self.current_impact_samples) < self.minimum_duration_samples:
            logger.debug("Impact too short, discarding")
            self.current_impact_samples.clear()
            return None
        
        # Onset is the FIRST sample in the sequence (when we started recording)
        onset_sample = self.current_impact_samples[0]
        
        # Peak is the HIGHEST magnitude sample in the sequence
        peak_sample = max(self.current_impact_samples, key=lambda s: s.magnitude)
        
        # Validate that we have a proper impact (peak should be above detection threshold)
        if peak_sample.magnitude < self.threshold:
            logger.debug(f"Peak magnitude {peak_sample.magnitude:.1f}g below threshold {self.threshold}g, discarding")
            self.current_impact_samples.clear()
            return None
        
        # Calculate impact metrics
        duration_ms = (end_sample.timestamp - onset_sample.timestamp).total_seconds() * 1000
        confidence = self._calculate_confidence(onset_sample, peak_sample, len(self.current_impact_samples))
        
        # Create impact event with correct timing order
        impact = ImpactEvent(
            onset_timestamp=onset_sample.timestamp,    # FIRST sample (onset)
            peak_timestamp=peak_sample.timestamp,      # HIGHEST sample (peak)
            onset_magnitude=onset_sample.magnitude,
            peak_magnitude=peak_sample.magnitude,
            duration_ms=duration_ms,
            sample_count=len(self.current_impact_samples),
            confidence=confidence,
            onset_samples=self.current_impact_samples[:3],  # First few samples
            peak_samples=self.current_impact_samples        # Full sequence
        )
        
        # Validate timing order
        onset_to_peak_ms = (peak_sample.timestamp - onset_sample.timestamp).total_seconds() * 1000
        
        # Store impact details for consolidated logging in main bridge
        impact._onset_to_peak_ms = onset_to_peak_ms
        impact._duration_ms = duration_ms
        impact._sample_count = len(self.current_impact_samples)
        impact._confidence = confidence
        
        self.current_impact_samples.clear()
        self.impact_start_index = -1
        
        return impact
    
    def _calculate_confidence(self, onset_sample: SamplePoint, peak_sample: SamplePoint, sample_count: int) -> float:
        """Calculate detection confidence based on signal characteristics"""
        
        # Base confidence from magnitude ratio
        magnitude_ratio = peak_sample.magnitude / max(onset_sample.magnitude, 1.0)
        magnitude_confidence = min(magnitude_ratio / 5.0, 1.0)  # 5x increase = 100% confidence
        
        # Duration confidence (prefer impacts with reasonable duration)
        duration_confidence = min(sample_count / 6.0, 1.0)  # 6+ samples = 100% confidence
        
        # Signal strength confidence
        strength_confidence = min(peak_sample.magnitude / (self.threshold * 1.5), 1.0)
        
        # Combined confidence
        confidence = (magnitude_confidence * 0.4 + duration_confidence * 0.3 + strength_confidence * 0.3)
        
        return min(max(confidence, 0.0), 1.0)

# Integration example for existing bridge
def integrate_enhanced_impact_detection():
    """
    Example integration with existing fixed_bridge.py:
    
    # In FixedBridge.__init__():
    from enhanced_impact_detection import EnhancedImpactDetector
    self.enhanced_impact_detector = EnhancedImpactDetector(
        threshold=150.0,        # Peak detection threshold
        onset_threshold=30.0,   # Onset detection threshold  
        lookback_samples=10     # Look back 10 samples for onset
    )
    
    # In bt50_notification_handler():
    # After calculating magnitude...
    impact_event = self.enhanced_impact_detector.process_sample(
        timestamp=datetime.now(),
        raw_values=[vx_raw, vy_raw, vz_raw],
        corrected_values=[vx_corrected, vy_corrected, vz_corrected],
        magnitude=magnitude_corrected
    )
    
    if impact_event:
        # Use onset_timestamp for timing correlation instead of peak timestamp
        self.timing_calibrator.add_impact_event(
            timestamp=impact_event.onset_timestamp,  # Key change: use onset!
            magnitude=impact_event.peak_magnitude,
            device_id=device_id,
            raw_value=vx_raw
        )
        
        self.logger.info(f"Enhanced Impact: onset {impact_event.onset_timestamp.strftime('%H:%M:%S.%f')[:-3]} "
                        f"→ peak {impact_event.peak_timestamp.strftime('%H:%M:%S.%f')[:-3]} "
                        f"({impact_event.onset_magnitude:.1f}g → {impact_event.peak_magnitude:.1f}g)")
    """
    pass

if __name__ == "__main__":
    # Test the enhanced impact detector
    import time
    
    logging.basicConfig(level=logging.INFO)
    detector = EnhancedImpactDetector()
    
    # Simulate sample sequence like observed in logs
    base_time = datetime.now()
    samples = [
        # Baseline samples
        ([1910, 0, 0], [0, 0, 0], 0.0),
        ([1906, 2, 4], [-4, 2, 4], 6.0),
        ([1919, 4, 4], [9, 4, 4], 10.6),
        # Onset
        ([1894, 62, 4], [-16, 62, 4], 64.2),  # First significant increase
        ([1938, 39, 4], [28, 39, 4], 48.2),
        ([1919, 83, 4], [9, 83, 4], 83.6),
        # Peak
        ([1900, 187, 4], [-10, 187, 4], 187.3),  # Peak detected here
        # Decay
        ([1906, 151, 4], [-4, 151, 4], 151.1),
        ([1919, 19, 4], [9, 19, 4], 21.4),
        ([1906, 5, 4], [-4, 5, 4], 7.5),  # Return to baseline
    ]
    
    print("Processing sample sequence...")
    for i, (raw, corrected, mag) in enumerate(samples):
        timestamp = base_time + timedelta(milliseconds=i * 50)  # 50ms intervals
        
        impact = detector.process_sample(timestamp, raw, corrected, mag)
        if impact:
            print(f"\n🎯 IMPACT DETECTED!")
            print(f"Onset: {impact.onset_timestamp.strftime('%H:%M:%S.%f')[:-3]} ({impact.onset_magnitude:.1f}g)")
            print(f"Peak:  {impact.peak_timestamp.strftime('%H:%M:%S.%f')[:-3]} ({impact.peak_magnitude:.1f}g)")
            onset_to_peak = (impact.peak_timestamp - impact.onset_timestamp).total_seconds() * 1000
            print(f"Onset→Peak: {onset_to_peak:.1f}ms")
            break