#!/usr/bin/env python3
"""Analyze BT50 frame structure"""

# From the actual raw data
test_hex = "5561000000000000000000000000d1070000000000000400060003000000b001"

print("BT50 Frame Analysis:")
test_bytes = bytes.fromhex(test_hex)

print(f"Total length: {len(test_bytes)} bytes")
print()

for i in range(0, len(test_bytes), 2):
    if i + 1 < len(test_bytes):
        byte_pair = test_bytes[i:i+2]
        hex_str = byte_pair.hex()
        
        # Try to interpret as little-endian int16
        try:
            val_le = int.from_bytes(byte_pair, 'little', signed=True)
            val_be = int.from_bytes(byte_pair, 'big', signed=True)
            print(f"Offset {i:2d}-{i+1:2d}: {hex_str} -> LE:{val_le:6d}, BE:{val_be:6d}")
        except:
            print(f"Offset {i:2d}-{i+1:2d}: {hex_str}")

print()
print("Looking for significant values (non-zero):")
for i in range(0, len(test_bytes), 2):
    if i + 1 < len(test_bytes):
        byte_pair = test_bytes[i:i+2]
        if byte_pair != b'\x00\x00':
            val_le = int.from_bytes(byte_pair, 'little', signed=True)
            val_be = int.from_bytes(byte_pair, 'big', signed=True)
            print(f"  Offset {i:2d}: {byte_pair.hex()} -> LE:{val_le}, BE:{val_be}")