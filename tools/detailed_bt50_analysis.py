#!/usr/bin/env python3
"""
BT50 Detailed Analysis Tool
Shows max, min, avg for X, Y, Z across multiple tests
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

class BT50DetailedAnalyzer:
    def __init__(self):
        self.client = None
        self.samples = []
        self.collecting = False
        self.target_samples = 100  # Collect 100 samples per test
        
    async def notification_handler(self, characteristic, data):
        """Collect sensor data for detailed analysis"""
        if not self.collecting:
            return
            
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Store each sample with timestamp
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

    async def collect_test_data(self, test_num):
        """Collect data for one test"""
        print(f"\n--- TEST {test_num} ---")
        print("Keep sensor STATIONARY for accurate measurement")
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
            }
        }
        
        print(f"\nTEST {test_num} DETAILED RESULTS:")
        print(f"Samples: {stats['sample_count']}")
        print(f"")
        print(f"X-axis:")
        print(f"  Min:   {stats['vx']['min']:8.6f}g")
        print(f"  Max:   {stats['vx']['max']:8.6f}g")
        print(f"  Avg:   {stats['vx']['avg']:8.6f}g")
        print(f"  Range: {stats['vx']['range']:8.6f}g")
        print(f"  StDev: {stats['vx']['stdev']:8.6f}g")
        
        print(f"")
        print(f"Y-axis:")
        print(f"  Min:   {stats['vy']['min']:8.6f}g")
        print(f"  Max:   {stats['vy']['max']:8.6f}g")
        print(f"  Avg:   {stats['vy']['avg']:8.6f}g")
        print(f"  Range: {stats['vy']['range']:8.6f}g")
        print(f"  StDev: {stats['vy']['stdev']:8.6f}g")
        
        print(f"")
        print(f"Z-axis:")
        print(f"  Min:   {stats['vz']['min']:8.6f}g")
        print(f"  Max:   {stats['vz']['max']:8.6f}g")
        print(f"  Avg:   {stats['vz']['avg']:8.6f}g")
        print(f"  Range: {stats['vz']['range']:8.6f}g")
        print(f"  StDev: {stats['vz']['stdev']:8.6f}g")
        
        print(f"")
        print(f"Magnitude:")
        print(f"  Min:   {stats['magnitude']['min']:8.6f}g")
        print(f"  Max:   {stats['magnitude']['max']:8.6f}g")
        print(f"  Avg:   {stats['magnitude']['avg']:8.6f}g")
        print(f"  Range: {stats['magnitude']['range']:8.6f}g")
        print(f"  StDev: {stats['magnitude']['stdev']:8.6f}g")
        
        return stats

    def analyze_combined_results(self, all_stats):
        """Analyze results across all tests"""
        if not all_stats:
            print("✗ No test results to analyze")
            return
            
        print(f"\n" + "="*60)
        print(f"COMBINED ANALYSIS ACROSS {len(all_stats)} TESTS")
        print(f"="*60)
        
        # Aggregate across all tests
        for axis in ['vx', 'vy', 'vz', 'magnitude']:
            axis_name = {'vx': 'X-AXIS', 'vy': 'Y-AXIS', 'vz': 'Z-AXIS', 'magnitude': 'MAGNITUDE'}[axis]
            
            all_mins = [stats[axis]['min'] for stats in all_stats]
            all_maxs = [stats[axis]['max'] for stats in all_stats]
            all_avgs = [stats[axis]['avg'] for stats in all_stats]
            all_ranges = [stats[axis]['range'] for stats in all_stats]
            
            overall_min = min(all_mins)
            overall_max = max(all_maxs)
            avg_of_avgs = statistics.mean(all_avgs)
            avg_range = statistics.mean(all_ranges)
            consistency = statistics.stdev(all_avgs) if len(all_avgs) > 1 else 0.0
            
            print(f"\n{axis_name}:")
            print(f"  Overall Min:     {overall_min:8.6f}g")
            print(f"  Overall Max:     {overall_max:8.6f}g")
            print(f"  Overall Range:   {overall_max - overall_min:8.6f}g")
            print(f"  Avg of Averages: {avg_of_avgs:8.6f}g")
            print(f"  Avg Range:       {avg_range:8.6f}g")
            print(f"  Test Consistency:±{consistency:8.6f}g")
            
            # Per-test breakdown
            print(f"  Per-test breakdown:")
            for i, stats in enumerate(all_stats, 1):
                print(f"    Test {i}: Min={stats[axis]['min']:7.4f}g, Max={stats[axis]['max']:7.4f}g, Avg={stats[axis]['avg']:7.4f}g")

    async def run_detailed_analysis(self, num_tests=3):
        """Run detailed multi-test analysis"""
        print("=== BT50 DETAILED SENSOR ANALYSIS ===")
        print(f"Running {num_tests} tests with detailed min/max/avg analysis")
        
        if not await self.connect():
            return
            
        all_test_stats = []
        
        try:
            for test_num in range(1, num_tests + 1):
                test_samples = await self.collect_test_data(test_num)
                test_stats = self.analyze_test_data(test_num, test_samples)
                
                if test_stats:
                    all_test_stats.append(test_stats)
                
                if test_num < num_tests:
                    print("Waiting 5 seconds before next test...")
                    await asyncio.sleep(5)
            
            # Combined analysis
            self.analyze_combined_results(all_test_stats)
            
        except KeyboardInterrupt:
            print("\nAnalysis interrupted")
            
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                print("\n✓ Disconnected from sensor")

    async def run(self):
        """Main analysis routine"""
        await self.run_detailed_analysis(3)

async def main():
    analyzer = BT50DetailedAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    asyncio.run(main())