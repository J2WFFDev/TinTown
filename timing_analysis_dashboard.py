#!/usr/bin/env python3
"""
TinTown Timing Analysis Dashboard

Automated analysis and reporting for timing correlation, impact characteristics,
and system performance metrics during development.
"""

import os
import json
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import statistics

class TinTownAnalysisDashboard:
    """Automated analysis dashboard for TinTown bridge development"""
    
    def __init__(self, logs_directory: str = "logs"):
        self.logs_dir = Path(logs_directory)
        self.analysis_results = {}
        
    def analyze_session(self, session_date: str = None) -> Dict[str, Any]:
        """Analyze a complete testing session"""
        
        if not session_date:
            session_date = datetime.now().strftime('%Y%m%d')
        
        print(f"🔍 TINTOWN SESSION ANALYSIS - {session_date}")
        print("="*80)
        
        # Find log files for the session
        main_log = self._find_main_log(session_date)
        debug_log = self._find_debug_log(session_date)
        
        if not main_log:
            print(f"❌ No main log found for {session_date}")
            return {}
        
        # Extract session data
        session_data = {
            'session_date': session_date,
            'main_log': str(main_log),
            'debug_log': str(debug_log) if debug_log else None,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # Analyze timing correlation
        timing_analysis = self._analyze_timing_correlation(main_log)
        session_data['timing_analysis'] = timing_analysis
        
        # Analyze impact characteristics  
        impact_analysis = self._analyze_impact_characteristics(main_log)
        session_data['impact_analysis'] = impact_analysis
        
        # Analyze system performance
        performance_analysis = self._analyze_system_performance(main_log, debug_log)
        session_data['performance_analysis'] = performance_analysis
        
        # Generate summary report
        self._generate_summary_report(session_data)
        
        return session_data
    
    def _find_main_log(self, date_str: str) -> Optional[Path]:
        """Find main log file for given date"""
        pattern = f"bridge_main_{date_str}.ndjson"
        main_logs = list(self.logs_dir.glob(f"main/{pattern}"))
        return main_logs[0] if main_logs else None
    
    def _find_debug_log(self, date_str: str) -> Optional[Path]:
        """Find most recent debug log for given date"""
        pattern = f"bridge_debug_{date_str}_*.log"
        debug_logs = list(self.logs_dir.glob(f"debug/{pattern}"))
        return max(debug_logs, key=os.path.getmtime) if debug_logs else None
    
    def _analyze_timing_correlation(self, main_log: Path) -> Dict[str, Any]:
        """Analyze shot-impact timing correlation"""
        
        print("📊 Analyzing timing correlation...")
        
        shots = []
        impacts = []
        correlations = []
        
        try:
            with open(main_log, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        if entry.get('type') == 'String' and 'Shot #' in entry.get('details', ''):
                            # Extract shot data
                            shot_match = re.search(r'Shot #(\d+)', entry['details'])
                            if shot_match:
                                shots.append({
                                    'shot_number': int(shot_match.group(1)),
                                    'timestamp': entry['timestamp_iso'],
                                    'datetime': entry['datetime']
                                })
                        
                        elif entry.get('type') == 'Impact' and 'Enhanced impact' in entry.get('details', ''):
                            # Extract impact data
                            impact_match = re.search(r'onset ([\d.]+)g.*peak ([\d.]+)g.*confidence ([\d.]+)', entry['details'])
                            if impact_match:
                                impacts.append({
                                    'onset_magnitude': float(impact_match.group(1)),
                                    'peak_magnitude': float(impact_match.group(2)),
                                    'confidence': float(impact_match.group(3)),
                                    'timestamp': entry['timestamp_iso'],
                                    'datetime': entry['datetime']
                                })
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            print(f"Error reading main log: {e}")
            return {'error': str(e)}
        
        # Calculate correlation statistics
        timing_stats = {
            'total_shots': len(shots),
            'total_impacts': len(impacts),
            'correlation_rate': len(impacts) / max(len(shots), 1) * 100
        }
        
        # Estimate timing delays (simplified - would need correlation logic)
        if len(shots) >= len(impacts) and impacts:
            delays = []
            for i, impact in enumerate(impacts):
                if i < len(shots):
                    shot_time = datetime.fromisoformat(shots[i]['timestamp'])
                    impact_time = datetime.fromisoformat(impact['timestamp'])
                    delay_ms = (impact_time - shot_time).total_seconds() * 1000
                    delays.append(delay_ms)
            
            if delays:
                timing_stats.update({
                    'average_delay_ms': statistics.mean(delays),
                    'delay_std_dev': statistics.stdev(delays) if len(delays) > 1 else 0,
                    'min_delay_ms': min(delays),
                    'max_delay_ms': max(delays),
                    'delays': delays
                })
        
        print(f"   ✅ Found {len(shots)} shots and {len(impacts)} impacts")
        print(f"   📈 Correlation rate: {timing_stats.get('correlation_rate', 0):.1f}%")
        if 'average_delay_ms' in timing_stats:
            print(f"   ⏱️  Average delay: {timing_stats['average_delay_ms']:.1f}ms")
        
        return timing_stats
    
    def _analyze_impact_characteristics(self, main_log: Path) -> Dict[str, Any]:
        """Analyze impact event characteristics"""
        
        print("🎯 Analyzing impact characteristics...")
        
        onset_magnitudes = []
        peak_magnitudes = []
        confidence_scores = []
        
        try:
            with open(main_log, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        if entry.get('type') == 'Impact' and 'Enhanced impact' in entry.get('details', ''):
                            # Extract impact metrics
                            impact_match = re.search(r'onset ([\d.]+)g.*peak ([\d.]+)g.*confidence ([\d.]+)', entry['details'])
                            if impact_match:
                                onset_magnitudes.append(float(impact_match.group(1)))
                                peak_magnitudes.append(float(impact_match.group(2)))
                                confidence_scores.append(float(impact_match.group(3)))
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            print(f"Error analyzing impacts: {e}")
            return {'error': str(e)}
        
        if not onset_magnitudes:
            return {'total_impacts': 0}
        
        impact_stats = {
            'total_impacts': len(onset_magnitudes),
            'onset_magnitude': {
                'average': statistics.mean(onset_magnitudes),
                'std_dev': statistics.stdev(onset_magnitudes) if len(onset_magnitudes) > 1 else 0,
                'min': min(onset_magnitudes),
                'max': max(onset_magnitudes)
            },
            'peak_magnitude': {
                'average': statistics.mean(peak_magnitudes),
                'std_dev': statistics.stdev(peak_magnitudes) if len(peak_magnitudes) > 1 else 0,
                'min': min(peak_magnitudes),
                'max': max(peak_magnitudes)
            },
            'confidence': {
                'average': statistics.mean(confidence_scores),
                'std_dev': statistics.stdev(confidence_scores) if len(confidence_scores) > 1 else 0,
                'min': min(confidence_scores),
                'max': max(confidence_scores)
            }
        }
        
        print(f"   ✅ Analyzed {len(onset_magnitudes)} impact events")
        print(f"   📊 Average onset: {impact_stats['onset_magnitude']['average']:.1f}g")
        print(f"   📈 Average peak: {impact_stats['peak_magnitude']['average']:.1f}g")
        print(f"   🎯 Average confidence: {impact_stats['confidence']['average']:.2f}")
        
        return impact_stats
    
    def _analyze_system_performance(self, main_log: Path, debug_log: Optional[Path]) -> Dict[str, Any]:
        """Analyze system performance metrics"""
        
        print("⚡ Analyzing system performance...")
        
        performance_stats = {
            'session_duration_minutes': 0,
            'total_events': 0,
            'events_per_minute': 0
        }
        
        try:
            # Count events and determine session duration
            events = []
            with open(main_log, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        events.append(entry['timestamp_iso'])
                    except (json.JSONDecodeError, KeyError):
                        continue
            
            if events:
                start_time = datetime.fromisoformat(events[0])
                end_time = datetime.fromisoformat(events[-1])
                duration_minutes = (end_time - start_time).total_seconds() / 60
                
                performance_stats.update({
                    'session_duration_minutes': duration_minutes,
                    'total_events': len(events),
                    'events_per_minute': len(events) / max(duration_minutes, 1)
                })
        
        except Exception as e:
            print(f"Error analyzing performance: {e}")
            return {'error': str(e)}
        
        print(f"   ⏱️  Session duration: {performance_stats['session_duration_minutes']:.1f} minutes")
        print(f"   📊 Total events: {performance_stats['total_events']}")
        print(f"   📈 Events per minute: {performance_stats['events_per_minute']:.1f}")
        
        return performance_stats
    
    def _generate_summary_report(self, session_data: Dict[str, Any]):
        """Generate and display summary report"""
        
        print("\n" + "="*80)
        print("📋 SESSION ANALYSIS SUMMARY")
        print("="*80)
        
        timing = session_data.get('timing_analysis', {})
        impacts = session_data.get('impact_analysis', {})
        performance = session_data.get('performance_analysis', {})
        
        print(f"📅 Session Date: {session_data['session_date']}")
        print(f"⏱️  Duration: {performance.get('session_duration_minutes', 0):.1f} minutes")
        print(f"📊 Total Events: {performance.get('total_events', 0)}")
        
        print(f"\n🎯 TIMING CORRELATION:")
        print(f"   Shots: {timing.get('total_shots', 0)}")
        print(f"   Impacts: {timing.get('total_impacts', 0)}")
        print(f"   Correlation Rate: {timing.get('correlation_rate', 0):.1f}%")
        if 'average_delay_ms' in timing:
            print(f"   Average Delay: {timing['average_delay_ms']:.1f}ms ± {timing.get('delay_std_dev', 0):.1f}ms")
        
        print(f"\n📈 IMPACT ANALYSIS:")
        if impacts.get('total_impacts', 0) > 0:
            onset_avg = impacts['onset_magnitude']['average']
            peak_avg = impacts['peak_magnitude']['average']
            conf_avg = impacts['confidence']['average']
            print(f"   Total Impacts: {impacts['total_impacts']}")
            print(f"   Onset Magnitude: {onset_avg:.1f}g (avg)")
            print(f"   Peak Magnitude: {peak_avg:.1f}g (avg)")
            print(f"   Confidence Score: {conf_avg:.2f} (avg)")
        else:
            print(f"   No impact events found")
        
        # Quality assessment
        print(f"\n🏆 SYSTEM ASSESSMENT:")
        correlation_rate = timing.get('correlation_rate', 0)
        avg_confidence = impacts.get('confidence', {}).get('average', 0)
        
        if correlation_rate >= 90:
            print(f"   ✅ Excellent correlation rate ({correlation_rate:.1f}%)")
        elif correlation_rate >= 70:
            print(f"   ⚠️  Good correlation rate ({correlation_rate:.1f}%)")
        else:
            print(f"   ❌ Poor correlation rate ({correlation_rate:.1f}%)")
        
        if avg_confidence >= 0.8:
            print(f"   ✅ High impact detection confidence ({avg_confidence:.2f})")
        elif avg_confidence >= 0.6:
            print(f"   ⚠️  Moderate impact detection confidence ({avg_confidence:.2f})")
        else:
            print(f"   ❌ Low impact detection confidence ({avg_confidence:.2f})")
        
        print("="*80)
        
        # Save detailed report
        report_path = f"analysis_report_{session_data['session_date']}.json"
        with open(report_path, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"📄 Detailed report saved to: {report_path}")

def main():
    """Main analysis function"""
    import sys
    
    dashboard = TinTownAnalysisDashboard()
    
    # Analyze today's session by default, or specified date
    session_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    results = dashboard.analyze_session(session_date)
    
    if not results:
        print("❌ No analysis results generated")
        sys.exit(1)

if __name__ == "__main__":
    main()