#!/usr/bin/env python3
"""
Minimal Bridge - Pure Connection and Raw Data Logging

This bridge ONLY:
1. Connects to AMG timer and BT50 sensor
2. Logs raw data exactly as received
3. No processing, no analysis, no calculations

Purpose: Isolate connection issues from processing logic issues
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from bleak import BleakClient, BleakScanner
import struct
import logging

class MinimalBridge:
    def __init__(self, log_dir: str | None = None):
        # Device configurations
        self.amg_timer_mac = "60:09:C3:1F:DC:1A"
        self.bt50_sensor_mac = "F8:FE:92:31:12:E3"
        
        # UUIDs for notifications
        self.amg_notify_uuid = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
        self.bt50_notify_uuid = "0000ffe4-0000-1000-8000-00805f9a34fb"  # BT50 actual UUID
        
        # Logging
        self.session_id = str(int(time.time()))
        self.seq_counter = 0
        
        # Setup log directory (default to logs/min)
        self.log_dir = Path(log_dir) if log_dir else Path("logs") / "min"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"minimal_bridge_{timestamp}.ndjson"
        
        print(f"Minimal Bridge starting - Session: {self.session_id}")
        print(f"Logging to: {self.log_file}")
        
    def log(self, msg_type, message, data=None):
        """Log an event in NDJSON format"""
        self.seq_counter += 1
        now = time.time()
        
        # Per logging policy: do not include machine timestamps (ts_ms/t_iso).
        log_entry = {
            "type": msg_type,
            "msg": message,
            "data": data or {},
            "hms": datetime.fromtimestamp(now).strftime("%H:%M:%S.%f")[:-3],
            "seq": self.seq_counter,
            "schema": "minimal_v1",
            "session_id": self.session_id
        }
        
        # Print to console
        print(f"[{log_entry['hms']}] {msg_type.upper()}: {message}")
        if data:
            print(f"    Data: {data}")
        
        # Write to log file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    async def amg_notification_handler(self, sender, data):
        """Handle raw AMG timer notifications"""
        hex_data = data.hex()
        self.log("amg_raw", "AMG timer raw notification", {
            "hex": hex_data,
            "bytes": len(data),
            "sender": str(sender)
        })
        
        # Try to interpret as ASCII if possible
        try:
            ascii_data = data.decode('ascii', errors='ignore')
            if ascii_data.strip():
                self.log("amg_ascii", "AMG timer ASCII data", {
                    "text": ascii_data.strip()
                })
        except:
            pass
    
    async def bt50_notification_handler(self, sender, data):
        """Handle raw BT50 sensor notifications"""
        hex_data = data.hex()
        self.log("bt50_raw", "BT50 sensor raw notification", {
            "hex": hex_data,
            "bytes": len(data),
            "sender": str(sender)
        })
        
        # Try to parse as acceleration data if it's the right size
        if len(data) >= 12:  # 3 floats = 12 bytes minimum
            try:
                # Try different unpacking formats
                if len(data) == 12:
                    vx, vy, vz = struct.unpack('<fff', data)
                    self.log("bt50_accel", "BT50 parsed acceleration", {
                        "vx": vx, "vy": vy, "vz": vz
                    })
                elif len(data) >= 20:  # More data available
                    # Try to unpack timestamp + acceleration
                    parts = struct.unpack('<' + 'f' * (len(data) // 4), data)
                    self.log("bt50_multi", "BT50 multiple values", {
                        "values": list(parts),
                        "count": len(parts)
                    })
            except Exception as e:
                self.log("bt50_parse_error", "Could not parse BT50 data", {
                    "error": str(e)
                })
    
    async def connect_amg_timer(self):
        """Connect to AMG timer"""
        self.log("info", "Attempting AMG timer connection", {
            "mac": self.amg_timer_mac
        })
        
        try:
            # Scan for device first
            self.log("info", "Scanning for AMG timer")
            devices = await BleakScanner.discover(timeout=10.0)
            amg_device = None
            
            for device in devices:
                if device.address.upper() == self.amg_timer_mac.upper():
                    amg_device = device
                    break
            
            if not amg_device:
                self.log("error", "AMG timer not found in scan")
                return None
            
            self.log("info", "AMG timer found, connecting", {
                "name": amg_device.name,
                "rssi": getattr(amg_device, 'rssi', 'unknown')
            })
            
            # Connect to device
            client = BleakClient(amg_device)
            await client.connect()
            
            self.log("success", "AMG timer connected", {
                "connected": client.is_connected,
                "services": len(list(client.services)) if client.services else 0
            })
            
            # Subscribe to notifications
            await client.start_notify(self.amg_notify_uuid, self.amg_notification_handler)
            self.log("success", "AMG timer notifications enabled")
            
            return client
            
        except Exception as e:
            self.log("error", "AMG timer connection failed", {
                "error": str(e),
                "type": type(e).__name__
            })
            return None
    
    async def connect_bt50_sensor(self):
        """Connect to BT50 sensor using proven direct connection method"""
        self.log("info", "Attempting BT50 sensor connection", {
            "mac": self.bt50_sensor_mac
        })
        
        try:
            # Discovery-first approach: find a Bleak device object by address,
            # then connect via that device. This avoids BlueZ races between
            # discovery and direct MAC connect which can cause "Operation
            # already in progress" errors.
            self.log("info", "Using discovery-first method for BT50")
            # small delay to let previous operations settle
            await asyncio.sleep(0.5)
            bt50_device = await BleakScanner.find_device_by_address(self.bt50_sensor_mac, timeout=15.0)
            if not bt50_device:
                raise RuntimeError("BT50 device not found by discovery")

            client = BleakClient(bt50_device, device="hci0")
            await client.connect(timeout=30.0)
            
            self.log("success", "BT50 sensor connected", {
                "connected": client.is_connected,
                "services": len(list(client.services)) if client.services else 0
            })
            
            # Subscribe to notifications
            await client.start_notify(self.bt50_notify_uuid, self.bt50_notification_handler)
            self.log("success", "BT50 sensor notifications enabled")
            
            return client
            
        except Exception as e:
            self.log("error", "BT50 connection failed (discovery-first)", {
                "error": str(e),
                "type": type(e).__name__
            })
            return None

        # Subscribe to notifications
        try:
            await client.start_notify(self.bt50_notify_uuid, self.bt50_notification_handler)
            self.log("success", "BT50 sensor notifications enabled")
        except Exception as e:
            self.log("error", "Failed to enable BT50 notifications", {"error": str(e)})
            try:
                await client.disconnect()
            except Exception:
                pass
            return None

        return client
    
    async def run(self):
        """Main bridge execution"""
        self.log("info", "Minimal Bridge starting", {
            "amg_mac": self.amg_timer_mac,
            "bt50_mac": self.bt50_sensor_mac
        })
        
        # Attempt connections SEQUENTIALLY to avoid "Operation already in progress"
        self.log("info", "Connecting devices sequentially...")
        
        # Connect AMG first
        amg_client = await self.connect_amg_timer()
        
        # Wait a moment before connecting BT50
        await asyncio.sleep(2.0)
        
        # Connect BT50 second  
        bt50_client = await self.connect_bt50_sensor()
        
        # Check connection results
        connected_devices = []
        if amg_client and amg_client.is_connected:
            connected_devices.append("AMG_Timer")
        if bt50_client and bt50_client.is_connected:
            connected_devices.append("BT50_Sensor")
        
        self.log("info", "Connection phase complete", {
            "connected_devices": connected_devices,
            "total_connected": len(connected_devices)
        })
        
        if not connected_devices:
            self.log("error", "No devices connected - exiting")
            return
        
        # Keep running and logging data
        self.log("info", "Starting data monitoring phase")
        print("\n=== MINIMAL BRIDGE ACTIVE ===")
        print("Monitoring raw data from connected devices...")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Run indefinitely, logging raw data as it arrives
            while True:
                await asyncio.sleep(1)
                
                # Periodic status check
                if time.time() % 30 < 1:  # Every 30 seconds
                    status = {}
                    if amg_client:
                        status["amg_connected"] = amg_client.is_connected
                    if bt50_client:
                        status["bt50_connected"] = bt50_client.is_connected
                    
                    self.log("status", "Device status check", status)
                
        except KeyboardInterrupt:
            self.log("info", "Shutdown requested")
        finally:
            # Cleanup connections
            if amg_client and amg_client.is_connected:
                await amg_client.disconnect()
                self.log("info", "AMG timer disconnected")
            if bt50_client and bt50_client.is_connected:
                await bt50_client.disconnect()
                self.log("info", "BT50 sensor disconnected")
            
            self.log("info", "Minimal Bridge shutdown complete")

async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Minimal Bridge")
    parser.add_argument("--log-dir", help="Directory to write logs into (default logs/min)", default=None)
    args = parser.parse_args()

    bridge = MinimalBridge(log_dir=args.log_dir)
    await bridge.run()

if __name__ == "__main__":
    print("=== Minimal Bridge - Pure Connection & Raw Data Logger ===")
    print("Purpose: Test device connections without processing logic")
    print("")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as e:
        print(f"Error: {e}")