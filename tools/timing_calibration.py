#!/usr/bin/env python3
"""
TinTown Timing Calibration Analysis Tool

This tool analyzes timing patterns between AMG timer events and BT50 sensor impacts
to establish accurate correlation parameters for shot-impact pairing.

Features:
- Parse existing log files for timing data
- Real-time timing analysis during live sessions
- Statistical analysis of delay patterns
- Calibration parameter generation
- Validation testing framework

Usage:
    python timing_calibration.py --analyze logs/
    python timing_calibration.py --live --calibrate
    python timing_calibration.py --test --shots 10
"""

import argparse
import csv
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import sys


class TimingEvent:
    """Represents a timestamped event (timer or sensor)."""
    
    def __init__(self, timestamp: datetime, event_type: str, device_type: str, 
                 device_id: str, details: str, magnitude: float = None):
        self.timestamp = timestamp
        self.event_type = event_type  # 'shot', 'impact', 'status'
        self.device_type = device_type  # 'Timer', 'Sensor'
        self.device_id = device_id
        self.details = details
        self.magnitude = magnitude
        
    def __repr__(self):
        return f"TimingEvent({self.timestamp}, {self.event_type}, {self.device_type}, {self.details})"


class ShotImpactPair:
    """Represents a correlated shot-impact pair."""
    
    def __init__(self, shot_event: TimingEvent, impact_event: TimingEvent):
        self.shot_event = shot_event
        self.impact_event = impact_event
        self.delay_ms = int((impact_event.timestamp - shot_event.timestamp).total_seconds() * 1000)
        
    def __repr__(self):
        return f"Pair(shot={self.shot_event.timestamp}, impact={self.impact_event.timestamp}, delay={self.delay_ms}ms)"


