#!/usr/bin/env python3
"""
Extract BT50 sensor data from debug log and create CSV
"""

import re
import csv
from datetime import datetime

# Read the debug log
with open('debug_latest.log', 'r') as f:
    log_content = f.read()

# Pattern to match BT50 RAW data lines
pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - FixedBridge - INFO - BT50 RAW: \[(\d+),(\d+),(\d+)\]'

# Find all matches
matches = re.findall(pattern, log_content)

print(f"Found {len(matches)} BT50 data points")

# Create CSV file
csv_file = 'bt50_sensor_data.csv'
with open(csv_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    
    # Write header
    writer.writerow(['Timestamp', 'X_Raw', 'Y_Raw', 'Z_Raw', 'X_Corrected', 'Y_Corrected', 'Z_Corrected', 'Magnitude'])
    
    # Baseline values for correction
    BASELINE_X = 2089
    BASELINE_Y = 0
    BASELINE_Z = 0
    
    # Write data rows
    for i, (timestamp_str, x_raw, y_raw, z_raw) in enumerate(matches):
        # Convert to integers
        x_raw = int(x_raw)
        y_raw = int(y_raw)
        z_raw = int(z_raw)
        
        # Calculate corrected values (baseline subtraction)
        x_corrected = x_raw - BASELINE_X
        y_corrected = y_raw - BASELINE_Y
        z_corrected = z_raw - BASELINE_Z
        
        # Calculate magnitude
        magnitude = (x_corrected**2 + y_corrected**2 + z_corrected**2)**0.5
        
        # Parse timestamp and convert to relative time in seconds
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
        if i == 0:
            start_time = dt
        relative_time = (dt - start_time).total_seconds()
        
        writer.writerow([
            relative_time,  # Time in seconds from start
            x_raw,
            y_raw, 
            z_raw,
            x_corrected,
            y_corrected,
            z_corrected,
            round(magnitude, 1)
        ])

print(f"Created {csv_file} with {len(matches)} data points")
print("Columns: Timestamp(seconds), X_Raw, Y_Raw, Z_Raw, X_Corrected, Y_Corrected, Z_Corrected, Magnitude")