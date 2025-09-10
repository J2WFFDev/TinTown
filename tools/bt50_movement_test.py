#!/usr/bin/env python3
"""
BT50 Movement Test - Test all 3 axes with deliberate movement
Move sensor on X, Y, Z axes to verify all axes are responsive
"""

import asyncio
import sys
import os
import time
import statistics
from datetime import datetime
from pathlib import Path
from bleak import BleakClient

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

class BT50MovementTester:
    def __init__(self):
        self.client = None
        self.samples = []
        self.collecting = False
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure log directories exist
        Path("logs/movement").mkdir(parents=True, exist_ok=True)
        
        # Setup log file
        self.log_file = f"logs/movement/bt50_movement_test_{self.session_id}.txt"
        
        print(f"Movement test session ID: {self.session_id}")
        print(f"Results will be logged to: {self.log_file}")
        
    def log_results(self, message):
        """Log results to both console and file"""
        print(message)
        with open(self.log_file, 'a') as f:
            f.write(message + '\n')
        
    async def notification_handler(self, characteristic, data):
        """Collect sensor data during movement test"""
        if not self.collecting:
            return
            
        try:
            result = parse_5561(data)
            if result and result['samples']:
                # Store each sample with timestamp
                timestamp = time.time()
                for sample in result['samples']:
                    self.samples.append({
                        'timestamp': timestamp,
                        'vx': sample['vx'],
                        'vy': sample['vy'], 
                        'vz': sample['vz'],
                        'magnitude': (sample['vx']**2 + sample['vy']**2 + sample['vz']**2)**0.5,
                    })
                    
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

    async def movement_test(self, test_name, duration_seconds, instructions):
        """Run a specific movement test"""
        self.log_results(f"\n--- {test_name} ---")
        self.log_results(f"Instructions: {instructions}")
        self.log_results("Test will start in 3 seconds...")
        
        await asyncio.sleep(3)
        
        self.log_results(f"Starting {duration_seconds}s collection...")
        self.samples = []
        self.collecting = True
        
        # Collect for specified duration
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(0.1)
            
        self.collecting = False
        
        if not self.samples:
            self.log_results("✗ No samples collected")
            return None
            
        # Analyze the movement data
        vx_values = [s['vx'] for s in self.samples]
        vy_values = [s['vy'] for s in self.samples] 
        vz_values = [s['vz'] for s in self.samples]
        mag_values = [s['magnitude'] for s in self.samples]
        
        results = {
            'test_name': test_name,
            'sample_count': len(self.samples),
            'duration': duration_seconds,
            'vx': {
                'min': min(vx_values),
                'max': max(vx_values),
                'avg': statistics.mean(vx_values),
                'range': max(vx_values) - min(vx_values),
                'stdev': statistics.stdev(vx_values)
            },
            'vy': {
                'min': min(vy_values),
                'max': max(vy_values),
                'avg': statistics.mean(vy_values),
                'range': max(vy_values) - min(vy_values),
                'stdev': statistics.stdev(vy_values) if len(set(vy_values)) > 1 else 0.0
            },
            'vz': {
                'min': min(vz_values),
                'max': max(vz_values),
                'avg': statistics.mean(vz_values),
                'range': max(vz_values) - min(vz_values),
                'stdev': statistics.stdev(vz_values) if len(set(vz_values)) > 1 else 0.0
            },
            'magnitude': {
                'min': min(mag_values),
                'max': max(mag_values),
                'avg': statistics.mean(mag_values),
                'range': max(mag_values) - min(mag_values),
                'stdev': statistics.stdev(mag_values)
            }
        }
        
        self.log_results(f"✓ Collected {results['sample_count']} samples")
        self.log_results(f"Results:")
        self.log_results(f"  X-axis: Min={results['vx']['min']:7.4f}g, Max={results['vx']['max']:7.4f}g, Range={results['vx']['range']:7.4f}g")
        self.log_results(f"  Y-axis: Min={results['vy']['min']:7.4f}g, Max={results['vy']['max']:7.4f}g, Range={results['vy']['range']:7.4f}g")
        self.log_results(f"  Z-axis: Min={results['vz']['min']:7.4f}g, Max={results['vz']['max']:7.4f}g, Range={results['vz']['range']:7.4f}g")
        self.log_results(f"  Magnitude: Min={results['magnitude']['min']:7.4f}g, Max={results['magnitude']['max']:7.4f}g, Range={results['magnitude']['range']:7.4f}g")
        
        return results

    async def run_movement_tests(self):
        """Run comprehensive movement tests"""
        self.log_results("="*80)
        self.log_results("BT50 SENSOR MOVEMENT TEST")
        self.log_results("="*80)
        self.log_results(f"Session ID: {self.session_id}")
        self.log_results(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_results(f"Sensor MAC: {BT50_SENSOR_MAC}")
        
        if not await self.connect():
            return
            
        all_results = []
        
        try:
            # Test 1: Stationary baseline
            result = await self.movement_test(
                "BASELINE (Stationary)", 
                10, 
                "Keep sensor completely still"
            )
            if result:
                all_results.append(result)
            
            await asyncio.sleep(2)
            
            # Test 2: X-axis movement
            result = await self.movement_test(
                "X-AXIS MOVEMENT", 
                15, 
                "Move sensor back and forth along X-axis (left-right)"
            )
            if result:
                all_results.append(result)
            
            await asyncio.sleep(2)
            
            # Test 3: Y-axis movement  
            result = await self.movement_test(
                "Y-AXIS MOVEMENT", 
                15, 
                "Move sensor back and forth along Y-axis (forward-backward)"
            )
            if result:
                all_results.append(result)
            
            await asyncio.sleep(2)
            
            # Test 4: Z-axis movement
            result = await self.movement_test(
                "Z-AXIS MOVEMENT", 
                15, 
                "Move sensor up and down along Z-axis (vertical)"
            )
            if result:
                all_results.append(result)
            
            await asyncio.sleep(2)
            
            # Test 5: Multi-axis movement
            result = await self.movement_test(
                "MULTI-AXIS MOVEMENT", 
                20, 
                "Move sensor in all directions - shake, rotate, tap"
            )
            if result:
                all_results.append(result)
            
            # Summary analysis
            self.analyze_movement_summary(all_results)
            
        except KeyboardInterrupt:
            self.log_results("\nMovement test interrupted")
            
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.log_results("\n✓ Disconnected from sensor")

    def analyze_movement_summary(self, results):
        """Analyze overall movement test results"""
        if not results:
            return
            
        self.log_results("\n" + "="*80)
        self.log_results("MOVEMENT TEST SUMMARY")
        self.log_results("="*80)
        
        # Find baseline (first test)
        baseline = results[0] if results else None
        
        self.log_results("Axis Responsiveness Analysis:")
        self.log_results("-" * 40)
        
        for axis in ['vx', 'vy', 'vz']:
            axis_name = {'vx': 'X-AXIS', 'vy': 'Y-AXIS', 'vz': 'Z-AXIS'}[axis]
            
            self.log_results(f"\n{axis_name}:")
            baseline_avg = baseline[axis]['avg'] if baseline else 0
            baseline_range = baseline[axis]['range'] if baseline else 0
            
            self.log_results(f"  Baseline: Avg={baseline_avg:7.4f}g, Range={baseline_range:7.4f}g")
            
            max_range = 0
            most_responsive_test = None
            
            for result in results[1:]:  # Skip baseline
                test_range = result[axis]['range']
                if test_range > max_range:
                    max_range = test_range
                    most_responsive_test = result['test_name']
                    
                self.log_results(f"  {result['test_name']}: Range={test_range:7.4f}g")
            
            if max_range > 0.01:
                self.log_results(f"  ✓ RESPONSIVE: Max range {max_range:.4f}g in {most_responsive_test}")
            elif max_range > 0.001:
                self.log_results(f"  ⚠ WEAK: Max range {max_range:.4f}g in {most_responsive_test}")
            else:
                self.log_results(f"  ✗ UNRESPONSIVE: Max range {max_range:.4f}g")
        
        # Calibration recommendations
        self.log_results(f"\nCalibration Recommendations:")
        self.log_results("-" * 40)
        
        if baseline:
            x_bias = baseline['vx']['avg']
            y_bias = baseline['vy']['avg'] 
            z_bias = baseline['vz']['avg']
            
            self.log_results(f"Detected axis biases (subtract these for zero calibration):")
            self.log_results(f"  X-axis bias: {x_bias:.4f}g")
            self.log_results(f"  Y-axis bias: {y_bias:.4f}g") 
            self.log_results(f"  Z-axis bias: {z_bias:.4f}g")
            
            # Determine which axis has gravity
            max_bias = max(abs(x_bias), abs(y_bias), abs(z_bias))
            if abs(x_bias) == max_bias:
                gravity_axis = "X"
            elif abs(y_bias) == max_bias:
                gravity_axis = "Y" 
            else:
                gravity_axis = "Z"
                
            self.log_results(f"  Likely gravity axis: {gravity_axis} ({max_bias:.4f}g)")
            self.log_results(f"  Expected gravity: ~1.0g")
            self.log_results(f"  Scale correction needed: {max_bias:.4f} → 1.0g")

    async def run(self):
        """Main movement test routine"""
        await self.run_movement_tests()

async def main():
    tester = BT50MovementTester()
    await tester.run()

if __name__ == "__main__":
    asyncio.run(main())