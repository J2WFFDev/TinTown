#!/usr/bin/env python3
"""Test script to debug BT50 parsing issues"""

import sys
sys.path.append('/home/jrwest/projects/TinTown')

from src.impact_bridge.ble.wtvb_parse import parse_5561

# Test with actual raw data from the latest test
test_hex = "5561000000000000000000000000d1070000000000000400060003000000b0015561000000000000000000000000cb070000000000000400060003000000b0015561000000000000000000000000c4070000000000000400060003000000b0015561000000000000000000000000c4070000000000000400060003000000b001"

print(f"Testing with hex data: {test_hex[:64]}...")
test_bytes = bytes.fromhex(test_hex)

print(f"Hex length: {len(test_hex)}")
print(f"Bytes length: {len(test_bytes)}")
print(f"First 16 bytes: {test_bytes[:16].hex()}")

# Check for 0x55 0x61 pattern
if b"\x55\x61" in test_bytes:
    print("✓ Found 0x55 0x61 pattern in data")
    positions = []
    for i in range(len(test_bytes) - 1):
        if test_bytes[i] == 0x55 and test_bytes[i+1] == 0x61:
            positions.append(i)
    print(f"Pattern found at positions: {positions}")
else:
    print("✗ No 0x55 0x61 pattern found")

# Test the parser
result = parse_5561(test_bytes)
if result:
    print(f"✓ Parser SUCCESS: {len(result.get('samples', []))} samples")
    print(f"Averages: VX={result.get('VX')}, VY={result.get('VY')}, VZ={result.get('VZ')}")
    for i, sample in enumerate(result.get('samples', [])[:3]):
        print(f"Sample {i}: vx={sample.get('vx')}, vy={sample.get('vy')}, vz={sample.get('vz')}")
        print(f"  Raw: {sample.get('raw')}")
else:
    print("✗ Parser returned None")