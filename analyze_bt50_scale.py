#!/usr/bin/env python3
"""
BT50 Scale Factor Analysis Tool

This script analyzes captured raw hex data from BT50 sensor to find the correct
scale factor for converting raw bytes to acceleration values in g-force.

We know:
1. Timer shots were fired (confirmed by timer events)
2. BT50 sensor was streaming data during impacts
3. Current scale factor produces values ~10^-33 g (way too small)
4. We need to find the correct interpretation

Test different scale factors and byte interpretations.
"""

import struct
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def _int16_le(b: bytes) -> int:
    """Little-endian signed 16-bit integer"""
    return struct.unpack('<h', b)[0]

def _int16_be(b: bytes) -> int:
    """Big-endian signed 16-bit integer"""
    return struct.unpack('>h', b)[0]

def _uint16_le(b: bytes) -> int:
    """Little-endian unsigned 16-bit integer"""
    return struct.unpack('<H', b)[0]

def _uint16_be(b: bytes) -> int:
    """Big-endian unsigned 16-bit integer"""
    return struct.unpack('>H', b)[0]

def analyze_hex_sample(hex_string: str):
    """Analyze a hex string sample with different scale factors and interpretations"""
    
    print(f"\n=== Analyzing Hex Sample ===")
    print(f"Hex: {hex_string[:64]}...")
    
    # Convert hex to bytes
    payload = bytes.fromhex(hex_string)
    print(f"Length: {len(payload)} bytes")
    
    # Find 0x55 0x61 frames
    frames_found = []
    i = 0
    while i < len(payload) - 32:
        if payload[i] == 0x55 and payload[i+1] == 0x61:
            frames_found.append(i)
            i += 32  # Skip to next potential frame
        else:
            i += 1
    
    print(f"Found {len(frames_found)} frames at offsets: {frames_found}")
    
    if not frames_found:
        print("No 0x55 0x61 frames found!")
        return
    
    # Analyze first frame in detail
    frame_offset = frames_found[0]
    print(f"\n=== Frame Analysis (offset {frame_offset}) ===")
    frame_bytes = payload[frame_offset:frame_offset+32]
    print("Frame hex:", frame_bytes.hex())
    
    # Test acceleration data at different offsets and scale factors
    test_offsets = [2, 6, 10, 14, 18, 22, 26, 30]  # Different potential locations
    scale_factors = [
        1.0,           # Raw values
        1/2048.0,      # Current scale (±16g over ±32768)
        1/1024.0,      # ±32g over ±32768
        1/4096.0,      # ±8g over ±32768  
        1/16384.0,     # ±2g over ±32768
        1/32768.0,     # ±1g over ±32768
        32.0/32768.0,  # ±32g range
        16.0/32768.0,  # ±16g range
        8.0/32768.0,   # ±8g range
        4.0/32768.0,   # ±4g range
        2.0/32768.0,   # ±2g range
        1/655.36,      # Alternative WitMotion scale
        1/16.384,      # Another common scale
        0.001,         # mg scale
        0.01,          # 10mg scale
        0.1,           # 100mg scale
    ]
    
    print(f"\n=== Testing Different Interpretations ===")
    
    for offset in test_offsets:
        if offset + 6 >= len(frame_bytes):
            continue
            
        print(f"\nOffset {offset}:")
        
        # Extract 3 consecutive 16-bit values (X, Y, Z)
        try:
            # Little-endian signed
            vx_raw = _int16_le(frame_bytes[offset:offset+2])
            vy_raw = _int16_le(frame_bytes[offset+2:offset+4]) 
            vz_raw = _int16_le(frame_bytes[offset+4:offset+6])
            
            print(f"  Raw LE signed: X={vx_raw:6d}, Y={vy_raw:6d}, Z={vz_raw:6d}")
            
            # Test interesting scale factors
            for scale in [1/2048.0, 1/1024.0, 16.0/32768.0, 0.001, 0.01]:
                vx_g = vx_raw * scale
                vy_g = vy_raw * scale  
                vz_g = vz_raw * scale
                magnitude = (vx_g**2 + vy_g**2 + vz_g**2)**0.5
                
                print(f"    Scale {scale:10.6f}: X={vx_g:8.4f}g, Y={vy_g:8.4f}g, Z={vz_g:8.4f}g, Mag={magnitude:8.4f}g")
                
        except:
            continue

def main():
    # Sample hex strings from our captured data
    # These are actual BT50 notifications we captured during streaming
    test_samples = [
        # Sample 1 - from baseline streaming
        "556100000000000000000000000045090000000000000900050005000000ae01556100000000000000000000000052090000000000000900050005000000ae0155610000000000000000000000004c090000000000000900050005000000ae015561000000000000000000000000450900000000000900050005000000ae01",
        
        # Sample 2 - different pattern
        "55610000000000000000000000003f090000000000000900050005000000ae01556100000000000000000000000045090000000000000900050005000000ae01556100000000000000000000000071090000000000000900050005000000ae015561000000000000000000000000520900000000000900050005000000ae01",
        
        # Sample 3 - with different values
        "556100000000000000000000000065090000000000000200030001000000ae0155610000000000000000000000003f090000000000000200030001000000ae0155610000000000000000000000004c090000000000000200030001000000ae015561000000000000000000000000580900000000000200030001000000ae01"
    ]
    
    print("BT50 Scale Factor Analysis")
    print("=" * 50)
    print("Goal: Find correct scale factor to convert raw BT50 data to meaningful g-force values")
    print("Current problem: Values are ~10^-33 g, should be ~0.01-1.0 g during impacts")
    
    for i, sample in enumerate(test_samples, 1):
        print(f"\n{'='*20} SAMPLE {i} {'='*20}")
        analyze_hex_sample(sample)
    
    print(f"\n{'='*50}")
    print("ANALYSIS SUMMARY:")
    print("Look for:")
    print("1. Offset where X,Y,Z values make sense (not all zeros or huge numbers)")
    print("2. Scale factor that gives reasonable g-force values (0.01-2.0g range)")
    print("3. Values that change between samples (indicating real sensor data)")
    print("4. Magnitude calculations that are reasonable for sensor at rest or during impact")

if __name__ == "__main__":
    main()