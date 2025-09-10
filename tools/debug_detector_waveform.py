"""Run the synthetic waveform against the detector with debug prints."""

from impact_bridge.detector import DetectorParams, HitDetector
import time

params = DetectorParams(
    trigger_high=0.1,
    trigger_low=0.05,
    ring_min_ms=20,
    dead_time_ms=100,
    warmup_ms=50,
    baseline_min=0.001,
    min_amp=0.01,
)

det = HitDetector(params, "debug_plate")

# Generate waveform similar to test
start_time = time.monotonic_ns() + params.warmup_ms * 1_000_000

# Build baseline
for i in range(20):
    timestamp = start_time + i * 5_000_000
    det.process_sample(timestamp, 0.005)

# Generate waveform
impact_start = start_time + 200_000_000
sample_interval_ns = 5_000_000

peak_amp = 0.5
duration_ms = 40
num_samples = duration_ms // 5

print('num_samples', num_samples)

result = None
for i in range(num_samples):
    timestamp = impact_start + i * sample_interval_ns
    progress = i / max(1, (duration_ms // 5))
    if progress <= 0.3:
        amplitude = peak_amp * (progress / 0.3)
    elif progress <= 0.7:
        amplitude = peak_amp * (0.9 + 0.1 * (0.5 - abs(progress - 0.5)))
    else:
        amplitude = peak_amp * (1.0 - progress) / 0.3
    
    # Add small noise
    amplitude += 0.001 * peak_amp
    amplitude = max(0, amplitude)
    
    print(f"i={i} ts={timestamp} amp={amplitude:.4f} baseline={det.current_baseline:.5f} triggered={det._triggered}")
    r = det.process_sample(timestamp, amplitude)
    if r:
        result = r
        print('DETECTED', r)
        break

if not result:
    print('No detection')
