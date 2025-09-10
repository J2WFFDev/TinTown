"""WitMotion BT50 vibration sensor BLE client."""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from typing import Callable, Optional, Tuple

from bleak import BleakClient, BleakError


logger = logging.getLogger(__name__)


class Bt50Sample:
    """Represents a single BT50 sensor sample."""
    
    def __init__(self, timestamp_ns: int, vx: float, vy: float, vz: float, amplitude: float):
        self.timestamp_ns = timestamp_ns
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.amplitude = amplitude
    
    def to_dict(self) -> dict:
        """Convert sample to dictionary for logging."""
        return {
            "ts": self.timestamp_ns,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
            "amp": self.amplitude,
        }


class Bt50Client:
    """BLE client for WitMotion BT50 vibration sensor."""
    
    def __init__(
        self,
        sensor_id: str,
        mac_address: str,
        notify_uuid: str,
        config_uuid: str = "",
        adapter: str = "hci0",
        idle_reconnect_sec: float = 300.0,
        keepalive_batt_sec: float = 30.0,
        reconnect_initial_sec: float = 0.1,
        reconnect_max_sec: float = 2.0,
        reconnect_jitter_sec: float = 0.5,
    ) -> None:
        self.sensor_id = sensor_id
        self.mac_address = mac_address
        self.notify_uuid = notify_uuid
        self.config_uuid = config_uuid
        self.adapter = adapter
        self.idle_reconnect_sec = idle_reconnect_sec
        self.keepalive_batt_sec = keepalive_batt_sec
        self.reconnect_initial_sec = reconnect_initial_sec
        self.reconnect_max_sec = reconnect_max_sec
        self.reconnect_jitter_sec = reconnect_jitter_sec
        
        self._client: Optional[BleakClient] = None
        self._connected = False
        self._stop_requested = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        
        # Sample tracking
        self._last_sample_ns: Optional[int] = None
        self._sample_count = 0
        
        # Callbacks
        self._on_sample: Optional[Callable[[Bt50Sample], None]] = None
        self._on_connect: Optional[Callable[[], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
    
    def set_sample_callback(self, callback: Callable[[Bt50Sample], None]) -> None:
        """Set callback for sensor samples."""
        self._on_sample = callback
    
    def set_connect_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for connection events."""
        self._on_connect = callback
    
    def set_disconnect_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for disconnection events."""
        self._on_disconnect = callback
    
    async def start(self) -> None:
        """Start the BT50 client with automatic reconnection."""
        self._stop_requested = False
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
    
    async def stop(self) -> None:
        """Stop the BT50 client and disconnect."""
        self._stop_requested = True
        
        # Cancel tasks
        for task in [self._reconnect_task, self._keepalive_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        await self._disconnect()
    
    async def write_config(self, data: bytes) -> bool:
        """Write configuration to BT50 device if connected and config UUID configured."""
        if not self._connected or not self._client or not self.config_uuid:
            return False
        
        try:
            await self._client.write_gatt_char(self.config_uuid, data)
            return True
        except BleakError as e:
            logger.warning(f"BT50 {self.sensor_id} config write failed: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """Check if sensor is currently connected."""
        return self._connected
    
    @property
    def sample_count(self) -> int:
        """Get total sample count since start."""
        return self._sample_count
    
    def get_status(self) -> dict:
        """Get sensor status information."""
        return {
            "sensor_id": self.sensor_id,
            "connected": self._connected,
            "sample_count": self._sample_count,
            "last_sample_ns": self._last_sample_ns,
        }
    
    async def _reconnect_loop(self) -> None:
        """Main reconnection loop with exponential backoff."""
        retry_delay = self.reconnect_initial_sec
        
        while not self._stop_requested:
            try:
                await self._connect()
                if self._connected:
                    # Reset retry delay on successful connection
                    retry_delay = self.reconnect_initial_sec
                    # Wait for disconnection
                    await self._wait_for_disconnect()
                
            except Exception as e:
                logger.warning(f"BT50 {self.sensor_id} connection failed: {e}")
            
            if not self._stop_requested:
                # Wait before retry with jitter
                jitter = (asyncio.get_event_loop().time() % 1.0) * self.reconnect_jitter_sec
                await asyncio.sleep(retry_delay + jitter)
                
                # Exponential backoff
                retry_delay = min(retry_delay * 2, self.reconnect_max_sec)
    
    async def _keepalive_loop(self) -> None:
        """Keepalive loop to detect idle sensors and force reconnection."""
        while not self._stop_requested:
            await asyncio.sleep(self.keepalive_batt_sec)
            
            if self._connected and self._last_sample_ns:
                idle_time_sec = (time.monotonic_ns() - self._last_sample_ns) / 1_000_000_000
                
                if idle_time_sec > self.idle_reconnect_sec:
                    logger.warning(
                        f"BT50 {self.sensor_id} idle for {idle_time_sec:.1f}s, reconnecting"
                    )
                    await self._disconnect()
    
    async def _connect(self) -> None:
        """Connect to BT50 device and setup notifications."""
        if self._connected:
            return
        
        logger.info(f"Connecting to BT50 {self.sensor_id} at {self.mac_address}")
        
        self._client = BleakClient(
            self.mac_address,
            adapter=self.adapter,
            disconnected_callback=self._on_device_disconnect,
        )
        
        await self._client.connect()
        self._connected = True
        
        # Subscribe to notifications
        await self._client.start_notify(self.notify_uuid, self._handle_notification)
        
        logger.info(f"BT50 {self.sensor_id} connected and notifications enabled")
        
        if self._on_connect:
            self._on_connect()
    
    async def _disconnect(self) -> None:
        """Disconnect from BT50 device."""
        if not self._connected:
            return
        
        self._connected = False
        
        if self._client:
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error during BT50 {self.sensor_id} disconnect: {e}")
            finally:
                self._client = None
        
        if self._on_disconnect:
            self._on_disconnect()
        
        logger.info(f"BT50 {self.sensor_id} disconnected")
    
    async def _wait_for_disconnect(self) -> None:
        """Wait for device to disconnect."""
        while self._connected and not self._stop_requested:
            await asyncio.sleep(1.0)
    
    def _on_device_disconnect(self, client: BleakClient) -> None:
        """Handle device disconnection callback from Bleak."""
        logger.warning(f"BT50 {self.sensor_id} device disconnected")
        self._connected = False
        if self._on_disconnect:
            self._on_disconnect()
    
    def _handle_notification(self, sender: int, data: bytes) -> None:
        """Handle incoming BLE notifications from BT50 sensor."""
        timestamp_ns = time.monotonic_ns()
        self._last_sample_ns = timestamp_ns
        self._sample_count += 1
        
        # Parse BT50 data packet
        sample = self._parse_bt50_data(timestamp_ns, data)
        
        if sample and self._on_sample:
            self._on_sample(sample)
    
    def _parse_bt50_data(self, timestamp_ns: int, data: bytes) -> Optional[Bt50Sample]:
        """
        Parse BT50 notification data into sensor sample.
        
        Expected format: 20-byte packets with acceleration data
        """
        if len(data) != 20:
            logger.debug(f"BT50 {self.sensor_id} unexpected packet length: {len(data)}")
            return None
        
        try:
            # Parse based on known BT50 packet structure
            # This may need adjustment based on actual device behavior
            
            # Extract acceleration values (assuming little-endian format)
            # Bytes 0-1: Header
            # Bytes 2-3: VX (int16)
            # Bytes 4-5: VY (int16) 
            # Bytes 6-7: VZ (int16)
            # Remaining bytes: other sensor data
            
            if data[0] != 0x55 or data[1] != 0x61:  # Check header
                logger.debug(f"BT50 {self.sensor_id} invalid header: {data[0]:02x}{data[1]:02x}")
                return None
            
            # Extract 16-bit signed acceleration values
            vx_raw = struct.unpack("<h", data[2:4])[0]
            vy_raw = struct.unpack("<h", data[4:6])[0]
            vz_raw = struct.unpack("<h", data[6:8])[0]
            
            # Convert to physical units (adjust scale factor as needed)
            # BT50 typically uses mg units (milli-g)
            scale = 1.0 / 32768.0 * 16.0  # Assuming ±16g range
            vx = vx_raw * scale
            vy = vy_raw * scale
            vz = vz_raw * scale
            
            # Calculate amplitude (magnitude)
            amplitude = (vx * vx + vy * vy + vz * vz) ** 0.5
            
            return Bt50Sample(timestamp_ns, vx, vy, vz, amplitude)
            
        except (struct.error, IndexError) as e:
            logger.warning(f"BT50 {self.sensor_id} parse error: {e}")
            return None