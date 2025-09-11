#!/usr/bin/env python3
"""
Statistical Offset Analysis for BT50 Sensor Timing Calibration

Analyzes large sample test data to calculate statistical offsets and confidence intervals
for accurate impact time projection.
"""

import re
import statistics
from datetime import datetime
import json

def parse_timestamp(timestamp_str):
    """Parse HH:MM:SS.mmm timestamp"""
    try:
        return datetime.strptime(f"2025-09-11 {timestamp_str}", "%Y-%m-%d %H:%M:%S.%f")
    except:
        try:
            return datetime.strptime(f"2025-09-11 {timestamp_str}", "%Y-%m-%d %H:%M:%S")
        except:
            return None

def analyze_timing_correlation(log_file):
    """Analyze shot-impact timing correlation from log file"""
    
    shots = []
    impacts = []
    
    print(f"🔍 Analyzing timing data from: {log_file}")
    
    # Extract shot data
    with open(log_file, 'r') as f:
        for line in f:
            # Shot pattern: Shot #N at HH:MM:SS.mmm (timer: X.XXs)
            shot_match = re.search(r'Shot #(\d+) at (\d+:\d+:\d+\.\d+) \(timer: ([\d.]+)s\)', line)
            if shot_match:
                shot_num = int(shot_match.group(1))
                timestamp_str = shot_match.group(2)
                timer_split = float(shot_match.group(3))
                timestamp = parse_timestamp(timestamp_str)
                if timestamp:
                    shots.append({
                        'number': shot_num,
                        'timestamp': timestamp,
                        'timer_split': timer_split
                    })
            
            # Impact pattern: Onset: HH:MM:SS.mmm (XXX.Xg)
            impact_match = re.search(r'Onset: (\d+:\d+:\d+\.\d+) \(([\d.]+)g\)', line)
            if impact_match:
                timestamp_str = impact_match.group(1)
                magnitude = float(impact_match.group(2))
                timestamp = parse_timestamp(timestamp_str)
                if timestamp:
                    impacts.append({
                        'timestamp': timestamp,
                        'magnitude': magnitude
                    })
    
    print(f"📊 Found {len(shots)} shots and {len(impacts)} impacts")
    
    # Correlate shots with impacts
    correlations = []
    for shot in shots:
        # Find closest impact within reasonable time window (±500ms)
        closest_impact = None
        min_delay = float('inf')
        
        for impact in impacts:
            delay_ms = (impact['timestamp'] - shot['timestamp']).total_seconds() * 1000
            if 0 <= delay_ms <= 500 and delay_ms < min_delay:  # Impact after shot, within 500ms
                min_delay = delay_ms
                closest_impact = impact
        
        if closest_impact:
            correlations.append({
                'shot_number': shot['number'],
                'shot_time': shot['timestamp'],
                'impact_time': closest_impact['timestamp'],
                'delay_ms': min_delay,
                'magnitude': closest_impact['magnitude'],
                'timer_split': shot['timer_split']
            })
    
    return correlations

def calculate_statistics(correlations):
    """Calculate statistical measures from correlation data"""
    
    if not correlations:
        print("❌ No correlations found!")
        return None
    
    delays = [c['delay_ms'] for c in correlations]
    magnitudes = [c['magnitude'] for c in correlations]
    
    stats = {
        'sample_size': len(correlations),
        'delay_mean': statistics.mean(delays),
        'delay_median': statistics.median(delays),
        'delay_std_dev': statistics.stdev(delays) if len(delays) > 1 else 0,
        'delay_min': min(delays),
        'delay_max': max(delays),
        'magnitude_mean': statistics.mean(magnitudes),
        'magnitude_std_dev': statistics.stdev(magnitudes) if len(magnitudes) > 1 else 0
    }
    
    # Calculate confidence intervals (95% = ±1.96 * std_dev)
    stats['confidence_95_lower'] = stats['delay_mean'] - (1.96 * stats['delay_std_dev'])
    stats['confidence_95_upper'] = stats['delay_mean'] + (1.96 * stats['delay_std_dev'])
    stats['confidence_68_lower'] = stats['delay_mean'] - stats['delay_std_dev']
    stats['confidence_68_upper'] = stats['delay_mean'] + stats['delay_std_dev']
    
    return stats, correlations

