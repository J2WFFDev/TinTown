#!/usr/bin/env python3
"""Test corrected BT50 parsing"""

import struct

def parse_bt50_corrected(payload: bytes):
    """Parse BT50 with corrected frame structure"""
    if not payload or len(payload) < 32:
        return None

    frames = []
    i = 0
    
    while i + 32 <= len(payload):
        # Look for 0x55 0x61 header
        if payload[i] == 0x55 and payload[i + 1] == 0x61:
            # Based on analysis, acceleration data appears to be at different offsets
            # Let's try offsets 22, 24, 26 (where we saw 4, 6, 3)
            try:
                # Extract as little-endian int16
                vx_raw = struct.unpack('<h', payload[i + 22:i + 24])[0]
                vy_raw = struct.unpack('<h', payload[i + 24:i + 26])[0] 
                vz_raw = struct.unpack('<h', payload[i + 26:i + 28])[0]
                
                # Apply scale factor
                scale = 16.0 / 32768.0
                vx = vx_raw * scale
                vy = vy_raw * scale
                vz = vz_raw * scale
                
                frames.append({
                    'vx': vx, 'vy': vy, 'vz': vz,
                    'raw': (vx_raw, vy_raw, vz_raw),
                    'offset': i
                })
                
                i += 32  # Move to next frame
            except struct.error:
                i += 1
        else:
            i += 1
    
    if not frames:
        return None
        
    # Compute averages
    n = len(frames)
    sum_vx = sum(f['vx'] for f in frames)
    sum_vy = sum(f['vy'] for f in frames)
    sum_vz = sum(f['vz'] for f in frames)
    
    return {
        'samples': frames,
        'VX': sum_vx / n,
        'VY': sum_vy / n,
        'VZ': sum_vz / n,
    }

# Test with actual data
test_hex = "5561000000000000000000000000d1070000000000000400060003000000b0015561000000000000000000000000cb070000000000000400060003000000b0015561000000000000000000000000c4070000000000000400060003000000b0015561000000000000000000000000c4070000000000000400060003000000b001"

test_bytes = bytes.fromhex(test_hex)
print("Testing corrected BT50 parser:")
print(f"Data length: {len(test_bytes)} bytes")

result = parse_bt50_corrected(test_bytes)
if result:
    print(f"✓ SUCCESS: {len(result['samples'])} samples")
    print(f"Averages: VX={result['VX']:.6f}g, VY={result['VY']:.6f}g, VZ={result['VZ']:.6f}g")
    for i, sample in enumerate(result['samples']):
        vx, vy, vz = sample['vx'], sample['vy'], sample['vz']
        raw = sample['raw']
        print(f"Sample {i}: vx={vx:.6f}g, vy={vy:.6f}g, vz={vz:.6f}g (raw: {raw})")
else:
    print("✗ Parser failed")