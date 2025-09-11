"""
Real-time shot detection for BT50 sensor data.
Based on analysis showing 6 shots with 150 count threshold and 6-11 sample duration.
"""
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

@dataclass
class ShotEvent:
    """Represents a detected shot event"""
    shot_id: int
    start_sample: int
    end_sample: int
    duration_samples: int
    max_deviation: int
    timestamp: float
    x_values: List[int]  # Raw X values during the shot
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds (assuming 50Hz sampling)"""
        return self.duration_samples * 20.0  # 20ms per sample at 50Hz
    
    @property
    def timestamp_str(self) -> str:
        """Human readable timestamp"""
        return time.strftime('%H:%M:%S.%f', time.localtime(self.timestamp))[:-3]

class ShotDetector:
    """
    Real-time shot detection for BT50 sensor data
    
    Validated criteria:
    - X-axis deviation > 150 counts from baseline (2089)
    - Duration: 6-11 consecutive samples (120-220ms at 50Hz)
    - Minimum 1 second interval between shots
    """
    
    def __init__(self, 
                 baseline_x: int = 2089,
                 threshold: int = 150,
                 min_duration: int = 6,
                 max_duration: int = 11,
                 min_interval_seconds: float = 1.0,
                 sampling_rate_hz: float = 50.0):
        """
        Initialize shot detector
        
        Args:
            baseline_x: Expected baseline X value (2089 from calibration)
            threshold: Minimum deviation from baseline to trigger detection (150 counts)
            min_duration: Minimum consecutive samples for valid shot (6)
            max_duration: Maximum consecutive samples for valid shot (11)
            min_interval_seconds: Minimum time between shots (1.0s)
            sampling_rate_hz: BT50 sampling rate (50Hz)
        """
        self.baseline_x = baseline_x
        self.threshold = threshold
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.min_interval_seconds = min_interval_seconds
        self.sampling_rate_hz = sampling_rate_hz
        
        # State tracking
        self.sample_count = 0
        self.shot_count = 0
        self.in_shot = False
        self.shot_start_sample = 0
        self.shot_values: List[int] = []
        self.last_shot_time = 0.0
        
        # History for validation
        self.recent_shots: List[ShotEvent] = []
        
        self.logger = logging.getLogger(__name__)
        
    def reset(self):
        """Reset detector state"""
        self.sample_count = 0
        self.shot_count = 0
        self.in_shot = False
        self.shot_start_sample = 0
        self.shot_values = []
        self.last_shot_time = 0.0
        self.recent_shots = []
        
    def process_sample(self, x_raw: int, timestamp: Optional[float] = None) -> Optional[ShotEvent]:
        """
        Process a single BT50 X-axis sample and detect shots
        
        Args:
            x_raw: Raw X-axis count from BT50 sensor
            timestamp: Sample timestamp (uses current time if None)
            
        Returns:
            ShotEvent if shot completed, None otherwise
        """
        if timestamp is None:
            timestamp = time.time()
            
        self.sample_count += 1
        deviation = abs(x_raw - self.baseline_x)
        
        # Check if this sample exceeds threshold
        exceeds_threshold = deviation >= self.threshold
        
        if not self.in_shot and exceeds_threshold:
            # Start of potential shot
            # Check minimum interval since last shot
            if timestamp - self.last_shot_time >= self.min_interval_seconds:
                self.in_shot = True
                self.shot_start_sample = self.sample_count
                self.shot_values = [x_raw]
                self.logger.debug(f"Shot start at sample {self.sample_count}, deviation: {deviation}")
            else:
                self.logger.debug(f"Shot rejected - too soon after last shot ({timestamp - self.last_shot_time:.1f}s)")
                
        elif self.in_shot and exceeds_threshold:
            # Continue existing shot
            self.shot_values.append(x_raw)
            
            # Check for maximum duration exceeded
            duration = len(self.shot_values)
            if duration > self.max_duration:
                self.logger.debug(f"Shot rejected - too long ({duration} samples)")
                self._reset_shot_state()
                
        elif self.in_shot and not exceeds_threshold:
            # End of shot - validate and create event
            duration = len(self.shot_values)
            
            if duration >= self.min_duration:
                # Valid shot detected!
                self.shot_count += 1
                max_deviation = max(abs(x - self.baseline_x) for x in self.shot_values)
                
                shot_event = ShotEvent(
                    shot_id=self.shot_count,
                    start_sample=self.shot_start_sample,
                    end_sample=self.shot_start_sample + duration - 1,
                    duration_samples=duration,
                    max_deviation=max_deviation,
                    timestamp=timestamp,
                    x_values=self.shot_values.copy()
                )
                
                self.recent_shots.append(shot_event)
                self.last_shot_time = timestamp
                
                # Keep only last 10 shots in memory
                if len(self.recent_shots) > 10:
                    self.recent_shots.pop(0)
                    
                self.logger.info(f"Shot {self.shot_count} detected: "
                               f"samples {shot_event.start_sample}-{shot_event.end_sample}, "
                               f"duration {duration}, max deviation {max_deviation}")
                
                self._reset_shot_state()
                return shot_event
            else:
                self.logger.debug(f"Shot rejected - too short ({duration} samples)")
                self._reset_shot_state()
        
        # No shot event
        return None
    
    def _reset_shot_state(self):
        """Reset current shot tracking state"""
        self.in_shot = False
        self.shot_start_sample = 0
        self.shot_values = []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            'total_samples': self.sample_count,
            'total_shots': self.shot_count,
            'shots_per_minute': self.shot_count / (self.sample_count / self.sampling_rate_hz / 60) if self.sample_count > 0 else 0,
            'current_baseline': self.baseline_x,
            'threshold': self.threshold,
            'recent_shots': len(self.recent_shots),
            'last_shot_time': self.last_shot_time
        }
    
    def get_recent_shots(self, count: int = 5) -> List[ShotEvent]:
        """Get the most recent shot events"""
        return self.recent_shots[-count:] if self.recent_shots else []