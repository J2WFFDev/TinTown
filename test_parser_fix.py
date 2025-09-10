#!/usr/bin/env python3
"""
Quick test of the corrected BT50 parser
"""
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test the parser import and scale
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    print("✓ Successfully imported parse_5561")
    
    # Test with a real hex sample
    hex_sample = "556100000000000000000000000045090000000000000900050005000000ae01556100000000000000000000000052090000000000000900050005000000ae0155610000000000000000000000004c090000000000000900050005000000ae015561000000000000000000000000450900000000000900050005000000ae01"
    
    payload = bytes.fromhex(hex_sample)
    result = parse_5561(payload)
    
    if result:
        print("✓ Parser working!")
        print(f"Sample count: {len(result['samples'])}")
        print(f"Average values: VX={result['VX']:.6f}g, VY={result['VY']:.6f}g, VZ={result['VZ']:.6f}g")
        
        # Check the scale - should be in mg range now
        for i, sample in enumerate(result['samples'][:3]):
            print(f"Sample {i}: VX={sample['vx']:.6f}g, VY={sample['vy']:.6f}g, VZ={sample['vz']:.6f}g")
    else:
        print("✗ Parser returned None")
        
except Exception as e:
    print(f"✗ Import failed: {e}")