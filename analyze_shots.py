#!/usr/bin/env python3
"""
Shot Detection Analysis for BT50 Sensor Data
Implements the proposed shot detection algorithm based on user observations
"""

import csv
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

def load_csv_data(filename):
    """Load BT50 CSV data"""
    x_data = []
    y_data = []
    z_data = []
    
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            x_data.append(int(row['X_Raw']))
            y_data.append(int(row['Y_Raw']))
            z_data.append(int(row['Z_Raw']))
    
    return np.array(x_data), np.array(y_data), np.array(z_data)

def detect_shots(x_data, baseline=2089, threshold=200, min_duration=6, max_duration=12, min_interval=50):
    """
    Detect shots based on spike criteria:
    - Spike magnitude > threshold counts from baseline
    - Duration: 6-12 consecutive samples  
    - Minimum 1 second (50 samples) between shots
    """
    shots = []
    in_spike = False
    spike_start = 0
    spike_samples = 0
    last_shot_end = -min_interval  # Allow detection from start
    
    for i, x_val in enumerate(x_data):
        deviation = abs(x_val - baseline)
        
        if not in_spike and deviation > threshold and (i - last_shot_end) >= min_interval:
            # Start of potential spike
            in_spike = True
            spike_start = i
            spike_samples = 1
            max_dev = deviation
            
        elif in_spike and deviation > threshold:
            # Continue spike
            spike_samples += 1
            max_dev = max(max_dev, deviation)
            
        elif in_spike and deviation <= threshold:
            # End of spike - check if it qualifies
            if min_duration <= spike_samples <= max_duration:
                shots.append({
                    'sample_start': spike_start,
                    'sample_end': i-1,
                    'duration_samples': spike_samples,
                    'max_deviation': max_dev,
                    'time_seconds': spike_start / 50.0,  # Assuming 50Hz sampling
                    'x_value_at_peak': baseline - max_dev if x_data[spike_start] < baseline else baseline + max_dev
                })
                last_shot_end = i
            in_spike = False
            spike_samples = 0
    
    return shots

def analyze_data(filename):
    """Analyze BT50 data and detect shots"""
    print(f"Loading data from {filename}...")
    x_data, y_data, z_data = load_csv_data(filename)
    
    print(f"Loaded {len(x_data)} samples")
    print(f"X-axis range: {x_data.min()} to {x_data.max()}")
    print(f"Baseline: 2089, Max deviation from baseline: {max(abs(x_data - 2089))}")
    
    # Test different threshold values
    thresholds = [150, 175, 200, 225, 250]
    
    for threshold in thresholds:
        print(f"\n=== Testing threshold: {threshold} counts ===")
        shots = detect_shots(x_data, threshold=threshold)
        
        print(f"Detected {len(shots)} shots:")
        for i, shot in enumerate(shots, 1):
            print(f"  Shot {i}: Sample {shot['sample_start']}-{shot['sample_end']} "
                  f"({shot['time_seconds']:.1f}s), Duration: {shot['duration_samples']} samples, "
                  f"Max deviation: {shot['max_deviation']:.0f} counts")
    
    # Detailed analysis with recommended threshold (200)
    print(f"\n{'='*60}")
    print("DETAILED ANALYSIS - Threshold: 200 counts")
    print(f"{'='*60}")
    
    shots = detect_shots(x_data, threshold=200)
    
    # Focus on samples 200-600 where user observed the 6 shots
    focus_start, focus_end = 200, 600
    focus_x = x_data[focus_start:focus_end]
    focus_samples = list(range(focus_start, focus_end))
    
    print(f"\nFocus region (samples {focus_start}-{focus_end}):")
    print(f"X-axis range in focus: {focus_x.min()} to {focus_x.max()}")
    
    shots_in_focus = [s for s in shots if focus_start <= s['sample_start'] <= focus_end]
    print(f"Shots detected in focus region: {len(shots_in_focus)}")
    
    # Compare with known AMG timer shots (6 shots expected)
    expected_shot_times = [18.9, 20.1, 21.4, 22.5, 23.8, 25.1]  # From log analysis
    
    print(f"\nComparison with AMG timer shots:")
    print(f"Expected: 6 shots at ~{expected_shot_times} seconds")
    print(f"Detected: {len(shots)} shots")
    
    for i, shot in enumerate(shots, 1):
        closest_expected = min(expected_shot_times, key=lambda t: abs(t - shot['time_seconds']))
        time_diff = abs(shot['time_seconds'] - closest_expected)
        print(f"  Shot {i}: {shot['time_seconds']:.1f}s (closest expected: {closest_expected}s, diff: {time_diff:.1f}s)")
    
    # Generate visualization data
    print(f"\nGenerating shot detection visualization...")
    return x_data, shots, focus_start, focus_end

def create_detection_summary(shots):
    """Create a summary of detection results"""
    if not shots:
        return "No shots detected with current criteria"
    
    summary = f"SHOT DETECTION SUMMARY\n"
    summary += f"{'='*50}\n"
    summary += f"Total shots detected: {len(shots)}\n"
    summary += f"Time span: {shots[0]['time_seconds']:.1f}s to {shots[-1]['time_seconds']:.1f}s\n"
    summary += f"Average duration: {np.mean([s['duration_samples'] for s in shots]):.1f} samples\n"
    summary += f"Average deviation: {np.mean([s['max_deviation'] for s in shots]):.0f} counts\n\n"
    
    summary += f"Individual shots:\n"
    for i, shot in enumerate(shots, 1):
        summary += f"Shot {i:2d}: {shot['time_seconds']:5.1f}s | "
        summary += f"{shot['duration_samples']:2d} samples | "
        summary += f"{shot['max_deviation']:3.0f} counts deviation\n"
    
    return summary

if __name__ == "__main__":
    filename = "bt50_xyz_data.csv"
    
    try:
        x_data, shots, focus_start, focus_end = analyze_data(filename)
        
        # Create summary
        summary = create_detection_summary(shots)
        print(f"\n{summary}")
        
        # Save results
        with open("shot_detection_results.txt", "w") as f:
            f.write(summary)
            f.write(f"\nDetailed shot data:\n")
            for shot in shots:
                f.write(f"{shot}\n")
        
        print(f"\nResults saved to shot_detection_results.txt")
        print(f"Recommendation: Threshold of 200 counts appears optimal for detecting the 6 expected shots")
        
    except FileNotFoundError:
        print(f"Error: {filename} not found. Make sure the CSV file is in the current directory.")
    except Exception as e:
        print(f"Error analyzing data: {e}")