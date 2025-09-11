#!/usr/bin/env python3
"""
Real-time Timing Capture for TinTown Bridge

This tool connects to the TinTown bridge to capture live timing data
for shot-impact correlation analysis and calibration.

Features:
- Real-time event capture from bridge logs
- Live timing analysis and statistics
- Automatic correlation window adjustment
- Export timing data for analysis
- Visual timing feedback

Usage:
    python timing_capture.py --duration 300 --output test_session.json
    python timing_capture.py --live --shots 10 --analysis
"""

import argparse
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
import subprocess
import os
import sys


class RealTimeTimingCapture:
    """Captures timing data from live TinTown bridge sessions."""
    
    def __init__(self):
        self.shot_events = deque(maxlen=100)  # Keep last 100 shots
        self.impact_events = deque(maxlen=1000)  # Keep last 1000 impacts
        self.correlations = []
        self.session_start = None
        self.is_running = False
        self.correlation_window_ms = 1500  # Start with 1.5 seconds
        
        # Statistics
        self.stats = {
            'shots_detected': 0,
            'impacts_detected': 0,
            'pairs_correlated': 0,
            'avg_delay_ms': 0,
            'session_duration': 0
        }
    
    def start_capture(self, duration_seconds: Optional[int] = None):
        """Start real-time capture session."""
        self.session_start = datetime.now()
        self.is_running = True
        
        print(f"🎯 Starting timing capture session at {self.session_start}")
        print(f"📊 Correlation window: {self.correlation_window_ms} ms")
        
        if duration_seconds:
            print(f"⏱️  Session duration: {duration_seconds} seconds")
            # Set up auto-stop timer
            timer = threading.Timer(duration_seconds, self.stop_capture)
            timer.start()
        
        print("🔍 Monitoring for timer and sensor events...")
        print("   Use Ctrl+C to stop manual capture")
        
        try:
            self._monitor_logs()
        except KeyboardInterrupt:
            print("\n🛑 Manual stop requested")
        finally:
            self.stop_capture()
    
    def stop_capture(self):
        """Stop capture session and show results."""
        if not self.is_running:
            return
            
        self.is_running = False
        end_time = datetime.now()
        
        if self.session_start:
            self.stats['session_duration'] = (end_time - self.session_start).total_seconds()
        
        print(f"\n📊 CAPTURE SESSION COMPLETE")
        print(f"{'='*50}")
        self._print_session_statistics()
        
    def _monitor_logs(self):
        """Monitor TinTown bridge logs for timing events."""
        # This would connect to the live bridge logs
        # For now, we'll simulate or read from a log tail
        
        # Look for active log files
        log_dirs = [
            Path("logs/main"),
            Path("logs/debug"), 
            Path(".")  # Current directory
        ]
        
        active_log = None
        for log_dir in log_dirs:
            if log_dir.exists():
                # Find newest log file
                log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.ndjson"))
                if log_files:
                    active_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    break
        
        if not active_log:
            print("⚠️  No active log files found. Starting simulation mode...")
            self._simulate_events()
            return
        
        print(f"📁 Monitoring log file: {active_log}")
        
        # Tail the log file
        try:
            if sys.platform == "win32":
                # Use PowerShell Get-Content for Windows
                cmd = f'powershell.exe Get-Content "{active_log}" -Wait -Tail 0'
            else:
                # Use tail for Unix-like systems
                cmd = f'tail -f "{active_log}"'
            
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, universal_newlines=True)
            
            while self.is_running:
                line = process.stdout.readline()
                if line:
                    self._process_log_line(line.strip())
                else:
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Error monitoring logs: {e}")
            print("🔄 Falling back to simulation mode...")
            self._simulate_events()
    
    def _process_log_line(self, line: str):
        """Process a single log line for timing events."""
        try:
            # Try to parse as JSON (NDJSON format)
            if line.startswith('{'):
                data = json.loads(line)
                self._extract_event_from_json(data)
            else:
                # Try to parse as console output
                self._extract_event_from_console(line)
                
        except json.JSONDecodeError:
            # Not JSON, try console format
            self._extract_event_from_console(line)
        except Exception as e:
            # Skip problematic lines
            pass
    
    def _extract_event_from_json(self, data: Dict):
        """Extract timing event from JSON log entry."""
        try:
            timestamp_str = data.get('timestamp_iso', '')
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            device_type = data.get('device', '')
            device_id = data.get('device_id', '')
            
            # Timer shot event
            if data.get('type') == 'amg_parsed':
                amg_data = data.get('data', {})
                if 'shot_number' in amg_data:
                    shot_num = amg_data['shot_number']
                    event = {
                        'timestamp': timestamp,
                        'type': 'shot',
                        'device_id': device_id,
                        'shot_number': shot_num,
                        'details': f"Shot #{shot_num}"
                    }
                    self.shot_events.append(event)
                    self.stats['shots_detected'] += 1
                    print(f"🎯 Shot #{shot_num} detected at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
                    self._check_for_correlations()
                    
            # Sensor impact event  
            elif data.get('type') == 'bt50_parsed':
                bt50_data = data.get('data', {})
                magnitude = bt50_data.get('mag', 0)
                
                if magnitude > 0.1:  # Significant impact threshold
                    event = {
                        'timestamp': timestamp,
                        'type': 'impact',
                        'device_id': device_id,
                        'magnitude': magnitude,
                        'details': f"Impact {magnitude:.3f}g"
                    }
                    self.impact_events.append(event)
                    self.stats['impacts_detected'] += 1
                    print(f"💥 Impact {magnitude:.3f}g detected at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
                    self._check_for_correlations()
                    
        except Exception as e:
            pass  # Skip problematic entries
    
    def _extract_event_from_console(self, line: str):
        """Extract timing event from console log line."""
        # Look for console patterns like:
        # [21:01:04.506] 📝 String: Timer DC:1A - Shot #1
        # [21:01:04.961] 📝 Impact Detected: Sensor 12:E3 Mag = 220
        
        import re
        
        # Extract timestamp
        timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]', line)
        if not timestamp_match:
            return
        
        time_str = timestamp_match.group(1)
        # Assume today's date
        today = datetime.now().date()
        timestamp = datetime.combine(today, datetime.strptime(time_str, '%H:%M:%S.%f').time())
        
        # Shot events
        shot_match = re.search(r'Shot #(\d+)', line, re.IGNORECASE)
        if shot_match:
            shot_num = int(shot_match.group(1))
            event = {
                'timestamp': timestamp,
                'type': 'shot',
                'device_id': 'console',
                'shot_number': shot_num,
                'details': f"Shot #{shot_num}"
            }
            self.shot_events.append(event)
            self.stats['shots_detected'] += 1
            print(f"🎯 Shot #{shot_num} detected at {time_str}")
            self._check_for_correlations()
            return
        
        # Impact events  
        impact_match = re.search(r'Impact.*Mag\s*=\s*([\d.]+)', line, re.IGNORECASE)
        if impact_match:
            magnitude = float(impact_match.group(1))
            event = {
                'timestamp': timestamp,
                'type': 'impact',
                'device_id': 'console',
                'magnitude': magnitude,
                'details': f"Impact {magnitude}mg"
            }
            self.impact_events.append(event)
            self.stats['impacts_detected'] += 1
            print(f"💥 Impact {magnitude}mg detected at {time_str}")
            self._check_for_correlations()
            return
    
    def _check_for_correlations(self):
        """Check for new shot-impact correlations."""
        if not self.shot_events or not self.impact_events:
            return
        
        # Check recent shots for uncorrelated impacts
        correlation_window = timedelta(milliseconds=self.correlation_window_ms)
        
        for shot in reversed(list(self.shot_events)):
            if shot.get('correlated'):
                continue
                
            # Look for impacts within window
            best_impact = None
            best_delay = float('inf')
            
            for impact in reversed(list(self.impact_events)):
                if impact.get('correlated'):
                    continue
                    
                if impact['timestamp'] < shot['timestamp']:
                    continue
                    
                delay = impact['timestamp'] - shot['timestamp']
                if delay > correlation_window:
                    continue
                
                delay_ms = delay.total_seconds() * 1000
                if delay_ms < best_delay:
                    best_delay = delay_ms
                    best_impact = impact
            
            if best_impact:
                # Mark as correlated
                shot['correlated'] = True
                best_impact['correlated'] = True
                
                correlation = {
                    'shot': shot,
                    'impact': best_impact,
                    'delay_ms': int(best_delay),
                    'timestamp': datetime.now()
                }
                
                self.correlations.append(correlation)
                self.stats['pairs_correlated'] += 1
                
                # Update average delay
                delays = [c['delay_ms'] for c in self.correlations]
                self.stats['avg_delay_ms'] = sum(delays) / len(delays)
                
                print(f"🔗 CORRELATION: Shot #{shot.get('shot_number', '?')} → Impact {best_impact['magnitude']:.3f} ({int(best_delay)}ms delay)")
                
                # Adaptive window adjustment
                if len(self.correlations) >= 3:
                    recent_delays = [c['delay_ms'] for c in self.correlations[-5:]]
                    mean_delay = sum(recent_delays) / len(recent_delays)
                    # Adjust window to mean + 50% buffer
                    new_window = int(mean_delay * 1.5)
                    if abs(new_window - self.correlation_window_ms) > 100:
                        self.correlation_window_ms = new_window
                        print(f"🔧 Adjusted correlation window to {self.correlation_window_ms}ms")
    
    def _simulate_events(self):
        """Simulate timing events for testing (when no live logs available)."""
        print("🎮 Simulation mode - generating test timing events...")
        print("   This simulates the 455ms delay pattern from the handoff notes")
        
        shot_number = 1
        
        while self.is_running:
            # Simulate a shot
            shot_time = datetime.now()
            shot_event = {
                'timestamp': shot_time,
                'type': 'shot',
                'device_id': 'SIM:Timer',
                'shot_number': shot_number,
                'details': f"Simulated Shot #{shot_number}"
            }
            self.shot_events.append(shot_event)
            self.stats['shots_detected'] += 1
            print(f"🎯 [SIM] Shot #{shot_number} at {shot_time.strftime('%H:%M:%S.%f')[:-3]}")
            
            # Simulate impact after realistic delay (400-500ms based on handoff)
            import random
            delay_ms = random.randint(400, 500)
            impact_time = shot_time + timedelta(milliseconds=delay_ms)
            
            # Small delay for realism
            time.sleep(delay_ms / 1000.0)
            
            magnitude = random.uniform(150, 300)  # Realistic impact range
            impact_event = {
                'timestamp': impact_time,
                'type': 'impact', 
                'device_id': 'SIM:Sensor',
                'magnitude': magnitude,
                'details': f"Simulated Impact {magnitude:.1f}mg"
            }
            self.impact_events.append(impact_event)
            self.stats['impacts_detected'] += 1
            print(f"💥 [SIM] Impact {magnitude:.1f}mg at {impact_time.strftime('%H:%M:%S.%f')[:-3]}")
            
            # Process correlation
            self._check_for_correlations()
            
            shot_number += 1
            
            # Wait before next shot (3-5 seconds)
            wait_time = random.uniform(3, 5)
            time.sleep(wait_time)
    
    def _print_session_statistics(self):
        """Print comprehensive session statistics."""
        print(f"Session duration: {self.stats['session_duration']:.1f} seconds")
        print(f"Shots detected: {self.stats['shots_detected']}")
        print(f"Impacts detected: {self.stats['impacts_detected']}")
        print(f"Pairs correlated: {self.stats['pairs_correlated']}")
        
        if self.stats['pairs_correlated'] > 0:
            correlation_rate = (self.stats['pairs_correlated'] / self.stats['shots_detected']) * 100
            print(f"Correlation rate: {correlation_rate:.1f}%")
            print(f"Average delay: {self.stats['avg_delay_ms']:.1f} ms")
            
            if len(self.correlations) >= 3:
                delays = [c['delay_ms'] for c in self.correlations]
                min_delay = min(delays)
                max_delay = max(delays)
                print(f"Delay range: {min_delay} - {max_delay} ms")
                
                import statistics
                stdev = statistics.stdev(delays)
                print(f"Delay std dev: {stdev:.1f} ms")
                
                print(f"\nRecommended settings:")
                print(f"  - Correlation window: {int(self.stats['avg_delay_ms'] + 3*stdev)} ms")
                print(f"  - Expected delay: {int(self.stats['avg_delay_ms'])} ms")
    
    def export_session_data(self, output_path: Path):
        """Export captured timing data to file."""
        session_data = {
            'session_info': {
                'start_time': self.session_start.isoformat() if self.session_start else None,
                'duration_seconds': self.stats['session_duration'],
                'correlation_window_ms': self.correlation_window_ms
            },
            'statistics': self.stats,
            'correlations': self.correlations,
            'shots': list(self.shot_events),
            'impacts': list(self.impact_events)
        }
        
        # Convert datetime objects to ISO strings
        def datetime_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        with open(output_path, 'w') as f:
            json.dump(session_data, f, indent=2, default=datetime_serializer)
        
        print(f"📁 Session data exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Real-time Timing Capture for TinTown Bridge")
    parser.add_argument("--duration", type=int, help="Capture duration in seconds")
    parser.add_argument("--output", default="timing_capture.json", help="Output data file")
    parser.add_argument("--window", type=int, default=1500, help="Initial correlation window (ms)")
    parser.add_argument("--live", action="store_true", help="Monitor live bridge logs")
    parser.add_argument("--simulate", action="store_true", help="Force simulation mode")
    
    args = parser.parse_args()
    
    capture = RealTimeTimingCapture()
    capture.correlation_window_ms = args.window
    
    if args.simulate:
        print("🎮 Starting in simulation mode...")
    
    try:
        capture.start_capture(args.duration)
    finally:
        # Export data
        output_path = Path(args.output)
        capture.export_session_data(output_path)


if __name__ == "__main__":
    main()