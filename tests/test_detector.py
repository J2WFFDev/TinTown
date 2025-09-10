"""Tests for impact detection algorithms with synthetic waveforms."""

import time
from unittest.mock import Mock

import pytest

from impact_bridge.detector import DetectorParams, HitDetector, HitEvent, MultiPlateDetector


class TestHitDetector:
    """Test suite for HitDetector with synthetic waveforms."""
    
    def setup_method(self):
        """Set up test detector with standard parameters."""
        self.params = DetectorParams(
            trigger_high=0.5,
            trigger_low=0.1,
            ring_min_ms=10,
            dead_time_ms=50,
            warmup_ms=100,
            baseline_min=0.01,
            min_amp=0.05,
        )
        self.detector = HitDetector(self.params, "test_sensor")
    
    def test_initialization(self):
        """Test detector initialization."""
        assert self.detector.sensor_id == "test_sensor"
        assert not self.detector.is_warmed_up
        assert self.detector.current_baseline >= self.params.baseline_min
        assert self.detector.sample_count == 0
    
    def test_warmup_period(self):
        """Test that detector ignores samples during warmup."""
        start_time = time.monotonic_ns()
        
        # Send high amplitude sample during warmup
        result = self.detector.process_sample(start_time + 50_000_000, 1.0)
        assert result is None
        
        # Wait for warmup to complete
        warmup_end = start_time + self.params.warmup_ms * 1_000_000
        
        # Should detect after warmup
        result = self.detector.process_sample(warmup_end + 1_000_000, 1.0)
        assert result is None  # Still building baseline
    
    def test_baseline_calculation(self):
        """Test baseline calculation from noise samples."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Send low amplitude noise samples
        noise_levels = [0.02, 0.03, 0.01, 0.025, 0.015, 0.02, 0.01, 0.03, 0.02, 0.015]
        
        for i, amplitude in enumerate(noise_levels):
            timestamp = start_time + i * 10_000_000  # 10ms intervals
            self.detector.process_sample(timestamp, amplitude)
        
        # Baseline should be near minimum of noise samples
        assert 0.009 <= self.detector.current_baseline <= 0.02
    
    def test_simple_impact_detection(self):
        """Test detection of a simple impact above threshold."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Build baseline with noise
        for i in range(10):
            timestamp = start_time + i * 10_000_000
            self.detector.process_sample(timestamp, 0.02)
        
        # Generate impact: rise, peak, fall
        impact_samples = [
            (start_time + 200_000_000, 0.1),   # Start rising
            (start_time + 210_000_000, 0.6),   # Above trigger_high
            (start_time + 220_000_000, 0.8),   # Peak
            (start_time + 230_000_000, 0.6),   # Start falling
            (start_time + 240_000_000, 0.3),   # Still above trigger_low
            (start_time + 250_000_000, 0.05),  # Below trigger_low
        ]
        
        result = None
        for timestamp, amplitude in impact_samples:
            result = self.detector.process_sample(timestamp, amplitude)
        
        # Should detect impact on final sample
        assert result is not None
        assert isinstance(result, HitEvent)
        assert result.peak_amplitude == 0.8
        assert result.duration_ms >= self.params.ring_min_ms
    
    def test_short_spike_rejection(self):
        """Test rejection of spikes shorter than ring_min_ms."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Build baseline
        for i in range(10):
            timestamp = start_time + i * 10_000_000
            self.detector.process_sample(timestamp, 0.02)
        
        # Generate short spike (< ring_min_ms)
        spike_samples = [
            (start_time + 200_000_000, 0.6),   # Above trigger_high
            (start_time + 205_000_000, 0.05),  # Below trigger_low (5ms duration)
        ]
        
        result = None
        for timestamp, amplitude in spike_samples:
            result = self.detector.process_sample(timestamp, amplitude)
        
        # Should not detect impact (too short)
        assert result is None
    
    def test_dead_time_enforcement(self):
        """Test that dead time prevents double-counting."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Build baseline
        for i in range(10):
            timestamp = start_time + i * 10_000_000
            self.detector.process_sample(timestamp, 0.02)
        
        # First impact
        first_impact = [
            (start_time + 200_000_000, 0.6),
            (start_time + 220_000_000, 0.05),
        ]
        
        for timestamp, amplitude in first_impact:
            result = self.detector.process_sample(timestamp, amplitude)
        
        # Should detect first impact
        assert result is not None
        
        # Second impact within dead time
        second_impact = [
            (start_time + 240_000_000, 0.6),   # 20ms after first (< dead_time_ms)
            (start_time + 260_000_000, 0.05),
        ]
        
        result = None
        for timestamp, amplitude in second_impact:
            result = self.detector.process_sample(timestamp, amplitude)
        
        # Should not detect second impact (within dead time)
        assert result is None
    
    def test_low_amplitude_filtering(self):
        """Test filtering of samples below min_amp threshold."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Send samples below min_amp (should be ignored)
        low_amp_samples = [
            (start_time + 200_000_000, 0.02),  # Below min_amp (0.05)
            (start_time + 210_000_000, 0.01),
            (start_time + 220_000_000, 0.03),
        ]
        
        for timestamp, amplitude in low_amp_samples:
            result = self.detector.process_sample(timestamp, amplitude)
            assert result is None
        
        # Detector should not be triggered
        assert not self.detector._triggered
    
    def test_hysteresis_behavior(self):
        """Test hysteresis behavior with trigger_high and trigger_low."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Build baseline
        for i in range(10):
            timestamp = start_time + i * 10_000_000
            self.detector.process_sample(timestamp, 0.02)
        
        # Test that trigger doesn't start until trigger_high
        samples = [
            (start_time + 200_000_000, 0.3),   # Above trigger_low but below trigger_high
            (start_time + 210_000_000, 0.4),   # Still below trigger_high
            (start_time + 220_000_000, 0.6),   # Above trigger_high - should trigger
        ]
        
        for timestamp, amplitude in samples[:2]:
            result = self.detector.process_sample(timestamp, amplitude)
            assert not self.detector._triggered
        
        # Should trigger on third sample
        result = self.detector.process_sample(samples[2][0], samples[2][1])
        assert self.detector._triggered


