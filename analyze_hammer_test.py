#!/usr/bin/env python3
"""
Quick analysis of hammer test timing correlations
"""

import re
import sys
from datetime import datetime
from pathlib import Path

def analyze_hammer_test():
    """Analyze the hammer test data for timing correlations"""
    
    print("🔨 Hammer Test Timing Analysis")
    print("=" * 50)
    
    # Parse shots and impacts from the log
    shots = []
    impacts = []
    projections = []
    
    log_file = "/home/pi/projects/TinTown/logs/debug/bridge_debug_20250911_121309.log"
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Parse shots
                if "Timer DC:1A - Shot #" in line:
                    match = re.search(r"Shot #(\d+) at (\d{2}:\d{2}:\d{2}\.\d{3})", line)
                    if match:
                        shot_num = int(match.group(1))
                        time_str = match.group(2)
                        shots.append((shot_num, time_str))
                
                # Parse impact events
                elif "Enhanced impact:" in line:
                    # Extract timestamp and magnitude
                    match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3}).*onset (\d+\.\d+)g.*peak (\d+\.\d+)g", line)
                    if match:
                        timestamp = match.group(1).replace(',', '.')
                        onset_mag = float(match.group(2))
                        peak_mag = float(match.group(3))
                        impacts.append((timestamp, onset_mag, peak_mag))
                
                # Parse projections
                elif "Projected Impact:" in line:
                    match = re.search(r"Projected Impact: (\d{2}:\d{2}:\d{2}\.\d{3})", line)
                    if match:
                        proj_time = match.group(1)
                        projections.append(proj_time)
    
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return
    
    print(f"📊 Data Summary:")
    print(f"   Shots detected: {len(shots)}")
    print(f"   Impacts detected: {len(impacts)}")  
    print(f"   Projections made: {len(projections)}")
    print()
    
    if len(shots) > 0:
        print(f"🎯 Shot Details:")
        for i, (shot_num, time_str) in enumerate(shots[-10:]):  # Last 10 shots
            print(f"   Shot #{shot_num}: {time_str}")
        print()
    
    if len(impacts) > 0:
        print(f"💥 Impact Details (last 10):")
        for i, (timestamp, onset_mag, peak_mag) in enumerate(impacts[-10:]):
            print(f"   Impact {i+len(impacts)-9:2d}: {timestamp} - {onset_mag:6.1f}g → {peak_mag:6.1f}g")
        print()
    
    # Look for the variance mentioned by user
    print(f"🔍 Analysis Notes:")
    print(f"   • Total shots: {len(shots)} (expected ~35 from user)")
    print(f"   • Total impacts: {len(impacts)}")
    
    # Check for missing correlations
    if len(shots) > len(impacts):
        missing = len(shots) - len(impacts)
        print(f"   • Missing impacts: {missing} (timer detected sound but no BT50 impact above threshold)")
    elif len(impacts) > len(shots):
        extra = len(impacts) - len(shots)
        print(f"   • Extra impacts: {extra} (BT50 detected impact but timer missed sound)")
    
    # Look for double-tap around shot 28
    print(f"   • Looking for double-tap near shot 28...")
    shot_28_area = [(num, time) for num, time in shots if 26 <= num <= 30]
    if shot_28_area:
        print(f"     Shots 26-30: {shot_28_area}")
    
    print()
    print(f"📈 Correlation Success Rate: {min(len(shots), len(impacts))}/{max(len(shots), len(impacts))} = {min(len(shots), len(impacts))/max(len(shots), len(impacts))*100:.1f}%")

if __name__ == "__main__":
    analyze_hammer_test()