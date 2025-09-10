#!/usr/bin/env python3
"""Simple Bleak scan helper — prints address, name, and rssi for discovered devices."""
from bleak import BleakScanner
import asyncio

async def scan():
    print('Starting BLE scan for 10s...')
    devices = await BleakScanner.discover(timeout=10.0)
    print(f'Found {len(devices)} devices')
    for d in devices:
        rssi = getattr(d, 'rssi', None)
        print(f"{d.address}  | {repr(d.name)} | rssi={rssi}")

if __name__ == '__main__':
    asyncio.run(scan())