class TestMultiPlateDetector:
    """Test suite for MultiPlateDetector."""
    
    def setup_method(self):
        """Set up multi-plate detector."""
        self.params = DetectorParams(
            trigger_high=0.5,
            trigger_low=0.1,
            ring_min_ms=10,
            dead_time_ms=50,
            warmup_ms=100,
            baseline_min=0.01,
            min_amp=0.05,
        )
        self.detector = MultiPlateDetector(self.params)
    
    def test_plate_management(self):
        """Test adding and managing multiple plates."""
        # Add plates
        self.detector.add_plate("P1")
        self.detector.add_plate("P2")
        
        # Check status
        status = self.detector.get_all_status()
        assert "P1" in status
        assert "P2" in status
        assert len(status) == 2
    
    def test_independent_detection(self):
        """Test that plates detect impacts independently."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Add plates
        self.detector.add_plate("P1")
        self.detector.add_plate("P2")
        
        # Build baseline for both plates
        for i in range(10):
            timestamp = start_time + i * 10_000_000
            self.detector.process_sample("P1", timestamp, 0.02)
            self.detector.process_sample("P2", timestamp, 0.02)
        
        # Generate impact on P1 only
        p1_impact = [
            (start_time + 200_000_000, 0.6),
            (start_time + 220_000_000, 0.05),
        ]
        
        for timestamp, amplitude in p1_impact:
            result_p1 = self.detector.process_sample("P1", timestamp, amplitude)
            result_p2 = self.detector.process_sample("P2", timestamp, 0.02)  # No impact on P2
        
        # Only P1 should detect impact
        assert result_p1 is not None
        assert result_p2 is None
    
    def test_auto_plate_creation(self):
        """Test automatic plate creation when processing unknown plate."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Process sample for unknown plate - should auto-create
        result = self.detector.process_sample("P3", start_time, 0.1)
        
        # Check that plate was created
        status = self.detector.get_all_status()
        assert "P3" in status
    
    def test_plate_status_reporting(self):
        """Test status reporting for individual plates."""
        self.detector.add_plate("P1")
        
        # Get status for specific plate
        status = self.detector.get_detector_status("P1")
        assert status["plate_id"] == "P1"
        assert "warmed_up" in status
        assert "baseline" in status
        assert "sample_count" in status
        assert "triggered" in status
        
        # Test status for non-existent plate
        status = self.detector.get_detector_status("P999")
        assert "error" in status


