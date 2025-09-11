"""
Statistical Timing Calibration System
Based on large sample analysis of 51 correlations from 152 shots and 101 impacts
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class StatisticalTimingCalibrator:
    """
    Advanced timing calibrator using statistical analysis from large sample data
    """
    
    def __init__(self):
        # Statistical findings from 51 correlations
        self.mean_delay_ms = 103.0  # Primary offset
        self.median_delay_ms = 83.0  # More stable central tendency
        self.std_dev_ms = 94.0      # High variability indicator
        
        # Confidence intervals (ms)
        self.confidence_68_lower = 9.2
        self.confidence_68_upper = 196.7
        self.confidence_95_lower = -80.8  # Note: negative indicates some BT50 detections before AMG
        self.confidence_95_upper = 286.7
        
        # Quality metrics
        self.sample_size = 51
        self.data_quality = "Poor"  # 9% consistency
        
        # Use median as primary offset for better stability
        self.recommended_offset_ms = self.median_delay_ms
        self.uncertainty_ms = self.std_dev_ms
        
        logger.info(f"Statistical calibrator initialized:")
        logger.info(f"  Primary offset: {self.recommended_offset_ms}ms")
        logger.info(f"  Uncertainty: ±{self.uncertainty_ms}ms")
        logger.info(f"  68% confidence: {self.confidence_68_lower:.1f}ms - {self.confidence_68_upper:.1f}ms")
        
    def project_impact_time(self, amg_shot_time: datetime, confidence_level: str = "median") -> Tuple[datetime, Dict]:
        """
        Project impact time from AMG shot time with statistical confidence
        
        Args:
            amg_shot_time: Time from AMG timer acoustic detection
            confidence_level: "median", "mean", "68_lower", "68_upper", "95_lower", "95_upper"
            
        Returns:
            Tuple of (projected_impact_time, timing_metadata)
        """
        offset_map = {
            "median": self.median_delay_ms,
            "mean": self.mean_delay_ms,
            "68_lower": self.confidence_68_lower,
            "68_upper": self.confidence_68_upper,
            "95_lower": self.confidence_95_lower,
            "95_upper": self.confidence_95_upper
        }
        
        offset_ms = offset_map.get(confidence_level, self.median_delay_ms)
        
        # Project impact time
        projected_time = amg_shot_time + timedelta(milliseconds=offset_ms)
        
        # Generate timing metadata
        metadata = {
            "amg_shot_time": amg_shot_time.isoformat(),
            "projected_impact_time": projected_time.isoformat(),
            "offset_used_ms": offset_ms,
            "confidence_level": confidence_level,
            "uncertainty_ms": self.uncertainty_ms,
            "statistical_quality": self.data_quality,
            "sample_size": self.sample_size,
            "confidence_intervals": {
                "68_percent": f"{self.confidence_68_lower:.1f} - {self.confidence_68_upper:.1f}ms",
                "95_percent": f"{self.confidence_95_lower:.1f} - {self.confidence_95_upper:.1f}ms"
            }
        }
        
        return projected_time, metadata
    
    def analyze_timing_accuracy(self, amg_time: datetime, actual_impact_time: datetime) -> Dict:
        """
        Analyze how well our statistical model predicted an actual impact
        
        Args:
            amg_time: AMG timer acoustic detection time
            actual_impact_time: Actual BT50 sensor impact onset time
            
        Returns:
            Analysis dictionary with accuracy metrics
        """
        actual_delay_ms = (actual_impact_time - amg_time).total_seconds() * 1000
        
        # Check against our statistical predictions
        median_prediction, _ = self.project_impact_time(amg_time, "median")
        median_error_ms = (actual_impact_time - median_prediction).total_seconds() * 1000
        
        # Determine confidence level this delay falls into
        confidence_level = "unknown"
        if self.confidence_68_lower <= actual_delay_ms <= self.confidence_68_upper:
            confidence_level = "68%"
        elif self.confidence_95_lower <= actual_delay_ms <= self.confidence_95_upper:
            confidence_level = "95%"
        elif actual_delay_ms < self.confidence_95_lower:
            confidence_level = "below_95%"
        else:
            confidence_level = "above_95%"
            
        return {
            "actual_delay_ms": actual_delay_ms,
            "predicted_delay_ms": self.median_delay_ms,
            "prediction_error_ms": median_error_ms,
            "confidence_level_achieved": confidence_level,
            "within_1_sigma": abs(actual_delay_ms - self.median_delay_ms) <= self.uncertainty_ms,
            "statistical_percentile": self._calculate_percentile(actual_delay_ms)
        }
    
    def _calculate_percentile(self, delay_ms: float) -> float:
        """
        Calculate approximate percentile of this delay in our statistical distribution
        Assumes normal distribution (approximation)
        """
        # Simple percentile calculation based on z-score
        z_score = (delay_ms - self.mean_delay_ms) / self.std_dev_ms
        
        # Approximate percentile (simplified)
        if z_score <= -1:
            return 16.0  # ~16th percentile
        elif z_score <= 0:
            return 16.0 + 34.0 * (z_score + 1)  # 16-50th percentile
        elif z_score <= 1:
            return 50.0 + 34.0 * z_score  # 50-84th percentile
        else:
            return min(100.0, 84.0 + 16.0 * min(z_score - 1, 1))  # 84-100th percentile
    
    def get_calibration_summary(self) -> Dict:
        """
        Get complete statistical calibration summary for logging/display
        """
        return {
            "calibration_type": "statistical_large_sample",
            "sample_size": self.sample_size,
            "statistics": {
                "mean_delay_ms": self.mean_delay_ms,
                "median_delay_ms": self.median_delay_ms,
                "std_deviation_ms": self.std_dev_ms,
                "recommended_offset_ms": self.recommended_offset_ms,
                "uncertainty_ms": self.uncertainty_ms
            },
            "confidence_intervals": {
                "68_percent": {
                    "lower_ms": self.confidence_68_lower,
                    "upper_ms": self.confidence_68_upper
                },
                "95_percent": {
                    "lower_ms": self.confidence_95_lower,
                    "upper_ms": self.confidence_95_upper
                }
            },
            "quality_metrics": {
                "data_quality": self.data_quality,
                "consistency_percent": 9.0,
                "delay_range_ms": f"{self.confidence_95_lower:.1f} - {self.confidence_95_upper:.1f}"
            },
            "usage_notes": [
                "High variability (±94ms) indicates real-world shooting conditions",
                "Median (83ms) preferred over mean (103ms) for stability", 
                "Some BT50 detections occur before AMG (negative delays)",
                "Consider projectile velocity and impact angle effects"
            ]
        }

# Create global instance
statistical_calibrator = StatisticalTimingCalibrator()