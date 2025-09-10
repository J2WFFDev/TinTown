"""Run the simple impact test scenario against the detector with debug prints."""

from impact_bridge.detector import DetectorParams, HitDetector
import time

params = DetectorParams(
    trigger_high=0.5,
    trigger_low=0.1,
    ring_min_ms=10,
    dead_time_ms=50,
    warmup_ms=100,
    baseline_min=0.01,
    min_amp=0.05,
)

det = HitDetector(params, "debug_simple")

start_time = time.monotonic_ns() + params.warmup_ms * 1_000_000

# Build baseline with noise
for i in range(10):
    timestamp = start_time + i * 10_000_000
    det.process_sample(timestamp, 0.02)

impact_samples = [
    (start_time + 200_000_000, 0.1),   # Start rising
    (start_time + 210_000_000, 0.6),   # Above trigger_high
    (start_time + 220_000_000, 0.8),   # Peak
    (start_time + 230_000_000, 0.6),   # Start falling
    (start_time + 240_000_000, 0.3),   # Still above trigger_low
    (start_time + 250_000_000, 0.05),  # Below trigger_low
]

result = None
for timestamp, amplitude in impact_samples:
    print(f"ts={timestamp} amp={amplitude:.3f} baseline={det.current_baseline:.3f} triggered={det._triggered}")
    r = det.process_sample(timestamp, amplitude)
    if r:
        print('DETECTED', r)
        result = r
        break

if not result:
    print('No detection')
