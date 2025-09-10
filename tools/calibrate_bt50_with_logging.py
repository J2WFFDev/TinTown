#!/usr/bin/env python3
"""
BT50 Calibration Tool with Logging
Runs 3 tests, saves all sample data and detailed analysis to log files
"""

import asyncio
import sys
import os
import time
import statistics
import json
import csv
from datetime import datetime
from pathlib import Path
from bleak import BleakClient
import struct

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    print("✓ Successfully imported corrected parse_5561 parser")
except Exception as e:
    print(f"⚠ Parser import failed: {e}")
    sys.exit(1)

# BT50 Sensor details
BT50_SENSOR_MAC = "F8:FE:92:31:12:E3"
BT50_SENSOR_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"

class BT50CalibratorWithLogging:
    def __init__(self):
        self.client = None
        self.samples = []
        self.collecting = False
        self.target_samples = 100  # Collect 100 samples per test
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure log directories exist
        Path("logs/calibration").mkdir(parents=True, exist_ok=True)
        
        # Setup log files
        self.raw_data_file = f"logs/calibration/bt50_raw_samples_{self.session_id}.csv"
        self.summary_file = f"logs/calibration/bt50_calibration_summary_{self.session_id}.json"
        self.report_file = f"logs/calibration/bt50_calibration_report_{self.session_id}.txt"
        
        print(f"Calibration session ID: {self.session_id}")
        print(f"Raw data will be saved to: {self.raw_data_file}")
        print(f"Summary will be saved to: {self.summary_file}")
        print(f"Report will be saved to: {self.report_file}")
        
    async def notification_handler(self, characteristic, data):
        """Collect sensor data for calibration analysis"""
        if not self.collecting:
            return
            
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Store each sample with detailed info
                timestamp = time.time()
                for i, sample in enumerate(result['samples']):
                    self.samples.append({
                        'timestamp': timestamp,
                        'sample_index': len(self.samples),
                        'frame_index': i,
                        'vx': sample['vx'],
                        'vy': sample['vy'], 
                        'vz': sample['vz'],
                        'vx_raw': sample['raw'][0],
                        'vy_raw': sample['raw'][1],
                        'vz_raw': sample['raw'][2],
                        'magnitude': (sample['vx']**2 + sample['vy']**2 + sample['vz']**2)**0.5,
                    })
                    
                print(f"\rCollected {len(self.samples)}/{self.target_samples} samples...", end='', flush=True)
                
                if len(self.samples) >= self.target_samples:
                    self.collecting = False
                    
        except Exception as e:
            print(f"⚠ Parsing error: {e}")

    async def connect(self):
        """Connect to BT50 sensor"""
        print(f"Connecting to BT50 sensor at {BT50_SENSOR_MAC}...")
        
        try:
            self.client = BleakClient(BT50_SENSOR_MAC)
            await self.client.connect()
            print("✓ Connected to BT50 sensor")
            
            # Enable notifications
            await self.client.start_notify(BT50_SENSOR_UUID, self.notification_handler)
            print("✓ Notifications enabled")
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
            
        return True

    async def collect_test_data(self, test_num):
        """Collect data for one test"""
        print(f"\n--- TEST {test_num} ---")
        print("Keep sensor STATIONARY for accurate baseline measurement")
        print("Collection will start in 3 seconds...")
        
        await asyncio.sleep(3)
        
        print("Starting data collection...")
        self.samples = []
        self.collecting = True
        
        # Wait for collection to complete
        while self.collecting:
            await asyncio.sleep(0.1)
            
        print(f"\n✓ Collected {len(self.samples)} samples")
        return self.samples.copy()  # Return copy of samples

    def save_raw_samples(self, test_num, samples):
        """Save raw sample data to CSV file"""
        # Create CSV file with headers if it doesn't exist
        file_exists = Path(self.raw_data_file).exists()
        
        with open(self.raw_data_file, 'a', newline='') as f:
            fieldnames = ['test_num', 'timestamp', 'sample_index', 'frame_index', 
                         'vx', 'vy', 'vz', 'vx_raw', 'vy_raw', 'vz_raw', 'magnitude']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            for sample in samples:
                row = sample.copy()
                row['test_num'] = test_num
                writer.writerow(row)
        
        print(f"✓ Saved {len(samples)} raw samples to {self.raw_data_file}")

    def analyze_test_data(self, test_num, samples):
        """Analyze detailed statistics for one test"""
        if not samples:
            print(f"✗ No samples for test {test_num}")
            return None
            
        # Extract axis data
        vx_values = [s['vx'] for s in samples]
        vy_values = [s['vy'] for s in samples] 
        vz_values = [s['vz'] for s in samples]
        mag_values = [s['magnitude'] for s in samples]
        
        # Calculate detailed stats
        stats = {
            'test_num': test_num,
            'sample_count': len(samples),
            'timestamp': datetime.now().isoformat(),
            'vx': {
                'min': min(vx_values),
                'max': max(vx_values),
                'avg': statistics.mean(vx_values),
                'stdev': statistics.stdev(vx_values),
                'range': max(vx_values) - min(vx_values)
            },
            'vy': {
                'min': min(vy_values),
                'max': max(vy_values),
                'avg': statistics.mean(vy_values),
                'stdev': statistics.stdev(vy_values) if len(set(vy_values)) > 1 else 0.0,
                'range': max(vy_values) - min(vy_values)
            },
            'vz': {
                'min': min(vz_values),
                'max': max(vz_values),
                'avg': statistics.mean(vz_values),
                'stdev': statistics.stdev(vz_values) if len(set(vz_values)) > 1 else 0.0,
                'range': max(vz_values) - min(vz_values)
            },
            'magnitude': {
                'min': min(mag_values),
                'max': max(mag_values),
                'avg': statistics.mean(mag_values),
                'stdev': statistics.stdev(mag_values),
                'range': max(mag_values) - min(mag_values)
            },
            'total_gravity': (statistics.mean(vx_values)**2 + statistics.mean(vy_values)**2 + statistics.mean(vz_values)**2)**0.5
        }
        
        print(f"\nTEST {test_num} RESULTS:")
        print(f"  X-axis: Min={stats['vx']['min']:7.4f}g, Max={stats['vx']['max']:7.4f}g, Avg={stats['vx']['avg']:7.4f}g")
        print(f"  Y-axis: Min={stats['vy']['min']:7.4f}g, Max={stats['vy']['max']:7.4f}g, Avg={stats['vy']['avg']:7.4f}g")
        print(f"  Z-axis: Min={stats['vz']['min']:7.4f}g, Max={stats['vz']['max']:7.4f}g, Avg={stats['vz']['avg']:7.4f}g")
        print(f"  Magnitude: Min={stats['magnitude']['min']:7.4f}g, Max={stats['magnitude']['max']:7.4f}g, Avg={stats['magnitude']['avg']:7.4f}g")
        print(f"  Total gravity: {stats['total_gravity']:.4f}g")
        
        return stats

    def save_calibration_summary(self, all_test_stats):
        """Save calibration summary to JSON file"""
        if not all_test_stats:
            return
            
        # Calculate combined statistics
        avg_vx = statistics.mean([t['vx']['avg'] for t in all_test_stats])
        avg_vy = statistics.mean([t['vy']['avg'] for t in all_test_stats])
        avg_vz = statistics.mean([t['vz']['avg'] for t in all_test_stats])
        avg_mag = statistics.mean([t['magnitude']['avg'] for t in all_test_stats])
        avg_gravity = statistics.mean([t['total_gravity'] for t in all_test_stats])
        
        # Calculate consistency (standard deviation between tests)
        consistency_vx = statistics.stdev([t['vx']['avg'] for t in all_test_stats]) if len(all_test_stats) > 1 else 0
        consistency_vy = statistics.stdev([t['vy']['avg'] for t in all_test_stats]) if len(all_test_stats) > 1 else 0
        consistency_vz = statistics.stdev([t['vz']['avg'] for t in all_test_stats]) if len(all_test_stats) > 1 else 0
        consistency_mag = statistics.stdev([t['magnitude']['avg'] for t in all_test_stats]) if len(all_test_stats) > 1 else 0
        
        # Average noise levels
        avg_noise_vx = statistics.mean([t['vx']['stdev'] for t in all_test_stats])
        avg_noise_vy = statistics.mean([t['vy']['stdev'] for t in all_test_stats])
        avg_noise_vz = statistics.mean([t['vz']['stdev'] for t in all_test_stats])
        avg_noise_mag = statistics.mean([t['magnitude']['stdev'] for t in all_test_stats])
        
        # Calculate recommendations
        total_uncertainty = avg_noise_mag + consistency_mag
        suggested_threshold = avg_mag + (5 * total_uncertainty)
        corrected_scale_factor = 0.001 / avg_gravity
        
        summary = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'sensor_mac': BT50_SENSOR_MAC,
            'num_tests': len(all_test_stats),
            'samples_per_test': self.target_samples,
            'individual_tests': all_test_stats,
            'combined_analysis': {
                'baseline_values': {
                    'vx_avg': avg_vx,
                    'vy_avg': avg_vy,
                    'vz_avg': avg_vz,
                    'magnitude_avg': avg_mag,
                    'total_gravity': avg_gravity
                },
                'consistency': {
                    'vx_consistency': consistency_vx,
                    'vy_consistency': consistency_vy,
                    'vz_consistency': consistency_vz,
                    'magnitude_consistency': consistency_mag
                },
                'noise_levels': {
                    'vx_noise': avg_noise_vx,
                    'vy_noise': avg_noise_vy,
                    'vz_noise': avg_noise_vz,
                    'magnitude_noise': avg_noise_mag
                },
                'recommendations': {
                    'current_scale_factor': 0.001,
                    'corrected_scale_factor': corrected_scale_factor,
                    'scale_correction_multiplier': 1.0 / avg_gravity,
                    'current_threshold': 0.002,
                    'suggested_threshold': suggested_threshold,
                    'total_uncertainty': total_uncertainty
                }
            }
        }
        
        with open(self.summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✓ Saved calibration summary to {self.summary_file}")
        return summary

    def save_calibration_report(self, summary):
        """Save human-readable calibration report"""
        with open(self.report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("BT50 SENSOR CALIBRATION REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Sensor MAC: {BT50_SENSOR_MAC}\n")
            f.write(f"Number of tests: {summary['num_tests']}\n")
            f.write(f"Samples per test: {summary['samples_per_test']}\n")
            f.write("\n")
            
            # Individual test results
            f.write("INDIVIDUAL TEST RESULTS:\n")
            f.write("-" * 40 + "\n")
            for test in summary['individual_tests']:
                f.write(f"Test {test['test_num']}:\n")
                f.write(f"  X-axis: Min={test['vx']['min']:7.4f}g, Max={test['vx']['max']:7.4f}g, Avg={test['vx']['avg']:7.4f}g\n")
                f.write(f"  Y-axis: Min={test['vy']['min']:7.4f}g, Max={test['vy']['max']:7.4f}g, Avg={test['vy']['avg']:7.4f}g\n")
                f.write(f"  Z-axis: Min={test['vz']['min']:7.4f}g, Max={test['vz']['max']:7.4f}g, Avg={test['vz']['avg']:7.4f}g\n")
                f.write(f"  Magnitude: Min={test['magnitude']['min']:7.4f}g, Max={test['magnitude']['max']:7.4f}g, Avg={test['magnitude']['avg']:7.4f}g\n")
                f.write(f"  Total gravity: {test['total_gravity']:.4f}g\n")
                f.write("\n")
            
            # Combined analysis
            ca = summary['combined_analysis']
            f.write("COMBINED ANALYSIS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Average baseline values:\n")
            f.write(f"  X-axis: {ca['baseline_values']['vx_avg']:8.4f}g\n")
            f.write(f"  Y-axis: {ca['baseline_values']['vy_avg']:8.4f}g\n")
            f.write(f"  Z-axis: {ca['baseline_values']['vz_avg']:8.4f}g\n")
            f.write(f"  Magnitude: {ca['baseline_values']['magnitude_avg']:8.4f}g\n")
            f.write(f"  Total gravity: {ca['baseline_values']['total_gravity']:8.4f}g\n")
            f.write("\n")
            
            f.write(f"Test consistency (between-test variation):\n")
            f.write(f"  X-axis: ±{ca['consistency']['vx_consistency']:8.4f}g\n")
            f.write(f"  Y-axis: ±{ca['consistency']['vy_consistency']:8.4f}g\n")
            f.write(f"  Z-axis: ±{ca['consistency']['vz_consistency']:8.4f}g\n")
            f.write(f"  Magnitude: ±{ca['consistency']['magnitude_consistency']:8.4f}g\n")
            f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Current scale factor: {ca['recommendations']['current_scale_factor']:.6f}\n")
            f.write(f"Corrected scale factor: {ca['recommendations']['corrected_scale_factor']:.6f}\n")
            f.write(f"Scale correction multiplier: {ca['recommendations']['scale_correction_multiplier']:.6f}\n")
            f.write(f"Current threshold: {ca['recommendations']['current_threshold']:.3f}g (TOO LOW)\n")
            f.write(f"Suggested threshold: {ca['recommendations']['suggested_threshold']:.3f}g\n")
            f.write(f"Total uncertainty: ±{ca['recommendations']['total_uncertainty']:.4f}g\n")
            f.write("\n")
            
            f.write("CODE UPDATES NEEDED:\n")
            f.write("-" * 40 + "\n")
            f.write(f"1. Update scale factor in wtvb_parse.py:\n")
            f.write(f"   scale = {ca['recommendations']['corrected_scale_factor']:.6f}\n")
            f.write(f"2. Update IMPACT_THRESHOLD in fixed_bridge.py:\n")
            f.write(f"   IMPACT_THRESHOLD = {ca['recommendations']['suggested_threshold']:.3f}\n")
            f.write(f"3. Alternative: Use baseline subtraction with threshold = {5 * ca['recommendations']['total_uncertainty']:.3f}\n")
        
        print(f"✓ Saved calibration report to {self.report_file}")

    async def run_calibration_with_logging(self, num_tests=3):
        """Run calibration with complete logging"""
        print("=== BT50 CALIBRATION WITH LOGGING ===")
        print(f"Running {num_tests} tests with complete data logging")
        
        if not await self.connect():
            return
            
        all_test_stats = []
        
        try:
            for test_num in range(1, num_tests + 1):
                test_samples = await self.collect_test_data(test_num)
                
                # Save raw samples to CSV
                self.save_raw_samples(test_num, test_samples)
                
                # Analyze test data
                test_stats = self.analyze_test_data(test_num, test_samples)
                
                if test_stats:
                    all_test_stats.append(test_stats)
                
                if test_num < num_tests:
                    print("Waiting 5 seconds before next test...")
                    await asyncio.sleep(5)
            
            # Save summary and report
            summary = self.save_calibration_summary(all_test_stats)
            if summary:
                self.save_calibration_report(summary)
                
            print(f"\n✓ Calibration complete! Files saved:")
            print(f"  Raw data: {self.raw_data_file}")
            print(f"  Summary: {self.summary_file}")
            print(f"  Report: {self.report_file}")
            
        except KeyboardInterrupt:
            print("\nCalibration interrupted")
            
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                print("\n✓ Disconnected from sensor")

    async def run(self):
        """Main calibration routine"""
        await self.run_calibration_with_logging(3)

async def main():
    calibrator = BT50CalibratorWithLogging()
    await calibrator.run()

if __name__ == "__main__":
    asyncio.run(main())