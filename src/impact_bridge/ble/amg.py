"""AMG Commander BLE client for T0 timing signals."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional, Dict, Any

from bleak import BleakClient, BleakError
from .amg_parse import parse_amg_timer_data, format_amg_event


logger = logging.getLogger(__name__)


class AmgClient:
    """BLE client for AMG Commander timer device."""
    
    def __init__(
        self,
        mac_address: str,
        start_uuid: str,
        write_uuid: str = "",
        adapter: str = "hci0",
        reconnect_initial_sec: float = 2.0,
        reconnect_max_sec: float = 20.0,
        reconnect_jitter_sec: float = 1.0,
    ) -> None:
        self.mac_address = mac_address
        self.start_uuid = start_uuid
        self.write_uuid = write_uuid
        self.adapter = adapter
        self.reconnect_initial_sec = reconnect_initial_sec
        self.reconnect_max_sec = reconnect_max_sec
        self.reconnect_jitter_sec = reconnect_jitter_sec
        
        self._client: Optional[BleakClient] = None
        self._connected = False
        self._stop_requested = False
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_t0: Optional[Callable[[int], None]] = None
        self._on_notification: Optional[Callable[[bytes], None]] = None
        self._on_parsed_data: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_connect: Optional[Callable[[], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
    
    def set_t0_callback(self, callback: Callable[[int], None]) -> None:
        """Set callback for T0 events. Callback receives timestamp_ns."""
        self._on_t0 = callback
    
    def set_notification_callback(self, callback: Callable[[bytes], None]) -> None:
        """Set callback for all notifications. Callback receives raw bytes."""
        self._on_notification = callback
    
    def set_parsed_data_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for parsed AMG data. Callback receives parsed dict."""
        self._on_parsed_data = callback
    
    def set_connect_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for connection events."""
        self._on_connect = callback
    
    def set_disconnect_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for disconnection events."""
        self._on_disconnect = callback
    
    async def start(self) -> None:
        """Start the AMG client with automatic reconnection."""
        self._stop_requested = False
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def stop(self) -> None:
        """Stop the AMG client and disconnect."""
        self._stop_requested = True
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        await self._disconnect()
    
    async def write_command(self, data: bytes) -> bool:
        """Write command to AMG device if connected and write UUID configured."""
        if not self._connected or not self._client or not self.write_uuid:
            return False
        
        try:
            await self._client.write_gatt_char(self.write_uuid, data)
            return True
        except BleakError as e:
            logger.warning(f"AMG write failed: {e}")
            return False
    
    async def write_text(self, text: str) -> bool:
        """Write text command to AMG device."""
        return await self.write_command(text.encode("utf-8"))
    
    async def write_hex(self, hex_string: str) -> bool:
        """Write hex command to AMG device. Format: 'AA-BB-CC' or 'AABBCC'."""
        try:
            # Remove separators and convert to bytes
            hex_clean = hex_string.replace("-", "").replace(" ", "")
            data = bytes.fromhex(hex_clean)
            return await self.write_command(data)
        except ValueError as e:
            logger.error(f"Invalid hex string '{hex_string}': {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """Check if AMG is currently connected."""
        return self._connected
    
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
                logger.warning(f"AMG connection failed: {e}")
            
            if not self._stop_requested:
                # Wait before retry with jitter
                jitter = (asyncio.get_event_loop().time() % 1.0) * self.reconnect_jitter_sec
                await asyncio.sleep(retry_delay + jitter)
                
                # Exponential backoff
                retry_delay = min(retry_delay * 2, self.reconnect_max_sec)
    
    async def _connect(self) -> None:
        """Connect to AMG device and setup notifications."""
        if self._connected:
            return
        
        logger.info(f"Connecting to AMG at {self.mac_address}")
        
        self._client = BleakClient(
            self.mac_address,
            adapter=self.adapter,
            disconnected_callback=self._on_device_disconnect,
        )
        
        await self._client.connect()
        self._connected = True
        
        # Subscribe to notifications
        await self._client.start_notify(self.start_uuid, self._handle_notification)
        
        logger.info("AMG connected and notifications enabled")
        
        if self._on_connect:
            self._on_connect()
    
    async def _disconnect(self) -> None:
        """Disconnect from AMG device."""
        if not self._connected:
            return
        
        self._connected = False
        
        if self._client:
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error during AMG disconnect: {e}")
            finally:
                self._client = None
        
        if self._on_disconnect:
            self._on_disconnect()
        
        logger.info("AMG disconnected")
    
    async def _wait_for_disconnect(self) -> None:
        """Wait for device to disconnect."""
        while self._connected and not self._stop_requested:
            await asyncio.sleep(1.0)
    
    def _on_device_disconnect(self, client: BleakClient) -> None:
        """Handle device disconnection callback from Bleak."""
        logger.warning("AMG device disconnected")
        self._connected = False
        if self._on_disconnect:
            self._on_disconnect()
    
    def _handle_notification(self, sender: int, data: bytes) -> None:
        """Handle incoming BLE notifications."""
        timestamp_ns = time.monotonic_ns()
        
        # Call raw notification callback if set
        if self._on_notification:
            self._on_notification(data)
        
        # Parse AMG data using the new parser
        parsed_data = parse_amg_timer_data(data)
        if parsed_data:
            logger.debug(f"AMG parsed: {format_amg_event(parsed_data)}")
            
            # Call parsed data callback if set
            if self._on_parsed_data:
                self._on_parsed_data(parsed_data)
            
            # Check for T0 signal based on parsed data
            if self._is_t0_from_parsed(parsed_data):
                logger.info(f"T0 signal detected: {format_amg_event(parsed_data)}")
                if self._on_t0:
                    self._on_t0(timestamp_ns)
        else:
            # Fallback to old detection for unparseable data
            if self._is_t0_signal(data):
                logger.info("T0 signal detected from AMG (fallback)")
                if self._on_t0:
                    self._on_t0(timestamp_ns)
    
    def _is_t0_from_parsed(self, parsed_data: Dict[str, Any]) -> bool:
        """
        Detect T0 signal from parsed AMG data.
        
        T0 signals based on AMG protocol analysis:
        - shot_state = 'START' (timer start)
        - shot_state = 'ACTIVE' with shot detection
        """
        shot_state = parsed_data.get('shot_state', '')
        shot_state_raw = parsed_data.get('shot_state_raw', 0)
        type_id = parsed_data.get('type_id', 0)
        
        # Timer start event
        if shot_state == 'START':
            return True
        
        # Shot detection events
        if shot_state == 'ACTIVE':
            # Shot detection: type_id=1, state=3 (BLE push)
            if type_id == 1 and shot_state_raw == 3:
                return True
            # Shot sequence data: type_id 10-26
            if 10 <= type_id <= 26:
                return True
        
        return False
    
    def _is_t0_signal(self, data: bytes) -> bool:
        """
        Detect T0 signal in notification data.
        
        Current detection logic:
        - Primary: 0x01 0x05 prefix
        - Fallback: 14-byte frames starting with 0x01 with zero middle bytes
        """
        if len(data) < 2:
            return False
        
        # Primary T0 pattern: 0x01 0x05
        if data[0] == 0x01 and data[1] == 0x05:
            return True
        
        # Legacy fallback: 14-byte 0x01 frames with mid bytes zero
        if (len(data) == 14 and 
            data[0] == 0x01 and 
            data[5:9] == b'\x00\x00\x00\x00'):
            return True
        
        return False