"""Main bridge module that coordinates AMG Commander and BT50 sensors."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

from .ble.amg import AmgClient
from .ble.witmotion_bt50 import Bt50Client, Bt50Sample
from .config import AppConfig
from .detector import DetectorParams, HitDetector, MultiPlateDetector
from .logs import DualNdjsonLogger, NdjsonLogger

logger = logging.getLogger(__name__)


class Bridge:
    """Main bridge coordinator for AMG Commander and BT50 sensors."""
    
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        
        # Initialize logging
        if hasattr(config.logging, "debug_dir"):
            self.logger = DualNdjsonLogger(
                config.logging.dir,
                config.logging.debug_dir,
                config.logging.file_prefix,
            )
        else:
            self.logger = NdjsonLogger(config.logging.dir, config.logging.file_prefix)
        
        # Configure logging mode and whitelist
        self.logger.mode = config.logging.mode
        if config.logging.verbose_whitelist:
            self.logger.verbose_whitelist.update(config.logging.verbose_whitelist)
        
        # Timing state
        self.t0_ns: Optional[int] = None
        self._last_amg_ns: Optional[int] = None
        
        # Device clients
        self.amg_client: Optional[AmgClient] = None
        self.bt50_clients: List[Bt50Client] = []
        
        # Detection system
        detector_params = DetectorParams(
            trigger_high=config.detector.trigger_high,
            trigger_low=config.detector.trigger_low,
            ring_min_ms=config.detector.ring_min_ms,
            dead_time_ms=config.detector.dead_time_ms,
            warmup_ms=config.detector.warmup_ms,
            baseline_min=config.detector.baseline_min,
            min_amp=config.detector.min_amp,
        )
        self.detector = MultiPlateDetector(detector_params)
        
        # Sample buffering for analysis (similar to existing system)
        self._bt50_buffers: Dict[str, List[Dict]] = {}
        self._bt50_last_processed: Dict[str, int] = {}
        
        # Control state
        self._stop_requested = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self) -> None:
        """Start the bridge system."""
        self._stop_requested = False
        
        self.logger.status("Bridge starting", {
            "amg_configured": self.config.amg is not None,
            "sensor_count": len(self.config.sensors),
            "detector_params": {
                "trigger_high": self.config.detector.trigger_high,
                "trigger_low": self.config.detector.trigger_low,
                "dead_time_ms": self.config.detector.dead_time_ms,
            },
        })
        
        # Start AMG Commander if configured
        if self.config.amg:
            amg_task = asyncio.create_task(self._run_amg())
            self._tasks.append(amg_task)
        
        # Start BT50 sensors
        for sensor_config in self.config.sensors:
            bt50_task = asyncio.create_task(self._run_bt50(sensor_config))
            self._tasks.append(bt50_task)
        
        # Status reporting task
        status_task = asyncio.create_task(self._status_loop())
        self._tasks.append(status_task)
        
        self.logger.status("Bridge started", {"active_tasks": len(self._tasks)})
    
    async def stop(self) -> None:
        """Stop the bridge system."""
        self._stop_requested = True
        
        self.logger.status("Bridge stopping")
        
        # Stop all clients
        if self.amg_client:
            await self.amg_client.stop()
        
        for client in self.bt50_clients:
            await client.stop()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self.logger.status("Bridge stopped")
        self.logger.close()
    
    async def _run_amg(self) -> None:
        """Run AMG Commander client with reconnection."""
        if not self.config.amg:
            return
        
        while not self._stop_requested:
            try:
                self.amg_client = AmgClient(
                    mac_address=self.config.amg.mac,
                    start_uuid=self.config.amg.start_uuid,
                    write_uuid=self.config.amg.write_uuid,
                    adapter=self.config.amg.adapter,
                    reconnect_initial_sec=self.config.amg.reconnect_initial_sec,
                    reconnect_max_sec=self.config.amg.reconnect_max_sec,
                    reconnect_jitter_sec=self.config.amg.reconnect_jitter_sec,
                )
                
                # Set up callbacks
                self.amg_client.set_t0_callback(self._on_t0)
                self.amg_client.set_notification_callback(self._on_amg_notification)
                self.amg_client.set_connect_callback(self._on_amg_connect)
                self.amg_client.set_disconnect_callback(self._on_amg_disconnect)
                
                # Start AMG client
                await self.amg_client.start()
                
                # Send initial commands if configured
                if self.config.amg.init_cmds:
                    await asyncio.sleep(1.0)  # Wait for connection to stabilize
                    for cmd in self.config.amg.init_cmds:
                        await self.amg_client.write_text(cmd)
                        await asyncio.sleep(0.1)
                
                # Wait for stop or disconnection
                while not self._stop_requested and self.amg_client.is_connected:
                    await asyncio.sleep(1.0)
                
            except Exception as e:
                self.logger.error("AMG client error", {"error": str(e), "type": type(e).__name__})
                await asyncio.sleep(5.0)  # Wait before retry
    
    async def _run_bt50(self, sensor_config) -> None:
        """Run BT50 sensor client with reconnection."""
        sensor_id = sensor_config.sensor
        
        # Add plate to detector
        plate_id = sensor_config.plate or sensor_id
        self.detector.add_plate(plate_id)
        
        # Initialize buffer for this sensor
        self._bt50_buffers[sensor_id] = []
        self._bt50_last_processed[sensor_id] = 0
        
        while not self._stop_requested:
            try:
                client = Bt50Client(
                    sensor_id=sensor_id,
                    mac_address=sensor_config.mac,
                    notify_uuid=sensor_config.notify_uuid,
                    config_uuid=sensor_config.config_uuid,
                    adapter=sensor_config.adapter,
                    idle_reconnect_sec=sensor_config.idle_reconnect_sec,
                    keepalive_batt_sec=sensor_config.keepalive_batt_sec,
                    reconnect_initial_sec=sensor_config.reconnect_initial_sec,
                    reconnect_max_sec=sensor_config.reconnect_max_sec,
                    reconnect_jitter_sec=sensor_config.reconnect_jitter_sec,
                )
                
                # Set up callbacks
                client.set_sample_callback(
                    lambda sample, sid=sensor_id, pid=plate_id: self._on_bt50_sample(sample, sid, pid)
                )
                client.set_connect_callback(lambda sid=sensor_id: self._on_bt50_connect(sid))
                client.set_disconnect_callback(lambda sid=sensor_id: self._on_bt50_disconnect(sid))
                
                # Add to client list
                self.bt50_clients.append(client)
                
                # Start client
                await client.start()
                
                # Wait for stop or disconnection
                while not self._stop_requested and client.is_connected:
                    await asyncio.sleep(1.0)
                
                # Remove from client list
                if client in self.bt50_clients:
                    self.bt50_clients.remove(client)
                
            except Exception as e:
                self.logger.error(f"BT50 {sensor_id} error", {"error": str(e), "type": type(e).__name__})
                await asyncio.sleep(2.0)  # Wait before retry
    
    async def _status_loop(self) -> None:
        """Periodic status reporting."""
        while not self._stop_requested:
            await asyncio.sleep(30.0)  # Report every 30 seconds
            
            status_data = {
                "t0_set": self.t0_ns is not None,
                "amg_connected": self.amg_client.is_connected if self.amg_client else False,
                "bt50_connected": sum(1 for c in self.bt50_clients if c.is_connected),
                "bt50_total": len(self.config.sensors),
                "detector_status": self.detector.get_all_status(),
            }
            
            self.logger.status("Bridge status", status_data)
    
    def _on_t0(self, timestamp_ns: int) -> None:
        """Handle T0 signal from AMG Commander."""
        self.t0_ns = timestamp_ns
        self._last_amg_ns = timestamp_ns
        
        self.logger.event("T0", t_rel_ms=0.0, data={
            "source": "AMG_Commander",
            "timestamp_ns": timestamp_ns,
        })
        
        self.logger.status("T0 received", {"timestamp_ns": timestamp_ns})
    
    def _on_amg_notification(self, data: bytes) -> None:
        """Handle raw AMG notifications for debugging."""
        self.logger.debug("amg_raw", {
            "hex": data.hex(),
            "length": len(data),
        })
    
    def _on_amg_connect(self) -> None:
        """Handle AMG connection."""
        self.logger.status("AMG connected", {
            "mac": self.config.amg.mac if self.config.amg else "unknown",
        })
    
    def _on_amg_disconnect(self) -> None:
        """Handle AMG disconnection."""
        self.logger.status("AMG disconnected")
    
    def _on_bt50_sample(self, sample: Bt50Sample, sensor_id: str, plate_id: str) -> None:
        """Handle BT50 sensor sample."""
        # Add to buffer
        buffer = self._bt50_buffers[sensor_id]
        buffer.append(sample.to_dict())
        
        # Process buffer if we have enough samples
        if len(buffer) >= 5:
            self._process_bt50_buffer(sensor_id, plate_id)
        
        # Check for impact detection
        hit_event = self.detector.process_sample(plate_id, sample.timestamp_ns, sample.amplitude)
        
        if hit_event:
            # Calculate relative time
            t_rel_ms = None
            if self.t0_ns:
                t_rel_ms = (hit_event.timestamp_ns - self.t0_ns) / 1_000_000
            
            self.logger.event("HIT", plate=plate_id, t_rel_ms=t_rel_ms, data={
                "sensor_id": sensor_id,
                "peak_amplitude": hit_event.peak_amplitude,
                "duration_ms": hit_event.duration_ms,
                "rms_amplitude": hit_event.rms_amplitude,
            })
    
    def _process_bt50_buffer(self, sensor_id: str, plate_id: str) -> None:
        """Process accumulated BT50 samples for analysis."""
        buffer = self._bt50_buffers[sensor_id]
        
        if not buffer:
            return
        
        # Log buffer samples for strip chart analysis
        self.logger.debug("bt50_buffer_samples", {
            "sensor_id": sensor_id,
            "plate_id": plate_id,
            "sample_count": len(buffer),
            "samples": buffer.copy(),
        })
        
        # Update processing timestamp
        self._bt50_last_processed[sensor_id] = time.monotonic_ns()
        
        # Clear buffer
        buffer.clear()
    
    def _on_bt50_connect(self, sensor_id: str) -> None:
        """Handle BT50 connection."""
        self.logger.status("BT50 connected", {"sensor_id": sensor_id})
    
    def _on_bt50_disconnect(self, sensor_id: str) -> None:
        """Handle BT50 disconnection."""
        self.logger.status("BT50 disconnected", {"sensor_id": sensor_id})


async def run_bridge(config_path: str) -> None:
    """Run the bridge with the specified configuration."""
    from .config import load_config, validate_config
    
    # Load and validate configuration
    config = load_config(config_path)
    errors = validate_config(config)
    
    if errors:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return
    
    # Create and start bridge
    bridge = Bridge(config)
    
    try:
        await bridge.start()
        
        # Run until interrupted
        while True:
            await asyncio.sleep(1.0)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, stopping bridge")
    finally:
        await bridge.stop()