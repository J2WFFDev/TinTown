"""Impact detection algorithms with envelope, hysteresis, ring-min, and dead-time."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple


@dataclass
class DetectorParams:
    """Parameters for impact detection algorithm."""
    
    trigger_high: float
    trigger_low: float
    ring_min_ms: int
    dead_time_ms: int
    warmup_ms: int
    baseline_min: float
    min_amp: float


@dataclass
class HitEvent:
    """Detected impact event."""
    
    timestamp_ns: int
    peak_amplitude: float
    duration_ms: float
    rms_amplitude: float


class HitDetector:
    """Impact detector using envelope detection with hysteresis and dead-time."""
    
    def __init__(self, params: DetectorParams, sensor_id: str) -> None:
        self.params = params
        self.sensor_id = sensor_id
        
        # State tracking
        self._triggered = False
        self._trigger_start_ns: Optional[int] = None
        self._last_hit_ns: Optional[int] = None
        self._warmup_end_ns = time.monotonic_ns() + (params.warmup_ms * 1_000_000)
        
        # Ring buffer for minimum baseline calculation
        self._baseline_samples: Deque[float] = deque(maxlen=100)
        self._baseline = params.baseline_min
        
        # Event accumulation during trigger period
        self._event_samples: list[Tuple[int, float]] = []
    
    def process_sample(self, timestamp_ns: int, amplitude: float) -> Optional[HitEvent]:
        """
        Process a new amplitude sample and return HitEvent if impact detected.
        
        Args:
            timestamp_ns: Sample timestamp in nanoseconds (monotonic)
            amplitude: Amplitude value from sensor
            
        Returns:
            HitEvent if impact detected, None otherwise
        """
        # Skip processing during warmup period
        if timestamp_ns < self._warmup_end_ns:
            self._baseline_samples.append(amplitude)
            return None
        
        # Update baseline from recent samples
        self._update_baseline(amplitude)
        
        # Skip samples below minimum amplitude threshold
        if amplitude < self.params.min_amp:
            return None
        
        # Check dead time - don't trigger if too soon after last hit
        if (self._last_hit_ns is not None and 
            timestamp_ns - self._last_hit_ns < self.params.dead_time_ms * 1_000_000):
            return None
        
        # Normalize amplitude against baseline
        normalized_amp = max(amplitude - self._baseline, 0.0)
        
        # State machine for trigger detection
        if not self._triggered:
            # Check for trigger condition
            if normalized_amp >= self.params.trigger_high:
                self._triggered = True
                self._trigger_start_ns = timestamp_ns
                self._event_samples = [(timestamp_ns, amplitude)]
                # Debug: log trigger start
                print(f"[DEBUG] Trigger start ts={timestamp_ns} amp={amplitude:.6f} norm={normalized_amp:.6f} baseline={self._baseline:.6f}")
                return None
        else:
            # Already triggered - accumulate samples
            self._event_samples.append((timestamp_ns, amplitude))
            
            # Check for release condition
            # Primary release: amplitude falls below trigger_low
            if normalized_amp <= self.params.trigger_low:
                # Check minimum ring time
                duration_ns = timestamp_ns - self._trigger_start_ns
                if duration_ns >= self.params.ring_min_ms * 1_000_000:
                    # Valid hit detected
                    # Debug: about to create hit event
                    print(f"[DEBUG] Release at ts={timestamp_ns} duration_ns={duration_ns} samples={len(self._event_samples)}")
                    hit_event = self._create_hit_event()
                    self._reset_trigger()
                    self._last_hit_ns = timestamp_ns
                    return hit_event
                else:
                    # Too short - reset without generating event
                    self._reset_trigger()
            else:
                # Fallback: waveform may decay without crossing trigger_low due to sampling/noise.
                # If we've been triggered for at least ring_min_ms and the amplitude has
                # fallen significantly from its previous peak, treat it as a release.
                duration_ns = timestamp_ns - self._trigger_start_ns
                if duration_ns >= self.params.ring_min_ms * 1_000_000 and len(self._event_samples) >= 3:
                    # Compute recent peak in the accumulated event samples
                    peak_amp = max(a for _, a in self._event_samples) if self._event_samples else 0.0
                    prev_amp = self._event_samples[-2][1]
                    # Release if amplitude has decayed substantially from the peak, or
                    # if it dropped quickly relative to the previous sample.
                    # Use a peak-based threshold (60% of peak) to be robust against
                    # sampling alignment where the immediate previous sample may be close
                    # to the current one.
                    decayed_from_peak = peak_amp > 0 and amplitude <= (peak_amp * 0.6)
                    rapid_drop = prev_amp > 0 and amplitude <= (prev_amp * 0.55)
                    if decayed_from_peak or rapid_drop:
                        # Debug: fallback release triggered (decay)
                        print(f"[DEBUG] Fallback release at ts={timestamp_ns} peak_amp={peak_amp:.6f} amp={amplitude:.6f}")
                        hit_event = self._create_hit_event()
                        self._reset_trigger()
                        self._last_hit_ns = timestamp_ns
                        return hit_event
        
        return None
    
    def _update_baseline(self, amplitude: float) -> None:
        """Update baseline calculation with new sample."""
        self._baseline_samples.append(amplitude)
        
        if len(self._baseline_samples) >= 10:
            # Use minimum of recent samples as baseline
            min_recent = min(self._baseline_samples)
            self._baseline = max(min_recent, self.params.baseline_min)
    
    def _create_hit_event(self) -> HitEvent:
        """Create HitEvent from accumulated samples."""
        if not self._event_samples:
            raise ValueError("No samples to create hit event")
        
        # Find peak amplitude and timestamp
        peak_amp = 0.0
        peak_timestamp = self._event_samples[0][0]
        
        # Calculate RMS and find peak
        sum_squares = 0.0
        for timestamp_ns, amplitude in self._event_samples:
            if amplitude > peak_amp:
                peak_amp = amplitude
                peak_timestamp = timestamp_ns
            sum_squares += amplitude * amplitude
        
        rms_amp = (sum_squares / len(self._event_samples)) ** 0.5
        
        # Calculate duration
        start_ns = self._event_samples[0][0]
        end_ns = self._event_samples[-1][0]
        duration_ms = (end_ns - start_ns) / 1_000_000
        
        return HitEvent(
            timestamp_ns=peak_timestamp,
            peak_amplitude=peak_amp,
            duration_ms=duration_ms,
            rms_amplitude=rms_amp,
        )
    
    def _reset_trigger(self) -> None:
        """Reset trigger state."""
        self._triggered = False
        self._trigger_start_ns = None
        self._event_samples.clear()
    
    @property
    def is_warmed_up(self) -> bool:
        """Check if detector has completed warmup period."""
        return time.monotonic_ns() >= self._warmup_end_ns
    
    @property
    def current_baseline(self) -> float:
        """Get current baseline value."""
        return self._baseline
    
    @property
    def sample_count(self) -> int:
        """Get number of baseline samples collected."""
        return len(self._baseline_samples)


class MultiPlateDetector:
    """Manages multiple HitDetector instances for different plates."""
    
    def __init__(self, detector_params: DetectorParams) -> None:
        self.params = detector_params
        self._detectors: dict[str, HitDetector] = {}
    
    def add_plate(self, plate_id: str) -> None:
        """Add a new plate detector."""
        if plate_id not in self._detectors:
            self._detectors[plate_id] = HitDetector(self.params, plate_id)
    
    def process_sample(
        self, 
        plate_id: str, 
        timestamp_ns: int, 
        amplitude: float
    ) -> Optional[HitEvent]:
        """Process sample for specific plate."""
        if plate_id not in self._detectors:
            self.add_plate(plate_id)
        
        return self._detectors[plate_id].process_sample(timestamp_ns, amplitude)
    
    def get_detector_status(self, plate_id: str) -> dict[str, any]:
        """Get status information for a plate detector."""
        if plate_id not in self._detectors:
            return {"error": "Detector not found"}
        
        detector = self._detectors[plate_id]
        return {
            "plate_id": plate_id,
            "warmed_up": detector.is_warmed_up,
            "baseline": detector.current_baseline,
            "sample_count": detector.sample_count,
            "triggered": detector._triggered,
        }
    
    def get_all_status(self) -> dict[str, dict[str, any]]:
        """Get status for all plate detectors."""
        return {
            plate_id: self.get_detector_status(plate_id)
            for plate_id in self._detectors
        }