
from __future__ import annotations
import asyncio, time
from typing import List, Optional
from .config import AppCfg, load_config, DetectorCfg
from .logs import NdjsonLogger
from .detector import HitDetector, DetectorParams
from .ble.amg import AmgClient
from .ble.witmotion_bt50 import Bt50Client
from .ble.wtvb_parse import parse_5561

class Bridge:
    def __init__(self, cfg: AppCfg):
        self.cfg = cfg
        self.logger = NdjsonLogger(cfg.logging.dir, cfg.logging.file_prefix)
        # Apply logging mode and whitelist from config if present
        try:
            if hasattr(cfg.logging, 'mode'):
                self.logger.mode = cfg.logging.mode or self.logger.mode
            if hasattr(cfg.logging, 'verbose_whitelist') and cfg.logging.verbose_whitelist:
                # merge any configured whitelist with env-derived whitelist
                self.logger.verbose_whitelist.update(cfg.logging.verbose_whitelist)
        except Exception:
            pass
        self.t0_ns: Optional[int] = None
        self._last_amg_ns: Optional[int] = None
        self._pending_session: bool = False
        self.amg: Optional[AmgClient] = None
        self.bt_clients: List[Bt50Client] = []
        self.detectors = {}
        self._stream_stats = {}
        self._stop = False
        self._bt_tasks: List[asyncio.Task] = []
        
        # BT50 sample buffering for impact counting
        self._bt50_samples = {}  # sensor_id -> list of (ts_ns, amp, vx, vy, vz)
        self._bt50_last_processed = {}  # sensor_id -> last processed timestamp

    async def _check_process_conflicts(self):
        """Check for competing bridge processes that could cause Bluetooth conflicts"""
        try:
            import subprocess
            # Check for bridge-related processes
            result = subprocess.run(
                ["ps", "aux"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                bridge_processes = []
                
                for line in lines:
                    if any(pattern in line.lower() for pattern in ['bridge.py', 'run_bridge', 'minimal_bridge', 'steelcity']):
                        if 'grep' not in line.lower() and 'ps aux' not in line.lower():
                            bridge_processes.append(line.strip())
                
                if bridge_processes:
                    self.logger.write({
                        "type": "warning",
                        "msg": "Competing_processes_detected",
                        "data": {
                            "count": len(bridge_processes),
                            "processes": bridge_processes[:3],  # Log first 3 processes
                            "recommendation": "Kill competing processes to avoid Bluetooth conflicts"
                        }
                    })
                else:
                    self.logger.write({
                        "type": "info",
                        "msg": "Process_check_passed",
                        "data": {"competing_processes": 0}
                    })
            else:
                self.logger.write({
                    "type": "warning", 
                    "msg": "Process_check_failed",
                    "data": {"error": "could_not_run_ps_command"}
                })
                
        except Exception as e:
            self.logger.write({
                "type": "warning",
                "msg": "Process_check_error",
                "data": {"error": str(e), "type": type(e).__name__}
            })

    async def start(self):
        # PRE-FLIGHT: Check for competing bridge processes that could cause conflicts
        await self._check_process_conflicts()
        
        # Start AMG listener with reconnect/backoff loop (only if AMG is configured)
        async def _amg_loop():
            backoff = max(0.0, float(self.cfg.amg.reconnect_initial_sec))
            max_b = max(backoff, float(self.cfg.amg.reconnect_max_sec))
            jitter = max(0.0, float(self.cfg.amg.reconnect_jitter_sec))
            while not self._stop:
                self.amg = AmgClient(
                    self.cfg.amg.adapter,
                    self.cfg.amg.mac or self.cfg.amg.name,
                    self.cfg.amg.start_uuid,
                    self.cfg.amg.write_uuid,
                    self.cfg.amg.commands,
                )
                self.amg.on_t0(self._on_t0)
                # Optional raw dump for debugging
                self.amg.on_raw(lambda ts, raw: self._on_amg_raw(ts, raw))
                # Structured signals
                self.amg.on_signal(lambda ts, name, raw: self._on_amg_signal(ts, name, raw))
                try:
                    # Log intent to connect
                    self.logger.write({
                        "type": "info",
                        "msg": "Bridge_connecting_Timer",
                        "data": {
                            "adapter": self.cfg.amg.adapter,
                            "target": self.cfg.amg.mac or self.cfg.amg.name,
                            "start_uuid": self.cfg.amg.start_uuid,
                        },
                    })
                    await self.amg.start()
                    # Log AMG connection info (subscription started)
                    self.logger.write({
                        "type": "info",
                        "msg": "Timer_connected",
                        "data": {
                            "adapter": self.cfg.amg.adapter,
                            "mac": self.cfg.amg.mac,
                            "device_category": "Smart Timer",
                            "device_id": self.cfg.amg.mac[-5:].replace(":", ""),
                            "start_uuid": self.cfg.amg.start_uuid,
                            "subscribed": True,
                        },
                    })
                    # Optional initial commands
                    try:
                        cmds = (self.cfg.amg.init_cmds or [])
                        for cmd in cmds:
                            if not isinstance(cmd, dict):
                                continue
                            delay_ms = int(cmd.get("delay_ms", 0)) if hasattr(cmd, "get") else 0
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms/1000.0)
                            payload: Optional[bytes] = None
                            if hasattr(cmd, "get") and cmd.get("text") is not None:
                                payload = str(cmd.get("text")).encode("utf-8")
                            elif hasattr(cmd, "get") and cmd.get("hex") is not None:
                                hx = str(cmd.get("hex")).replace(" ", "").replace("-", ":").replace(",", ":")
                                parts = [p for p in hx.split(":") if p]
                                try:
                                    payload = bytes(int(p, 16) for p in parts)
                                except Exception:
                                    payload = None
                            if payload:
                                try:
                                    await self.amg.write_cmd(payload, response=True)
                                    self.logger.write({"type":"debug","msg":"amg_write_init","data":{"len": len(payload), "hex": payload.hex()}})
                                except Exception as e:
                                    self.logger.write({"type":"error","msg":"amg_write_failed","data":{"error": str(e)}})
                    except Exception as e:
                        self.logger.write({"type":"error","msg":"amg_init_cmds_error","data":{"error": str(e)}})

                    # Wait indefinitely until AMG disconnects
                    try:
                        await self.amg.wait_disconnect()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    # Log disconnect state (normal or error path will also come here)
                    self.logger.write({
                        "type": "info",
                        "msg": "Timer_disconnected",
                        "data": {"adapter": self.cfg.amg.adapter, "target": self.cfg.amg.mac or self.cfg.amg.name},
                    })
                except Exception as e:
                    # Proceed even if AMG is not available; BT50 can still stream
                    self.logger.write({
                        "type": "error",
                        "msg": "Timer_connect_failed",
                        "data": {"adapter": self.cfg.amg.adapter, "mac": self.cfg.amg.mac, "error": str(e)}
                    })
                finally:
                    try:
                        if self.amg:
                            await self.amg.stop()
                    except Exception:
                        pass
                # Backoff before retry
                if self._stop:
                    break
                # simple exponential backoff with cap and small jitter
                await asyncio.sleep(min(max_b, backoff) + (jitter if jitter > 0 else 0))
                backoff = min(max_b, max(1.0, backoff * 1.7))

        # SEQUENTIAL CONNECTION STRATEGY to avoid "Operation already in progress" errors
        self.logger.write({
            "type": "info",
            "msg": "Bridge_startup",
            "data": {"strategy": "sequential_connections", "amg_first": True}
        })

        # Only start AMG loop if AMG is configured (has MAC or name)
        if self.cfg.amg.mac or self.cfg.amg.name:
            self.logger.write({
                "type": "info",
                "msg": "AMG_connecting",
                "data": {"phase": "1_amg_first"}
            })
            asyncio.create_task(_amg_loop())
            
            # Wait 2 seconds before starting BT50 connections to avoid Bluetooth conflicts
            self.logger.write({
                "type": "info",
                "msg": "Sequential_delay",
                "data": {"wait_seconds": 2.0, "reason": "avoid_bluetooth_conflicts"}
            })
            await asyncio.sleep(2.0)
        else:
            self.logger.write({
                "type": "info",
                "msg": "AMG_skipped",
                "data": {"reason": "no_mac_or_name_configured"}
            })

        # Start BT50 sensor loops AFTER AMG connection attempt  
        self.logger.write({
            "type": "info",
            "msg": "BT50_connecting",
            "data": {"phase": "2_bt50_second", "sensor_count": len(self.cfg.sensors)}
        })
        for s in self.cfg.sensors:
            task = asyncio.create_task(self._bt50_loop(s.sensor, s.adapter, s.mac, s.notify_uuid, s.config_uuid))
            self._bt_tasks.append(task)

        # Periodic status
        asyncio.create_task(self._status_task())

    async def _status_task(self):
        while True:
            self.logger.write({
                "type":"status",
                "t_rel_ms": None if self.t0_ns is None else (time.monotonic_ns()-self.t0_ns)/1e6,
                "msg":"alive",
                "data":{"sensors": list(self.detectors.keys())}
            })
            await asyncio.sleep(5)

    async def _bt50_loop(self, sensor_id: str, adapter: str, mac: str, notify_uuid: str, config_uuid: Optional[str]):
        """Maintain a BT50 connection with reconnects."""
        # Pull per-sensor config for backoff and keepalive/idle
        scfg = None
        for s in self.cfg.sensors:
            if s.sensor == sensor_id and s.mac == mac:
                scfg = s
                break
        reconnect_initial = float(getattr(scfg, "reconnect_initial_sec", 2.0) if scfg else 2.0)
        reconnect_max = float(getattr(scfg, "reconnect_max_sec", 20.0) if scfg else 20.0)
        reconnect_jitter = float(getattr(scfg, "reconnect_jitter_sec", 1.0) if scfg else 1.0)
        backoff = max(0.0, reconnect_initial)
        while not self._stop:
            cli = Bt50Client(adapter, mac, notify_uuid, config_uuid)
            # apply tunables
            if scfg:
                cli.idle_reconnect_sec = float(getattr(scfg, "idle_reconnect_sec", cli.idle_reconnect_sec))
                cli.keepalive_batt_sec = float(getattr(scfg, "keepalive_batt_sec", cli.keepalive_batt_sec))
            cli.on_packet(lambda ts, data, p=sensor_id: self._on_bt50_packet(p, ts, data))
            # Log intent to connect
            self.logger.write({"type": "info", "msg": "Sensor_connecting", "data": {"sensor_id": sensor_id, "adapter": adapter, "mac": mac}})
            try:
                await cli.start()
            except Exception as e:
                self.logger.write({"type": "error", "msg": "Sensor_connect_failed", "data": {"sensor_id": sensor_id, "adapter": adapter, "mac": mac, "error": str(e)}})
                # backoff then retry
                await asyncio.sleep(min(reconnect_max, backoff) + reconnect_jitter)
                backoff = min(reconnect_max, max(1.0, backoff * 1.7))
                continue

            if cli not in self.bt_clients:
                self.bt_clients.append(cli)
            if sensor_id not in self.detectors:
                self.detectors[sensor_id] = HitDetector(DetectorParams(**self.cfg.detector.__dict__))
            # Log connection details
            self.logger.write({"type": "info", "msg": "Sensor_connected", "data": {"sensor_id": sensor_id, "adapter": adapter, "mac": mac, "notify_uuid": notify_uuid}})
            
            # Initialize t0_ns for BT50-only mode (since AMG is disabled)
            if self.t0_ns is None:
                self.t0_ns = time.time_ns()
                self.logger.write({
                    "type": "event",
                    "msg": "Timer_START_BTN", 
                    "data": {"method": "bt50_connection_init"}
                })
            
            # reset backoff on success
            backoff = reconnect_initial
            # Snapshot battery and services (best-effort)
            try:
                batt = await cli.read_battery_level()
            except Exception:
                batt = None
            self.logger.write({"type": "info", "msg": "Sensor_battery", "data": {"sensor_id": sensor_id, "battery_pct": batt}})
            try:
                svcs = await cli.list_services()
            except Exception:
                svcs = []
            if svcs:
                self.logger.write({"type": "info", "msg": "Sensor_services", "data": {"sensor_id": sensor_id, "services": svcs[:12]}})

            # Wait for disconnect
            try:
                await cli.wait_disconnect()
            except Exception:
                pass
            self.logger.write({"type": "info", "msg": "Sensor_disconnected", "data": {"sensor_id": sensor_id}})
            try:
                await cli.stop()
            except Exception:
                pass
            await asyncio.sleep(min(reconnect_max, backoff) + reconnect_jitter)
            backoff = min(reconnect_max, max(1.0, backoff * 1.7))

    def _on_t0(self, t0_ns: int, raw: bytes):
        # If we haven't already marked a session start, infer a start button at T0
        if not self._pending_session:
            self._pending_session = True
            self.logger.write({
                "type": "event",
                "msg": "Timer_START_BTN",
                "data": {"raw": raw.hex(), "method": "inferred_at_t0"}
            })
        self.t0_ns = t0_ns
        self.logger.write({"type":"event","t_rel_ms":0.0,"msg":"T0","data":{"raw": raw.hex()}})

    def _on_amg_raw(self, ts_ns: int, raw: bytes):
        if getattr(self.amg, "debug_raw", False):
            self.logger.write({"type":"debug","msg":"shot_raw","data":{"raw": raw.hex()}})
        # Track last AMG activity to help infer start button prior to T0
        self._last_amg_ns = ts_ns

    def _on_amg_signal(self, ts_ns: int, name: str, raw: bytes):
        # Generic structured AMG signal event; specific T0 handling remains in _on_t0 for t0_ns state.
        if name == "T0":
            self.logger.write({"type":"event","msg":f"Timer_T0","data":{"raw": raw.hex()}})
        elif name == "SHOT_RAW":
            # Process individual shot events
            device_id = getattr(self.amg, 'mac', 'DC1A')[-4:] if hasattr(self.amg, 'mac') else "DC1A"
            shot_time_ms = round(ts_ns / 1_000_000, 3)
            
            # Create SHOT_RAW event with chronological timestamp for actual shots
            event_data = {
                "type": "event",
                "msg": "SHOT_RAW",
                "data": {
                    "device_id": device_id,
                    "timestamp_ms": shot_time_ms,
                    "signal": "shot_report",
                    "raw": raw.hex()
                }
            }
            if self.t0_ns is not None:
                event_data["t_rel_ms"] = (ts_ns - self.t0_ns) / 1e6
            self.logger.write(event_data)
        elif name == "ARROW_END":
            self.logger.write({"type":"event","msg":f"String_END","data":{"raw": raw.hex()}})
        elif name == "TIMEOUT_END":
            self.logger.write({"type":"event","msg":f"String_TIMEOUT_END","data":{"raw": raw.hex()}})
        else:
            self.logger.write({"type":"event","msg":f"Timer_{name}","data":{"raw": raw.hex()}})
        # If explicit end signals appear, close the session
        if name in ("ARROW_END", "TIMEOUT_END"):
            reason = "arrow" if name == "ARROW_END" else "timeout"
            self.logger.write({"type":"event","msg":"Timer_SESSION_END","data":{"reason": reason}})
            # Clear t0; optionally we could rotate session_id if desired in the logger
            self.t0_ns = None
            # Reset pending-session marker so next T0 can infer a new start
            self._pending_session = False

    def _on_bt50_packet(self, sensor_id: str, ts_ns: int, payload: bytes):
        # Prefer structured parse per WTVB01-BT50 manual (HDR 0x55, FLAG 0x61)
        # Fallback to byte-energy heuristic if parse fails.
        if not payload:
            return
        pkt = parse_5561(payload)
        if pkt is not None:
            # Use velocity magnitude (mm/s) as amplitude proxy
            vx, vy, vz = pkt['VX'], pkt['VY'], pkt['VZ']
            amp = (vx*vx + vy*vy + vz*vz) ** 0.5
        else:
            s = sum(b*b for b in payload) / len(payload)
            amp = float(s**0.5)  # pseudo-RMS of payload bytes
            vx = vy = vz = 0.0  # Fallback values

        # Initialize sample buffer for this sensor
        if sensor_id not in self._bt50_samples:
            self._bt50_samples[sensor_id] = []
            self._bt50_last_processed[sensor_id] = 0
            # Log buffer initialization
            self.logger.write({
                "type": "debug",
                "msg": "bt50_buffer_init",
                "data": {"sensor_id": sensor_id, "init_ts_ns": ts_ns}
            })
        
        # Add sample to buffer
        self._bt50_samples[sensor_id].append((ts_ns, amp, vx, vy, vz))
        
        # Process buffered samples every ~2 seconds (similar to bt50_stream timing)
        buffer = self._bt50_samples[sensor_id]
        time_window_ns = 2_000_000_000  # 2 seconds in nanoseconds
        
        # Debug buffer status every 20 samples or when we have motion or always for first 5 packets
        time_since_last = (ts_ns - self._bt50_last_processed[sensor_id]) / 1_000_000  # ms
        ready_to_process = len(buffer) >= 40 and time_since_last > 2000
        
        if len(buffer) <= 5 or len(buffer) % 20 == 0 or amp > 0.1 or ready_to_process:
            self.logger.write({
                "type": "debug",
                "msg": "bt50_buffer_status", 
                "data": {
                    "sensor_id": sensor_id,
                    "buffer_size": len(buffer),
                    "time_since_last_ms": round(time_since_last, 1),
                    "ready_to_process": ready_to_process,
                    "current_amp": round(amp, 3),
                    "current_vx": round(vx, 3),
                    "current_vy": round(vy, 3), 
                    "current_vz": round(vz, 3),
                    "last_processed_ns": self._bt50_last_processed[sensor_id]
                }
            })
        
        if len(buffer) >= 40 and (ts_ns - self._bt50_last_processed[sensor_id]) > time_window_ns:
            self._process_bt50_buffer(sensor_id, ts_ns)
            self._bt50_last_processed[sensor_id] = ts_ns
    
    def _process_bt50_buffer(self, sensor_id: str, ts_ns: int):
        """Process buffered BT50 samples to detect discrete impact events with double tap classification"""
        # Debug: Function called successfully
        self.logger.write({
            "type": "debug",
            "msg": "PROCESSING_BUFFER_CALLED",
            "data": {"sensor_id": sensor_id}
        })
        
        buffer = self._bt50_samples[sensor_id]
        if not buffer:
            return
        # Log buffer samples for strip chart analysis
        self.logger.write({
            "type": "debug",
            "msg": "bt50_buffer_samples",
            "data": {
                "sensor_id": sensor_id,
                "sample_count": len(buffer),
                "samples": [
                    {"ts": ts, "amp": amp, "vx": vx, "vy": vy, "vz": vz}
                    for (ts, amp, vx, vy, vz) in buffer[:50]
                ]
            }
        })
            
        # Extract amplitudes and detect peaks
        peaks = self._detect_impact_peaks(buffer)
        impact_count = len(peaks)
        max_amp = max([sample[1] for sample in buffer]) if buffer else 0.0
        total_amp = sum([sample[1] for sample in buffer])
        
        # Classify peak patterns (single, double tap, etc.)
        impact_classifications = self._classify_impact_patterns(peaks)
        
        # Calculate aggregated amplitude for detector (similar to bt50_stream avg_amp)
        avg_amp = total_amp / len(buffer) if buffer else 0.0
        
        # Process through detector with aggregated amplitude
        det = self.detectors[sensor_id]
        hit = det.update(avg_amp, dt_ms=2000.0)  # 2-second window
        
        # Count impacts by intensity level
        intensity_counts = {'LIGHT': 0, 'MEDIUM': 0, 'HEAVY': 0}
        peak_amplitudes = []
        for peak in peaks:
            intensity_counts[peak['intensity']] += 1
            peak_amplitudes.append(peak['amplitude'])
        
        # ALWAYS log buffer analysis and write detailed data for inspection
        self.logger.write({
            "type": "debug", 
            "msg": "bt50_impact_analysis",
            "data": {
                "sensor_id": sensor_id,
                "sample_count": len(buffer),
                "impact_count": impact_count,
                "avg_amp": round(avg_amp, 3),
                "max_amp": round(max_amp, 3),
                "detector_hit": hit,
                "peaks_detected": len(peaks),
                "impact_types": impact_classifications,
                "intensity_counts": intensity_counts,
                "peak_amplitudes": peak_amplitudes,
                "noise_samples": len([s for s in buffer if s[1] < 5.0]),
                "above_threshold": len([s for s in buffer if s[1] >= 10.0]),
                "t0_ns_set": self.t0_ns is not None,
                "detector_state": det.state if hasattr(det, 'state') else None,
                "detector_armed": det.armed if hasattr(det, 'armed') else None,
                "idle_rms": round(det.idle_rms, 6),
            }
        })
        
        # ALWAYS write detailed buffer data to text file for analysis
        self._write_detailed_buffer(sensor_id, buffer, avg_amp, impact_count, hit)
        
        # Generate individual impact events for each detected peak (like AMG_RAW format)
        if impact_count > 0 and self.t0_ns is not None:
            # Get device identifier from BT50 MAC (last 4 characters)
            device_id = sensor_id[-4:] if len(sensor_id) >= 4 else sensor_id
            
            for i, (peak, classification) in enumerate(zip(peaks, impact_classifications)):
                t_rel_ms = (ts_ns - self.t0_ns)/1e6
                
                # Create individual impact event similar to AMG_RAW format
                impact_event = {
                    "type": "event",
                    "sensor_id": sensor_id,
                    "device_id": device_id,  # Last 4 of MAC (12E3 for BT50)
                    "t_rel_ms": t_rel_ms,
                    "event_type": "BT50_RAW",  # Similar to AMG_RAW
                    "msg": f"Impact #{i + 1} detected",  # Similar to "Shot #1 detected"
                    "signal_description": f"Impact #{i + 1} detected",
                    "raw_data": {
                        "peak_amplitude": round(peak['amplitude'], 3),
                        "frame_index": peak['frame_idx'],
                        "peak_timestamp": round(peak['timestamp'], 1),
                        "impact_type": classification,
                        "intensity": peak['intensity']
                    }
                }
                self.logger.write(impact_event)
        
        # Clear processed samples (keep recent ones for overlap)
        keep_recent = 10  # Keep last 10 samples for continuity
        self._bt50_samples[sensor_id] = buffer[-keep_recent:] if len(buffer) > keep_recent else []

    def _detect_impact_peaks(self, buffer):
        """Detect discrete impact peaks in BT50 buffer using amplitude thresholds"""
        peaks = []
        if not buffer:
            return peaks
            
        # Extract timestamps and amplitudes
        frame_data = [(i, sample[0], sample[1]) for i, sample in enumerate(buffer)]
        
        # Find amplitude peaks above baseline threshold (based on observed data)
        # Background noise: 1-4, Light impacts: 10-15, Medium: 15-40, Heavy: >40
        peak_threshold = 10.0  # Minimum amplitude to consider a real impact
        for i, (frame_idx, timestamp, amplitude) in enumerate(frame_data):
            if amplitude > peak_threshold:
                # Check if this is a local maximum
                is_peak = True
                
                # Check neighbors within 3 frames (avoid double-counting resonance)
                for j in range(max(0, i-3), min(len(frame_data), i+4)):
                    if j != i and frame_data[j][2] > amplitude:
                        is_peak = False
                        break
                
                if is_peak:
                    # Classify impact intensity based on amplitude
                    if amplitude >= 40.0:
                        intensity = 'HEAVY'
                    elif amplitude >= 15.0:
                        intensity = 'MEDIUM'
                    else:
                        intensity = 'LIGHT'
                    
                    peaks.append({
                        'frame_idx': frame_idx,
                        'timestamp': timestamp, 
                        'amplitude': amplitude,
                        'intensity': intensity
                    })
        
        return peaks

    def _classify_impact_patterns(self, peaks):
        """Classify impact patterns as single, double tap, triple tap, etc."""
        if len(peaks) <= 1:
            return ['SINGLE'] if peaks else []
            
        classifications = []
        i = 0
        
        while i < len(peaks):
            if i == len(peaks) - 1:
                # Last peak - single
                classifications.append('SINGLE')
                i += 1
                continue
                
            # Check separation to next peak
            current_peak = peaks[i]
            next_peak = peaks[i + 1]
            separation_ms = next_peak['timestamp'] - current_peak['timestamp']
            
            # Double tap detection: 100-200ms separation with amplitude increase
            if 100 <= separation_ms <= 200:
                amp_ratio = next_peak['amplitude'] / max(current_peak['amplitude'], 0.1)
                if amp_ratio >= 1.5:  # At least 50% amplitude increase
                    classifications.extend(['DOUBLE_TAP_1', 'DOUBLE_TAP_2'])
                    i += 2  # Skip next peak since we classified both
                    continue
            
            # Resonance: 25-90ms separation  
            elif 25 <= separation_ms <= 90:
                classifications.append('RESONANCE')
                i += 1
                continue
                
            # Single tap (large separation)
            else:
                classifications.append('SINGLE')
                i += 1
                
        return classifications

        # Periodic telemetry to confirm streaming and help calibrate
        st = self._stream_stats.get(sensor_id)
        if st is None:
            st = {"n": 0, "sum": 0.0, "last_ns": ts_ns}
            self._stream_stats[sensor_id] = st
        st["n"] += 1
        st["sum"] += amp
        if st["n"] >= 200 or (ts_ns - st["last_ns"]) > 2_000_000_000:
            avg = st["sum"] / max(1, st["n"])
            data = {"sensor_id": sensor_id, "samples": st["n"], "avg_amp": round(avg, 3)}
            # Include a snapshot of parsed fields occasionally if parse succeeded recently
            if pkt is not None:
                # keep it compact: only a few fields
                data.update({"avg_vx": pkt['VX'], "avg_vy": pkt['VY'], "avg_vz": pkt['VZ'], "temp_c": pkt['TEMP']})
            self.logger.write({"type":"info","msg":"bt50_stream","data": data})
            st["n"] = 0
            st["sum"] = 0.0
            st["last_ns"] = ts_ns

    def _write_detailed_buffer(self, sensor_id: str, buffer, avg_amp: float, impact_count: int, hit):
        """Write detailed buffer data to text file for analysis"""
        import datetime as dt
        
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/buffer_detail_{sensor_id}_{timestamp}_amp{avg_amp:.3f}_impacts{impact_count}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write(f"# BT50 Buffer Detail Analysis\n")
                f.write(f"# Sensor: {sensor_id}\n")
                f.write(f"# Timestamp: {timestamp}\n")
                f.write(f"# Buffer Size: {len(buffer)} samples\n")
                f.write(f"# Average Amplitude: {avg_amp:.3f}\n")
                f.write(f"# Impact Count: {impact_count}\n")
                f.write(f"# Detector Hit: {hit}\n")
                f.write(f"#\n")
                f.write(f"# Format: sample_idx, ts_ns, amplitude, vx_mm_s, vy_mm_s, vz_mm_s\n")
                f.write(f"#\n")
                
                for i, (ts_ns, amp, vx, vy, vz) in enumerate(buffer):
                    f.write(f"{i:3d}, {ts_ns:15d}, {amp:8.3f}, {vx:8.3f}, {vy:8.3f}, {vz:8.3f}\n")
                
                f.write(f"\n# Summary Statistics:\n")
                f.write(f"# Max Amplitude: {max(sample[1] for sample in buffer):.3f}\n")
                f.write(f"# Non-zero Velocities: {sum(1 for _, _, vx, vy, vz in buffer if abs(vx) > 0.001 or abs(vy) > 0.001 or abs(vz) > 0.001)}\n")
                f.write(f"# Time Span: {(buffer[-1][0] - buffer[0][0]) / 1_000_000:.1f} ms\n")
                
            self.logger.write({
                "type": "info",
                "msg": "buffer_detail_written", 
                "data": {"sensor_id": sensor_id, "filename": filename, "samples": len(buffer)}
            })
        except Exception as e:
            self.logger.write({
                "type": "error",
                "msg": "buffer_detail_write_failed",
                "data": {"sensor_id": sensor_id, "error": str(e)}
            })

    async def stop(self):
        self._stop = True
        for t in self._bt_tasks:
            t.cancel()
            try:
                await t
            except Exception:
                pass
        for cli in self.bt_clients:
            try:
                await cli.stop()
            except Exception:
                pass
        if self.amg:
            try:
                await self.amg.stop()
            except Exception:
                pass

async def run(config_path: str):
    cfg = load_config(config_path)
    br = Bridge(cfg)
    await br.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await br.stop()
