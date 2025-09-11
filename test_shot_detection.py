#!/usr/bin/env python3
"""
Test script to validate shot detection integration in the bridge system.
This script can be run locally to test the shot detector with sample data.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from impact_bridge.shot_detector import ShotDetector
import csv
import time

def test_shot_detector_with_csv():
    """Test shot detector using the extracted CSV data"""
    
    # Initialize detector with same parameters as bridge
    detector = ShotDetector(
        baseline_x=2089,
        threshold=150,
        min_duration=6,
        max_duration=11,
        min_interval_seconds=1.0
    )
    
    csv_file = "bt50_xyz_data.csv"
    if not Path(csv_file).exists():
        print(f"❌ CSV file not found: {csv_file}")
        print("Please ensure bt50_xyz_data.csv exists in the current directory")
        return False
    
    print(f"🔍 Testing shot detector with {csv_file}")
    print(f"Detector parameters:")
    print(f"  Baseline X: {detector.baseline_x}")
    print(f"  Threshold: {detector.threshold} counts")
    print(f"  Duration: {detector.min_duration}-{detector.max_duration} samples")
    print(f"  Min interval: {detector.min_interval_seconds}s")
    print()
    
    shots_detected = []
    sample_count = 0
    
    # Read and process CSV data
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            sample_count += 1
            x_raw = int(row['X_Raw'])
            
            # Simulate timing (50Hz = 20ms per sample)
            timestamp = sample_count * 0.02
            
            # Process sample through detector
            shot_event = detector.process_sample(x_raw, timestamp)
            
            if shot_event:
                shots_detected.append(shot_event)
                print(f"🎯 Shot #{shot_event.shot_id} detected:")
                print(f"   Samples: {shot_event.start_sample}-{shot_event.end_sample}")
                print(f"   Duration: {shot_event.duration_samples} samples ({shot_event.duration_ms:.0f}ms)")
                print(f"   Max deviation: {shot_event.max_deviation} counts")
                print(f"   Time: {shot_event.timestamp:.1f}s")
                print(f"   X values: {shot_event.x_values}")
                print()
    
    # Summary
    print(f"📊 Test Summary:")
    print(f"   Total samples processed: {sample_count}")
    print(f"   Shots detected: {len(shots_detected)}")
    print(f"   Expected shots: 6 (based on previous analysis)")
    
    stats = detector.get_stats()
    print(f"   Detector stats: {stats}")
    
    if len(shots_detected) == 6:
        print("✅ SUCCESS: Detected exactly 6 shots as expected!")
        return True
    else:
        print(f"⚠️  WARNING: Expected 6 shots, detected {len(shots_detected)}")
        return False

def test_shot_detector_synthetic():
    """Test shot detector with synthetic data to verify logic"""
    
    print("🧪 Testing shot detector with synthetic data...")
    
    detector = ShotDetector(baseline_x=2089, threshold=150, min_duration=6, max_duration=11)
    
    # Synthetic data: baseline -> spike -> baseline
    test_data = (
        [2089] * 10 +      # 10 samples at baseline
        [2089 + 200] * 8 + # 8 samples with 200 count spike (should detect)
        [2089] * 10 +      # 10 samples at baseline
        [2089 + 100] * 4 + # 4 samples with 100 count spike (too short)
        [2089] * 10 +      # 10 samples at baseline  
        [2089 + 180] * 15 + # 15 samples with 180 count spike (too long)
        [2089] * 10        # 10 samples at baseline
    )
    
    shots = []
    for i, x_value in enumerate(test_data):
        shot = detector.process_sample(x_value, i * 0.02)
        if shot:
            shots.append(shot)
            print(f"Synthetic shot detected: duration {shot.duration_samples}, deviation {shot.max_deviation}")
    
    print(f"Synthetic test: {len(shots)} shots detected (expected: 1)")
    return len(shots) == 1

if __name__ == "__main__":
    print("🚀 Shot Detection Integration Test")
    print("=" * 50)
    
    # Test with synthetic data first
    synthetic_ok = test_shot_detector_synthetic()
    print()
    
    # Test with real CSV data
    csv_ok = test_shot_detector_with_csv()
    print()
    
    if synthetic_ok and csv_ok:
        print("🎉 All tests passed! Shot detection is ready for live bridge integration.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please review the detector configuration.")
        sys.exit(1)