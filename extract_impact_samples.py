#!/usr/bin/env python3
"""
Impact Sample Data Extractor

Extracts and displays detailed sample data around impact events for strip chart analysis.
"""

import sys
import json
from datetime import datetime, timedelta
import re

def parse_log_timestamp(timestamp_str):
    """Parse log timestamp format"""
    try:
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
    except:
        return None

def extract_impact_samples(debug_log_path, impact_time_str, samples_before=40, samples_after=40):
    """
    Extract sample data around a specific impact event
    """
    
    # Parse target impact time
    target_time = None
    try:
        # Try parsing different time formats
        for fmt in ["%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"]:
            try:
                if fmt == "%H:%M:%S.%f":
                    # Add today's date
                    today = datetime.now().strftime("%Y-%m-%d")
                    target_time = datetime.strptime(f"{today} {impact_time_str}", f"%Y-%m-%d {fmt}")
                else:
                    target_time = datetime.strptime(impact_time_str, fmt)
                break
            except:
                continue
    except:
        print(f"Error: Could not parse impact time '{impact_time_str}'")
        return None
    
    if not target_time:
        print(f"Error: Invalid time format '{impact_time_str}'")
        return None
    
    print(f"🎯 Searching for samples around impact at {target_time.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"📊 Looking for {samples_before} samples before and {samples_after} samples after")
    
    # Time window to search (wider to catch all samples)
    start_window = target_time - timedelta(seconds=2)
    end_window = target_time + timedelta(seconds=2)
    
    samples = []
    
    try:
        with open(debug_log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Extract timestamp from log line
                timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                if not timestamp_match:
                    continue
                
                log_time = parse_log_timestamp(timestamp_match.group(1))
                if not log_time or log_time < start_window or log_time > end_window:
                    continue
                
                # Look for BT50 sample data with raw values
                if 'BT50 sample:' in line and 'vx_raw' in line:
                    # Extract raw and corrected values
                    # Format: "BT50 sample: 09:55:21.428 vx_raw=1995, vy_raw=41, vz_raw=0, magnitude=43.7"
                    try:
                        vx_match = re.search(r'vx_raw=(-?\d+)', line)
                        vy_match = re.search(r'vy_raw=(-?\d+)', line)
                        vz_match = re.search(r'vz_raw=(-?\d+)', line)
                        mag_match = re.search(r'magnitude=(-?\d+\.?\d*)', line)
                        
                        if all([vx_match, vy_match, vz_match, mag_match]):
                            sample_data = {
                                'timestamp': log_time,
                                'timestamp_str': log_time.strftime('%H:%M:%S.%f')[:-3],
                                'vx_raw': int(vx_match.group(1)),
                                'vy_raw': int(vy_match.group(1)),
                                'vz_raw': int(vz_match.group(1)),
                                'magnitude': float(mag_match.group(1)),
                                'time_offset_ms': (log_time - target_time).total_seconds() * 1000
                            }
                            samples.append(sample_data)
                    except Exception as e:
                        continue
    
    except FileNotFoundError:
        print(f"Error: Debug log file not found: {debug_log_path}")
        return None
    except Exception as e:
        print(f"Error reading log file: {e}")
        return None
    
    if not samples:
        print("❌ No sample data found around the specified impact time")
        print("   Make sure the debug log contains detailed BT50 notification data")
        return None
    
    # Sort samples by timestamp
    samples.sort(key=lambda x: x['timestamp'])
    
    # Find sample closest to impact time
    impact_sample_idx = -1
    min_time_diff = float('inf')
    
    for i, sample in enumerate(samples):
        time_diff = abs((sample['timestamp'] - target_time).total_seconds() * 1000)
        if time_diff < min_time_diff:
            min_time_diff = time_diff
            impact_sample_idx = i
    
    if impact_sample_idx == -1:
        print("❌ Could not find sample closest to impact time")
        return None
    
    # Extract samples around impact
    start_idx = max(0, impact_sample_idx - samples_before)
    end_idx = min(len(samples), impact_sample_idx + samples_after + 1)
    
    result_samples = samples[start_idx:end_idx]
    
    print(f"✅ Found {len(result_samples)} samples around impact")
    print(f"📍 Impact sample #{impact_sample_idx - start_idx + 1} of {len(result_samples)}")
    
    return {
        'impact_time': target_time,
        'impact_sample_index': impact_sample_idx - start_idx,
        'total_samples': len(result_samples),
        'samples': result_samples
    }

def create_strip_chart(sample_data):
    """Create a detailed strip chart of the impact event"""
    
    if not sample_data:
        return
    
    samples = sample_data['samples']
    impact_idx = sample_data['impact_sample_index']
    
    print("\n" + "="*120)
    print("🎯 IMPACT EVENT STRIP CHART")
    print("="*120)
    print(f"Impact Time: {sample_data['impact_time'].strftime('%H:%M:%S.%f')[:-3]}")
    print(f"Total Samples: {len(samples)} (Impact at sample #{impact_idx + 1})")
    print()
    
    # Header
    print(f"{'#':<3} {'Time':<12} {'Offset':<8} {'X_Raw':<6} {'Y_Raw':<6} {'Z_Raw':<6} {'Magnitude':<9} {'Notes'}")
    print("-" * 120)
    
    # Find peak magnitude for reference
    max_magnitude = max(s['magnitude'] for s in samples)
    peak_sample_idx = next(i for i, s in enumerate(samples) if s['magnitude'] == max_magnitude)
    
    for i, sample in enumerate(samples):
        # Sample number
        sample_num = f"{i+1:2d}"
        
        # Timestamp
        time_str = sample['timestamp_str']
        
        # Time offset from impact
        offset_ms = f"{sample['time_offset_ms']:+6.1f}ms"
        
        # Raw values
        x_raw = f"{sample['vx_raw']:5d}"
        y_raw = f"{sample['vy_raw']:5d}" 
        z_raw = f"{sample['vz_raw']:5d}"
        
        # Magnitude
        magnitude = f"{sample['magnitude']:7.1f}g"
        
        # Notes
        notes = ""
        if i == impact_idx:
            notes += "← IMPACT DETECTED"
        if i == peak_sample_idx:
            notes += "← PEAK MAGNITUDE" if not notes else " + PEAK"
        if sample['magnitude'] >= 150:
            notes += "← ABOVE PEAK THRESHOLD" if not notes else ""
        elif sample['magnitude'] >= 30:
            notes += "← ABOVE ONSET THRESHOLD" if not notes else ""
        
        print(f"{sample_num} {time_str} {offset_ms} {x_raw} {y_raw} {z_raw} {magnitude} {notes}")
    
    print("-" * 120)
    
    # Summary statistics
    print(f"\n📊 IMPACT ANALYSIS SUMMARY:")
    print(f"   Peak Magnitude: {max_magnitude:.1f}g (sample #{peak_sample_idx + 1})")
    print(f"   Impact Detection: Sample #{impact_idx + 1}")
    print(f"   Duration Analyzed: {samples[-1]['time_offset_ms'] - samples[0]['time_offset_ms']:.1f}ms")
    
    # Onset analysis
    onset_samples = [s for s in samples if s['magnitude'] >= 30 and s['magnitude'] < 150]
    if onset_samples:
        first_onset = onset_samples[0]
        onset_idx = next(i for i, s in enumerate(samples) if s == first_onset)
        print(f"   First Onset (30g+): Sample #{onset_idx + 1} at {first_onset['magnitude']:.1f}g")
    
    peak_samples = [s for s in samples if s['magnitude'] >= 150]
    if peak_samples:
        first_peak = peak_samples[0] 
        peak_threshold_idx = next(i for i, s in enumerate(samples) if s == first_peak)
        print(f"   First Peak (150g+): Sample #{peak_threshold_idx + 1} at {first_peak['magnitude']:.1f}g")
    
    print("="*120)

def export_sample_data(sample_data, format_type="csv", output_path=None):
    """Export sample data to various formats for further analysis"""
    
    if not sample_data:
        print("No sample data to export")
        return
    
    samples = sample_data['samples']
    impact_time = sample_data['impact_time']
    
    if not output_path:
        timestamp_str = impact_time.strftime('%Y%m%d_%H%M%S')
        output_path = f"impact_analysis_{timestamp_str}"
    
    if format_type.lower() == "csv":
        import csv
        csv_path = f"{output_path}.csv"
        
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=[
                'sample_num', 'timestamp', 'time_offset_ms', 
                'vx_raw', 'vy_raw', 'vz_raw', 'magnitude'
            ])
            writer.writeheader()
            
            for i, sample in enumerate(samples):
                writer.writerow({
                    'sample_num': i + 1,
                    'timestamp': sample['timestamp_str'],
                    'time_offset_ms': sample['time_offset_ms'],
                    'vx_raw': sample['vx_raw'],
                    'vy_raw': sample['vy_raw'], 
                    'vz_raw': sample['vz_raw'],
                    'magnitude': sample['magnitude']
                })
        
        print(f"✅ CSV data exported to: {csv_path}")
        
    elif format_type.lower() == "json":
        import json
        json_path = f"{output_path}.json"
        
        export_data = {
            'impact_analysis': {
                'impact_time': impact_time.isoformat(),
                'total_samples': len(samples),
                'impact_sample_index': sample_data['impact_sample_index'],
                'analysis_timestamp': datetime.now().isoformat()
            },
            'samples': samples
        }
        
        # Convert datetime objects to strings for JSON serialization
        for sample in export_data['samples']:
            sample['timestamp'] = sample['timestamp'].isoformat()
        
        with open(json_path, 'w') as jsonfile:
            json.dump(export_data, jsonfile, indent=2)
        
        print(f"✅ JSON data exported to: {json_path}")

def analyze_impact_waveform(sample_data):
    """Analyze impact waveform characteristics"""
    
    if not sample_data:
        return
    
    samples = sample_data['samples']
    impact_idx = sample_data['impact_sample_index']
    
    print("\n" + "="*80)
    print("📈 IMPACT WAVEFORM ANALYSIS")
    print("="*80)
    
    # Find key points in waveform
    magnitudes = [s['magnitude'] for s in samples]
    max_magnitude = max(magnitudes)
    max_idx = magnitudes.index(max_magnitude)
    
    # Find onset (first sample above 30g)
    onset_idx = -1
    for i, mag in enumerate(magnitudes):
        if mag >= 30.0:
            onset_idx = i
            break
    
    # Find return to baseline (first sample after peak below 30g)
    baseline_return_idx = -1
    for i in range(max_idx + 1, len(magnitudes)):
        if magnitudes[i] < 30.0:
            baseline_return_idx = i
            break
    
    if onset_idx >= 0 and baseline_return_idx >= 0:
        # Calculate waveform metrics
        onset_time = samples[onset_idx]['timestamp']
        peak_time = samples[max_idx]['timestamp']
        baseline_time = samples[baseline_return_idx]['timestamp']
        
        rise_time = (peak_time - onset_time).total_seconds() * 1000
        fall_time = (baseline_time - peak_time).total_seconds() * 1000
        total_duration = (baseline_time - onset_time).total_seconds() * 1000
        
        print(f"🎯 Waveform Characteristics:")
        print(f"   Onset Sample: #{onset_idx + 1} at {samples[onset_idx]['magnitude']:.1f}g")
        print(f"   Peak Sample:  #{max_idx + 1} at {max_magnitude:.1f}g")
        print(f"   Return Sample: #{baseline_return_idx + 1} at {samples[baseline_return_idx]['magnitude']:.1f}g")
        print(f"   Rise Time: {rise_time:.1f}ms")
        print(f"   Fall Time: {fall_time:.1f}ms") 
        print(f"   Total Duration: {total_duration:.1f}ms")
        
        # Peak-to-onset ratio
        onset_magnitude = samples[onset_idx]['magnitude']
        peak_ratio = max_magnitude / max(onset_magnitude, 1.0)
        print(f"   Peak/Onset Ratio: {peak_ratio:.1f}x")
        
        # Impact energy (simplified area under curve)
        impact_energy = sum(magnitudes[onset_idx:baseline_return_idx + 1])
        print(f"   Impact Energy (area): {impact_energy:.1f}")
        
    print("="*80)

def analyze_multi_shot_correlation(log_path, window_minutes=5):
    """Analyze multiple shot-impact correlations from a log session"""
    
    print(f"\n🎯 ANALYZING MULTI-SHOT CORRELATION from {log_path}")
    print(f"Looking for shots and impacts within {window_minutes} minute window")
    
    # This would extract all shot and impact events from the log
    # and analyze correlation patterns, timing consistency, etc.
    # Implementation would be similar to extract_impact_samples but for multiple events
    
    print("📊 Multi-shot correlation analysis - Feature placeholder")
    print("   This feature would analyze:")
    print("   • Multiple shot-impact pairs")
    print("   • Timing consistency across shots")
    print("   • Impact magnitude variations")
    print("   • Correlation confidence trends")
    print("   • System performance metrics")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 extract_impact_samples.py <debug_log_path> <impact_time> [options]")
        print("Example: python3 extract_impact_samples.py logs/debug/bridge_debug_20250911_094814.log 09:48:28.867")
        print("")
        print("Options:")
        print("  --export-csv              Export data to CSV format")
        print("  --export-json             Export data to JSON format")
        print("  --waveform-analysis       Perform detailed waveform analysis")
        print("  --multi-shot              Analyze multiple shot correlations")
        sys.exit(1)
    
    debug_log_path = sys.argv[1]
    impact_time = sys.argv[2]
    
    # Parse command line options
    export_csv = "--export-csv" in sys.argv
    export_json = "--export-json" in sys.argv
    waveform_analysis = "--waveform-analysis" in sys.argv
    multi_shot = "--multi-shot" in sys.argv
    
    print(f"🔍 Extracting impact samples from: {debug_log_path}")
    print(f"🎯 Impact time: {impact_time}")
    
    if multi_shot:
        # Analyze multiple shots instead of single impact
        analyze_multi_shot_correlation(debug_log_path)
        sys.exit(0)
    
    # Extract sample data
    sample_data = extract_impact_samples(debug_log_path, impact_time)
    
    if sample_data:
        # Create strip chart
        create_strip_chart(sample_data)
        
        # Optional waveform analysis
        if waveform_analysis:
            analyze_impact_waveform(sample_data)
        
        # Optional data export
        if export_csv:
            export_sample_data(sample_data, "csv")
        
        if export_json:
            export_sample_data(sample_data, "json")
            
    else:
        print("❌ Failed to extract sample data")
        sys.exit(1)