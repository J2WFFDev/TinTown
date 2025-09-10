#!/usr/bin/env python3
"""
BT50 Sensor Calibration Tool
Analyzes sensor orientation and baseline values for proper calibration
"""

import asyncio
import sys
import os
import time
import statistics
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

class BT50Calibrator:
    def __init__(self):
        self.client = None
        self.samples = []
        self.collecting = False
        self.target_samples = 100  # Collect 100 samples for baseline
        
    async def notification_handler(self, characteristic, data):
        """Collect sensor data for calibration analysis"""
        if not self.collecting:
            return
            
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Store each sample
                for sample in result['samples']:
                    self.samples.append({
                        'vx': sample['vx'],
                        'vy': sample['vy'], 
                        'vz': sample['vz'],
                        'magnitude': (sample['vx']**2 + sample['vy']**2 + sample['vz']**2)**0.5,
                        'timestamp': time.time()
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

    async def collect_baseline_data(self):
        """Collect baseline data for calibration analysis"""
        print(f"\n=== COLLECTING BASELINE DATA ===")
        print("Keep sensor STATIONARY and level for accurate baseline measurement")
        print("Collection will start in 3 seconds...")
        
        await asyncio.sleep(3)
        
        print("Starting data collection...")
        self.samples = []
        self.collecting = True
        
        # Wait for collection to complete
        while self.collecting:
            await asyncio.sleep(0.1)
            
        print(f"\n✓ Collected {len(self.samples)} samples")

    def analyze_calibration(self):
        """Analyze collected data for calibration insights"""
        if not self.samples:
            print("✗ No samples collected")
            return
            
        # Extract axis data
        vx_values = [s['vx'] for s in self.samples]
        vy_values = [s['vy'] for s in self.samples] 
        vz_values = [s['vz'] for s in self.samples]
        mag_values = [s['magnitude'] for s in self.samples]
        
        # Calculate statistics
        vx_mean = statistics.mean(vx_values)
        vy_mean = statistics.mean(vy_values)
        vz_mean = statistics.mean(vz_values)
        mag_mean = statistics.mean(mag_values)
        
        vx_stdev = statistics.stdev(vx_values)
        vy_stdev = statistics.stdev(vy_values) 
        vz_stdev = statistics.stdev(vz_values)
        mag_stdev = statistics.stdev(mag_values)
        
        # Total gravity should be ~1g if properly calibrated
        total_gravity = (vx_mean**2 + vy_mean**2 + vz_mean**2)**0.5
        
        print(f"\n=== CALIBRATION ANALYSIS ===")
        print(f"Samples analyzed: {len(self.samples)}")
        print(f"\nBaseline Values (mean ± std dev):")
        print(f"  X-axis: {vx_mean:8.4f}g ± {vx_stdev:.4f}g")
        print(f"  Y-axis: {vy_mean:8.4f}g ± {vy_stdev:.4f}g") 
        print(f"  Z-axis: {vz_mean:8.4f}g ± {vz_stdev:.4f}g")
        print(f"  Magnitude: {mag_mean:8.4f}g ± {mag_stdev:.4f}g")
        
        print(f"\nGravity Analysis:")
        print(f"  Total gravity vector: {total_gravity:.4f}g")
        print(f"  Expected: ~1.000g (Earth's gravity)")
        
        # Determine sensor orientation
        dominant_axis = "X" if abs(vx_mean) > abs(vy_mean) and abs(vx_mean) > abs(vz_mean) else \
                       "Y" if abs(vy_mean) > abs(vz_mean) else "Z"
        
        print(f"\nSensor Orientation:")
        print(f"  Dominant axis: {dominant_axis} ({abs(eval(f'v{dominant_axis.lower()}_mean')):.4f}g)")
        print(f"  Sensor appears to be oriented with {dominant_axis}-axis aligned to gravity")
        
        # Calibration recommendations
        print(f"\nCalibration Status:")
        if 0.9 <= total_gravity <= 1.1:
            print(f"  ✓ GOOD: Total gravity ({total_gravity:.4f}g) is within normal range")
        else:
            print(f"  ⚠ WARNING: Total gravity ({total_gravity:.4f}g) deviates from 1g")
            print(f"    This suggests calibration offset or mounting angle issues")
            
        # Noise analysis
        max_noise = max(vx_stdev, vy_stdev, vz_stdev)
        print(f"\nNoise Analysis:")
        print(f"  Maximum axis noise: {max_noise:.4f}g")
        if max_noise < 0.01:
            print(f"  ✓ GOOD: Low noise sensor")
        elif max_noise < 0.05:
            print(f"  ⚠ MODERATE: Some noise present")
        else:
            print(f"  ✗ HIGH: Significant noise - check mounting/environment")
            
        # Impact threshold recommendations
        print(f"\nImpact Threshold Recommendations:")
        suggested_threshold = mag_mean + (5 * mag_stdev)  # 5-sigma above baseline
        print(f"  Current magnitude baseline: {mag_mean:.4f}g")
        print(f"  Suggested threshold (5σ above baseline): {suggested_threshold:.4f}g")
        print(f"  Current code threshold: 0.002g (WAY TOO LOW)")
        
        print(f"\nRecommended fixes:")
        print(f"  1. Update IMPACT_THRESHOLD = {suggested_threshold:.3f}")
        print(f"  2. Consider baseline subtraction for change detection")
        print(f"  3. Focus on {['Y','Z'][1 if dominant_axis=='X' else 0]}-axis for lateral impacts")

    async def run_multiple_tests(self, num_tests=3):
        """Run multiple calibration tests and calculate averages"""
        print("=== BT50 SENSOR CALIBRATION TOOL ===")
        print(f"Running {num_tests} calibration tests for accurate baseline")
        
        if not await self.connect():
            return
            
        all_test_results = []
        
        try:
            for test_num in range(1, num_tests + 1):
                print(f"\n--- TEST {test_num} of {num_tests} ---")
                
                # Reset for this test
                self.samples = []
                await self.collect_baseline_data()
                
                # Calculate stats for this test
                if self.samples:
                    vx_values = [s['vx'] for s in self.samples]
                    vy_values = [s['vy'] for s in self.samples] 
                    vz_values = [s['vz'] for s in self.samples]
                    mag_values = [s['magnitude'] for s in self.samples]
                    
                    test_result = {
                        'test_num': test_num,
                        'vx_mean': statistics.mean(vx_values),
                        'vy_mean': statistics.mean(vy_values),
                        'vz_mean': statistics.mean(vz_values),
                        'mag_mean': statistics.mean(mag_values),
                        'vx_stdev': statistics.stdev(vx_values),
                        'vy_stdev': statistics.stdev(vy_values),
                        'vz_stdev': statistics.stdev(vz_values),
                        'mag_stdev': statistics.stdev(mag_values),
                        'total_gravity': (statistics.mean(vx_values)**2 + statistics.mean(vy_values)**2 + statistics.mean(vz_values)**2)**0.5,
                        'sample_count': len(self.samples)
                    }
                    
                    all_test_results.append(test_result)
                    
                    print(f"Test {test_num} results:")
                    print(f"  X: {test_result['vx_mean']:.4f}g ± {test_result['vx_stdev']:.4f}g")
                    print(f"  Y: {test_result['vy_mean']:.4f}g ± {test_result['vy_stdev']:.4f}g")
                    print(f"  Z: {test_result['vz_mean']:.4f}g ± {test_result['vz_stdev']:.4f}g")
                    print(f"  Magnitude: {test_result['mag_mean']:.4f}g")
                    print(f"  Total gravity: {test_result['total_gravity']:.4f}g")
                
                if test_num < num_tests:
                    print("Waiting 5 seconds before next test...")
                    await asyncio.sleep(5)
            
            # Analyze combined results
            self.analyze_multiple_tests(all_test_results)
            
        except KeyboardInterrupt:
            print("\nCalibration interrupted")
            
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                print("\n✓ Disconnected from sensor")

    def analyze_multiple_tests(self, test_results):
        """Analyze results from multiple calibration tests"""
        if not test_results:
            print("✗ No test results to analyze")
            return
            
        print(f"\n=== MULTI-TEST CALIBRATION ANALYSIS ===")
        print(f"Tests completed: {len(test_results)}")
        
        # Calculate averages across all tests
        avg_vx = statistics.mean([t['vx_mean'] for t in test_results])
        avg_vy = statistics.mean([t['vy_mean'] for t in test_results])
        avg_vz = statistics.mean([t['vz_mean'] for t in test_results])
        avg_mag = statistics.mean([t['mag_mean'] for t in test_results])
        avg_gravity = statistics.mean([t['total_gravity'] for t in test_results])
        
        # Calculate consistency (standard deviation between tests)
        consistency_vx = statistics.stdev([t['vx_mean'] for t in test_results]) if len(test_results) > 1 else 0
        consistency_vy = statistics.stdev([t['vy_mean'] for t in test_results]) if len(test_results) > 1 else 0
        consistency_vz = statistics.stdev([t['vz_mean'] for t in test_results]) if len(test_results) > 1 else 0
        consistency_mag = statistics.stdev([t['mag_mean'] for t in test_results]) if len(test_results) > 1 else 0
        
        # Average noise levels
        avg_noise_vx = statistics.mean([t['vx_stdev'] for t in test_results])
        avg_noise_vy = statistics.mean([t['vy_stdev'] for t in test_results])
        avg_noise_vz = statistics.mean([t['vz_stdev'] for t in test_results])
        avg_noise_mag = statistics.mean([t['mag_stdev'] for t in test_results])
        
        print(f"\nAverage Baseline Values (across {len(test_results)} tests):")
        print(f"  X-axis: {avg_vx:8.4f}g (consistency: ±{consistency_vx:.4f}g, noise: ±{avg_noise_vx:.4f}g)")
        print(f"  Y-axis: {avg_vy:8.4f}g (consistency: ±{consistency_vy:.4f}g, noise: ±{avg_noise_vy:.4f}g)")
        print(f"  Z-axis: {avg_vz:8.4f}g (consistency: ±{consistency_vz:.4f}g, noise: ±{avg_noise_vz:.4f}g)")
        print(f"  Magnitude: {avg_mag:8.4f}g (consistency: ±{consistency_mag:.4f}g, noise: ±{avg_noise_mag:.4f}g)")
        
        print(f"\nGravity Analysis:")
        print(f"  Average total gravity: {avg_gravity:.4f}g")
        print(f"  Expected: ~1.000g (Earth's gravity)")
        print(f"  Scale factor error: {avg_gravity:.4f}x too high")
        
        # Determine sensor orientation
        dominant_axis = "X" if abs(avg_vx) > abs(avg_vy) and abs(avg_vx) > abs(avg_vz) else \
                       "Y" if abs(avg_vy) > abs(avg_vz) else "Z"
        
        print(f"\nSensor Orientation:")
        print(f"  Dominant axis: {dominant_axis} ({abs(eval(f'avg_v{dominant_axis.lower()}')):.4f}g)")
        
        # Calibration recommendations
        print(f"\nCalibration Status:")
        if 0.9 <= avg_gravity <= 1.1:
            print(f"  ✓ GOOD: Total gravity ({avg_gravity:.4f}g) is within normal range")
        else:
            print(f"  ⚠ WARNING: Total gravity ({avg_gravity:.4f}g) deviates from 1g")
            print(f"    Suggested scale correction: multiply by {1.0/avg_gravity:.6f}")
            
        # Consistency check
        max_consistency = max(consistency_vx, consistency_vy, consistency_vz)
        print(f"\nTest Consistency:")
        if max_consistency < 0.005:
            print(f"  ✓ EXCELLENT: Very consistent between tests (±{max_consistency:.4f}g)")
        elif max_consistency < 0.02:
            print(f"  ✓ GOOD: Reasonably consistent between tests (±{max_consistency:.4f}g)")
        else:
            print(f"  ⚠ WARNING: Inconsistent between tests (±{max_consistency:.4f}g)")
            
        # Impact threshold recommendations
        print(f"\nImpact Threshold Recommendations:")
        # Use 5-sigma above baseline including test consistency
        total_uncertainty = avg_noise_mag + consistency_mag
        suggested_threshold = avg_mag + (5 * total_uncertainty)
        
        print(f"  Average magnitude baseline: {avg_mag:.4f}g")
        print(f"  Total uncertainty (noise + consistency): ±{total_uncertainty:.4f}g")
        print(f"  Suggested threshold (5σ above baseline): {suggested_threshold:.4f}g")
        print(f"  Current code threshold: 0.002g (COMPLETELY WRONG)")
        
        print(f"\nRecommended Code Updates:")
        print(f"  1. Update scale factor: 0.001 → {0.001/avg_gravity:.6f}")
        print(f"  2. Update IMPACT_THRESHOLD = {suggested_threshold:.3f}")
        print(f"  3. Alternative: Use baseline subtraction with threshold = {5 * total_uncertainty:.3f}")

    async def run(self):
        """Main calibration routine - now runs multiple tests"""
        await self.run_multiple_tests(3)

async def main():
    calibrator = BT50Calibrator()
    await calibrator.run()

if __name__ == "__main__":
    asyncio.run(main())