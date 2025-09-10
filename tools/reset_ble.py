#!/usr/bin/env python3
"""
BLE Reset Tool - Clean up any hanging BLE connections
"""

import asyncio
import subprocess
import sys

BT50_SENSOR_MAC = "F8:FE:92:31:12:E3"
AMG_TIMER_MAC = "60:09:C3:1F:DC:1A"

async def reset_ble():
    """Reset BLE connections and clear any hanging processes"""
    print("🔄 Resetting BLE connections...")
    
    # Kill any hanging Python processes
    try:
        result = subprocess.run(['pkill', '-f', 'python.*bridge'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Killed hanging bridge processes")
        else:
            print("ℹ No hanging bridge processes found")
    except Exception as e:
        print(f"⚠ Failed to kill processes: {e}")
    
    # Disconnect devices via bluetoothctl
    devices = [BT50_SENSOR_MAC, AMG_TIMER_MAC]
    
    for mac in devices:
        try:
            # Disconnect device
            result = subprocess.run(['bluetoothctl', 'disconnect', mac], 
                                  capture_output=True, text=True, timeout=5)
            print(f"🔌 Disconnected {mac}: {result.stdout.strip()}")
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"⚠ Failed to disconnect {mac}: {e}")
    
    # Reset Bluetooth adapter
    try:
        subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], check=True)
        await asyncio.sleep(1)
        subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=True)
        print("🔄 Reset Bluetooth adapter")
    except Exception as e:
        print(f"⚠ Failed to reset adapter: {e}")
    
    print("✓ BLE reset complete - devices should be ready for new connections")

if __name__ == "__main__":
    asyncio.run(reset_ble())