class TestSyntheticWaveforms:
    """Test with realistic synthetic waveforms."""
    
    def setup_method(self):
        """Set up detector for waveform tests."""
        self.params = DetectorParams(
            trigger_high=0.1,
            trigger_low=0.05,
            ring_min_ms=20,
            dead_time_ms=100,
            warmup_ms=50,
            baseline_min=0.001,
            min_amp=0.01,
        )
        self.detector = HitDetector(self.params, "test_plate")
    
    def generate_impact_waveform(self, start_time: int, peak_amp: float, duration_ms: int) -> list:
        """Generate realistic impact waveform with rise, peak, decay."""
        samples = []
        sample_interval_ns = 5_000_000  # 5ms intervals
        duration_ns = duration_ms * 1_000_000
        
        # Generate samples for impact duration
        for i in range(duration_ms // 5):  # 5ms intervals
            timestamp = start_time + i * sample_interval_ns
            
            # Create triangular waveform with some noise
            progress = i / (duration_ms // 5)
            if progress <= 0.3:  # Rising edge
                amplitude = peak_amp * (progress / 0.3)
            elif progress <= 0.7:  # Peak
                amplitude = peak_amp * (0.9 + 0.1 * (0.5 - abs(progress - 0.5)))
            else:  # Decay
                amplitude = peak_amp * (1.0 - progress) / 0.3
            
            # Add small amount of noise
            import random
            amplitude += random.uniform(-0.01, 0.01) * peak_amp
            amplitude = max(0, amplitude)
            
            samples.append((timestamp, amplitude))
        
        return samples
    
    def test_realistic_impact_waveform(self):
        """Test with realistic impact waveform."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Build baseline
        for i in range(20):
            timestamp = start_time + i * 5_000_000
            self.detector.process_sample(timestamp, 0.005)
        
        # Generate and process impact waveform
        impact_start = start_time + 200_000_000
        waveform = self.generate_impact_waveform(impact_start, 0.5, 40)  # 40ms impact
        
        result = None
        for timestamp, amplitude in waveform:
            result = self.detector.process_sample(timestamp, amplitude)
        
        # Should detect impact
        assert result is not None
        assert result.peak_amplitude > 0.4  # Near expected peak
        assert 35 <= result.duration_ms <= 45  # Expected duration range
    
    def test_false_positive_prevention(self):
        """Test prevention of false positives from noise and vibration."""
        start_time = time.monotonic_ns() + self.params.warmup_ms * 1_000_000
        
        # Generate continuous low-level vibration
        vibration_samples = []
        for i in range(100):  # 500ms of vibration
            timestamp = start_time + i * 5_000_000
            # Sine wave with noise
            import math
            amplitude = 0.03 + 0.02 * math.sin(i * 0.3) + 0.01 * (0.5 - (i % 2))
            vibration_samples.append((timestamp, amplitude))
        
        # Process vibration - should not trigger
        for timestamp, amplitude in vibration_samples:
            result = self.detector.process_sample(timestamp, amplitude)
            assert result is None  # No false positives
        
        # Verify detector is ready for real impact
        assert not self.detector._triggered