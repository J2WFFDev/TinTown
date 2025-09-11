#!/usr/bin/env bash
# Deploy timing calibration code to Raspberry Pi

echo "=== TinTown Timing Calibration Deployment ==="
echo "Copying timing calibration files to Raspberry Pi..."

# Copy the timing calibration module
echo "1. Copying timing_calibration.py..."
scp src/impact_bridge/timing_calibration.py raspberrypi:~/projects/TinTown/src/impact_bridge/

# Copy the updated fixed_bridge.py
echo "2. Copying updated fixed_bridge.py..."
scp scripts/fixed_bridge.py raspberrypi:~/projects/TinTown/scripts/

# Copy the timing calibration config
echo "3. Copying timing calibration config..."
scp latest_timing_calibration.json raspberrypi:~/projects/TinTown/

# Copy integration examples (optional)
echo "4. Copying integration examples..."
scp src/impact_bridge/timing_integration.py raspberrypi:~/projects/TinTown/src/impact_bridge/

# Copy documentation
echo "5. Copying documentation..."
scp doc/timing_calibration_report.md raspberrypi:~/projects/TinTown/doc/
scp TIMING_INTEGRATION_STATUS.md raspberrypi:~/projects/TinTown/

echo ""
echo "=== Deployment Complete ==="
echo "Files copied to Pi:"
echo "  - src/impact_bridge/timing_calibration.py (new timing system)"
echo "  - scripts/fixed_bridge.py (updated with timing integration)"  
echo "  - latest_timing_calibration.json (526ms baseline config)"
echo "  - Documentation and examples"
echo ""
echo "Ready to test on Pi with:"
echo "  ssh raspberrypi 'cd ~/projects/TinTown && sudo python3 scripts/fixed_bridge.py'"