class TimingAnalyzer:
    """Analyzes timing patterns between timer and sensor events."""
    
    def __init__(self):
        self.events: List[TimingEvent] = []
        self.pairs: List[ShotImpactPair] = []
        self.timing_window_ms = 2000  # Default 2-second correlation window
        
    def parse_log_file(self, log_path: Path) -> int:
        """Parse a log file and extract timing events."""
        events_found = 0
        
        if log_path.suffix.lower() == '.csv':
            events_found = self._parse_csv_log(log_path)
        elif log_path.suffix.lower() == '.ndjson':
            events_found = self._parse_ndjson_log(log_path)
        else:
            print(f"Warning: Unsupported log format: {log_path}")
            
        return events_found
    
    def _parse_csv_log(self, log_path: Path) -> int:
        """Parse CSV format logs."""
        events_found = 0
        
        try:
            with open(log_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    event = self._extract_event_from_csv_row(row)
                    if event:
                        self.events.append(event)
                        events_found += 1
        except Exception as e:
            print(f"Error parsing CSV log {log_path}: {e}")
            
        return events_found
    
    def _parse_ndjson_log(self, log_path: Path) -> int:
        """Parse NDJSON format logs."""
        events_found = 0
        
        try:
            with open(log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        event = self._extract_event_from_json(data)
                        if event:
                            self.events.append(event)
                            events_found += 1
        except Exception as e:
            print(f"Error parsing NDJSON log {log_path}: {e}")
            
        return events_found
    
    def _extract_event_from_csv_row(self, row: Dict) -> Optional[TimingEvent]:
        """Extract timing event from CSV row."""
        try:
            # Parse timestamp from CSV datetime format
            dt_str = row.get('Datetime', '').replace('am', ' AM').replace('pm', ' PM')
            timestamp = datetime.strptime(dt_str, '%m/%d/%y %I:%M:%S.%f %p')
            
            device_type = row.get('Device', '')
            device_id = row.get('DeviceID', '')
            details = row.get('Details', '')
            
            # Determine event type from details
            event_type = self._classify_event(details, device_type)
            
            if event_type in ['shot', 'impact']:
                # Extract magnitude for impact events
                magnitude = self._extract_magnitude(details) if event_type == 'impact' else None
                
                return TimingEvent(
                    timestamp=timestamp,
                    event_type=event_type,
                    device_type=device_type,
                    device_id=device_id,
                    details=details,
                    magnitude=magnitude
                )
                
        except Exception as e:
            print(f"Error extracting event from CSV row: {e}")
            
        return None
    
    def _extract_event_from_json(self, data: Dict) -> Optional[TimingEvent]:
        """Extract timing event from JSON data."""
        try:
            # Parse ISO timestamp
            timestamp_str = data.get('timestamp_iso', '')
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            device_type = data.get('device', '')
            device_id = data.get('device_id', '')
            
            # Check for different event patterns in JSON
            if data.get('type') == 'amg_parsed':
                # Timer shot event
                amg_data = data.get('data', {})
                if 'shot_number' in amg_data:
                    return TimingEvent(
                        timestamp=timestamp,
                        event_type='shot',
                        device_type='Timer',
                        device_id=device_id,
                        details=f"Shot #{amg_data['shot_number']}"
                    )
                    
            elif data.get('type') == 'bt50_parsed':
                # Sensor impact event
                bt50_data = data.get('data', {})
                magnitude = bt50_data.get('mag', 0)
                
                if magnitude > 0.1:  # Threshold for significant impact
                    return TimingEvent(
                        timestamp=timestamp,
                        event_type='impact',
                        device_type='Sensor',
                        device_id=device_id,
                        details=f"Impact magnitude {magnitude:.3f}",
                        magnitude=magnitude
                    )
                    
        except Exception as e:
            print(f"Error extracting event from JSON: {e}")
            
        return None
    
    def _classify_event(self, details: str, device_type: str) -> str:
        """Classify event type based on details and device."""
        details_lower = details.lower()
        
        if device_type == 'Timer':
            if 'shot' in details_lower:
                return 'shot'
        elif device_type == 'Sensor':
            if 'impact' in details_lower or 'detected' in details_lower:
                return 'impact'
                
        return 'status'
    
    def _extract_magnitude(self, details: str) -> Optional[float]:
        """Extract magnitude value from impact details."""
        # Look for patterns like "Mag = 220" or "magnitude 1.234"
        mag_patterns = [
            r'mag\s*=\s*([\d.]+)',
            r'magnitude\s+([\d.]+)',
            r'impact\s+([\d.]+)'
        ]
        
        for pattern in mag_patterns:
            match = re.search(pattern, details.lower())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
                    
        return None
    
    def correlate_events(self) -> List[ShotImpactPair]:
        """Correlate shot events with impact events within timing window."""
        self.pairs.clear()
        
        # Sort events by timestamp
        shot_events = sorted([e for e in self.events if e.event_type == 'shot'], 
                           key=lambda x: x.timestamp)
        impact_events = sorted([e for e in self.events if e.event_type == 'impact'], 
                             key=lambda x: x.timestamp)
        
        print(f"Found {len(shot_events)} shot events and {len(impact_events)} impact events")
        
        # Correlate shots with impacts
        used_impacts = set()
        
        for shot in shot_events:
            best_impact = None
            best_delay = float('inf')
            
            # Look for impacts within timing window after shot
            window_end = shot.timestamp + timedelta(milliseconds=self.timing_window_ms)
            
            for i, impact in enumerate(impact_events):
                if i in used_impacts:
                    continue
                    
                if impact.timestamp < shot.timestamp:
                    continue
                    
                if impact.timestamp > window_end:
                    break
                    
                delay_ms = (impact.timestamp - shot.timestamp).total_seconds() * 1000
                
                if delay_ms < best_delay:
                    best_delay = delay_ms
                    best_impact = (i, impact)
            
            if best_impact:
                used_impacts.add(best_impact[0])
                pair = ShotImpactPair(shot, best_impact[1])
                self.pairs.append(pair)
                
        return self.pairs
    
    def analyze_timing_statistics(self) -> Dict:
        """Analyze timing statistics from correlated pairs."""
        if not self.pairs:
            return {"error": "No correlated pairs found"}
        
        delays = [pair.delay_ms for pair in self.pairs]
        magnitudes = [pair.impact_event.magnitude for pair in self.pairs if pair.impact_event.magnitude]
        
        stats = {
            "pair_count": len(self.pairs),
            "delay_stats": {
                "min_ms": min(delays),
                "max_ms": max(delays),
                "mean_ms": statistics.mean(delays),
                "median_ms": statistics.median(delays),
                "stdev_ms": statistics.stdev(delays) if len(delays) > 1 else 0
            }
        }
        
        if magnitudes:
            stats["magnitude_stats"] = {
                "min": min(magnitudes),
                "max": max(magnitudes),
                "mean": statistics.mean(magnitudes),
                "median": statistics.median(magnitudes)
            }
        
        # Calculate recommended correlation window
        if len(delays) > 1:
            mean_delay = stats["delay_stats"]["mean_ms"]
            stdev_delay = stats["delay_stats"]["stdev_ms"]
            recommended_window = mean_delay + (3 * stdev_delay)  # 3-sigma window
            stats["recommended_window_ms"] = int(recommended_window)
        
        return stats
    
    def generate_calibration_config(self) -> Dict:
        """Generate calibration configuration based on analysis."""
        stats = self.analyze_timing_statistics()
        
        if "error" in stats:
            return stats
        
        config = {
            "timing_calibration": {
                "correlation_window_ms": stats.get("recommended_window_ms", 1000),
                "expected_delay_ms": int(stats["delay_stats"]["mean_ms"]),
                "delay_tolerance_ms": int(stats["delay_stats"]["stdev_ms"] * 2),
                "minimum_magnitude": stats.get("magnitude_stats", {}).get("median", 0.1),
                "analysis_date": datetime.now().isoformat(),
                "sample_count": stats["pair_count"]
            }
        }
        
        return config
    
    def print_analysis_report(self):
        """Print comprehensive analysis report."""
        print(f"\n{'='*60}")
        print("TIMING CALIBRATION ANALYSIS REPORT")
        print(f"{'='*60}")
        
        print(f"Total events parsed: {len(self.events)}")
        shot_count = len([e for e in self.events if e.event_type == 'shot'])
        impact_count = len([e for e in self.events if e.event_type == 'impact'])
        print(f"  - Shot events: {shot_count}")
        print(f"  - Impact events: {impact_count}")
        
        if self.pairs:
            print(f"\nCorrelated pairs: {len(self.pairs)}")
            
            stats = self.analyze_timing_statistics()
            delay_stats = stats["delay_stats"]
            
            print(f"\nTiming Delay Statistics:")
            print(f"  - Mean delay: {delay_stats['mean_ms']:.1f} ms")
            print(f"  - Median delay: {delay_stats['median_ms']:.1f} ms")
            print(f"  - Min/Max delay: {delay_stats['min_ms']:.1f} - {delay_stats['max_ms']:.1f} ms")
            print(f"  - Standard deviation: {delay_stats['stdev_ms']:.1f} ms")
            
            if "magnitude_stats" in stats:
                mag_stats = stats["magnitude_stats"]
                print(f"\nImpact Magnitude Statistics:")
                print(f"  - Mean magnitude: {mag_stats['mean']:.3f}")
                print(f"  - Min/Max magnitude: {mag_stats['min']:.3f} - {mag_stats['max']:.3f}")
            
            if "recommended_window_ms" in stats:
                print(f"\nRecommended correlation window: {stats['recommended_window_ms']} ms")
            
            print(f"\nDetailed Pairs:")
            for i, pair in enumerate(self.pairs[:10]):  # Show first 10
                print(f"  {i+1}. {pair.delay_ms:4d}ms delay - Mag: {pair.impact_event.magnitude:.3f}")
            
            if len(self.pairs) > 10:
                print(f"  ... and {len(self.pairs) - 10} more pairs")
                
        else:
            print("\nNo correlated shot-impact pairs found!")
            print("This could indicate:")
            print("  - No simultaneous timer and sensor data")
            print("  - Timing window too narrow")
            print("  - Different log sessions")
    
    def export_calibration_config(self, output_path: Path):
        """Export calibration configuration to file."""
        config = self.generate_calibration_config()
        
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\nCalibration config exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="TinTown Timing Calibration Analysis Tool")
    parser.add_argument("--analyze", metavar="LOG_DIR", help="Analyze existing log files")
    parser.add_argument("--window", type=int, default=2000, help="Correlation window in ms (default: 2000)")
    parser.add_argument("--output", default="timing_calibration.json", help="Output config file")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    analyzer = TimingAnalyzer()
    analyzer.timing_window_ms = args.window
    
    if args.analyze:
        log_dir = Path(args.analyze)
        
        if not log_dir.exists():
            print(f"Error: Log directory not found: {log_dir}")
            sys.exit(1)
        
        print(f"Analyzing logs in: {log_dir}")
        print(f"Correlation window: {args.window} ms")
        
        # Find and parse log files
        log_files = []
        for pattern in ['*.csv', '*.ndjson']:
            log_files.extend(log_dir.glob(f"**/{pattern}"))
        
        total_events = 0
        for log_file in log_files:
            events = analyzer.parse_log_file(log_file)
            total_events += events
            if args.verbose:
                print(f"  {log_file.name}: {events} events")
        
        print(f"Total events parsed: {total_events}")
        
        # Correlate and analyze
        analyzer.correlate_events()
        analyzer.print_analysis_report()
        
        # Export configuration
        output_path = Path(args.output)
        analyzer.export_calibration_config(output_path)
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()