def print_analysis_report(stats, correlations):
    """Print comprehensive analysis report"""
    
    print("\n" + "="*80)
    print("🎯 STATISTICAL OFFSET ANALYSIS REPORT")
    print("="*80)
    
    print(f"\n📊 SAMPLE DATA:")
    print(f"   Total Correlations: {stats['sample_size']}")
    print(f"   Delay Range: {stats['delay_min']:.1f}ms - {stats['delay_max']:.1f}ms")
    print(f"   Impact Magnitude: {stats['magnitude_mean']:.1f}g ± {stats['magnitude_std_dev']:.1f}g")
    
    print(f"\n⏱️  TIMING OFFSET STATISTICS:")
    print(f"   Mean Delay: {stats['delay_mean']:.1f}ms")
    print(f"   Median Delay: {stats['delay_median']:.1f}ms")
    print(f"   Standard Deviation: {stats['delay_std_dev']:.1f}ms")
    
    print(f"\n🎯 CONFIDENCE INTERVALS:")
    print(f"   68% Confidence: {stats['confidence_68_lower']:.1f}ms - {stats['confidence_68_upper']:.1f}ms")
    print(f"   95% Confidence: {stats['confidence_95_lower']:.1f}ms - {stats['confidence_95_upper']:.1f}ms")
    
    print(f"\n🚀 RECOMMENDED OFFSET:")
    print(f"   Primary Offset: {stats['delay_mean']:.0f}ms")
    print(f"   Uncertainty: ±{stats['delay_std_dev']:.0f}ms")
    print(f"   Timing Accuracy: ±{stats['delay_std_dev']:.0f}ms (1σ)")
    
    # Quality assessment
    if stats['delay_std_dev'] < 15:
        quality = "Excellent"
    elif stats['delay_std_dev'] < 25:
        quality = "Good"
    elif stats['delay_std_dev'] < 35:
        quality = "Fair"
    else:
        quality = "Poor"
    
    print(f"\n📈 DATA QUALITY: {quality}")
    print(f"   Consistency: {100 - (stats['delay_std_dev']/stats['delay_mean']*100):.1f}%")
    
    # Show first 10 correlations as examples
    print(f"\n📋 SAMPLE CORRELATIONS (first 10):")
    print("    Shot#  AMG Time     Impact Time   Delay   Magnitude")
    print("    " + "-"*60)
    for i, corr in enumerate(correlations[:10]):
        shot_time = corr['shot_time'].strftime('%H:%M:%S.%f')[:-3]
        impact_time = corr['impact_time'].strftime('%H:%M:%S.%f')[:-3]
        print(f"    #{corr['shot_number']:2d}    {shot_time}  {impact_time}  {corr['delay_ms']:5.1f}ms  {corr['magnitude']:6.1f}g")
    
    if len(correlations) > 10:
        print(f"    ... and {len(correlations) - 10} more correlations")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 statistical_offset_analysis.py <log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    # Analyze correlations
    correlations = analyze_timing_correlation(log_file)
    
    if not correlations:
        print("❌ No valid correlations found!")
        sys.exit(1)
    
    # Calculate statistics
    stats, correlations = calculate_statistics(correlations)
    
    # Print report
    print_analysis_report(stats, correlations)
    
    # Save detailed results
    output_file = f"timing_offset_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Convert datetime objects to strings for JSON serialization
    json_correlations = []
    for corr in correlations:
        json_corr = corr.copy()
        json_corr['shot_time'] = corr['shot_time'].isoformat()
        json_corr['impact_time'] = corr['impact_time'].isoformat()
        json_correlations.append(json_corr)
    
    output_data = {
        'statistics': stats,
        'correlations': json_correlations,
        'analysis_timestamp': datetime.now().isoformat()
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n📄 Detailed analysis saved to: {output_file}")