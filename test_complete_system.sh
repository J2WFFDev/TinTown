#!/bin/bash
# TinTown Bridge Test Script
# Complete automated test sequence for Pi

echo "🚀 TinTown Bridge Test Sequence Starting..."
echo "========================================"

# Step 1: Update code from GitHub
echo ""
echo "📥 Step 1: Updating from GitHub..."
git pull origin main

# Step 2: Kill any existing bridge processes and reset BLE
echo ""
echo "🔄 Step 2: Cleaning up existing processes..."
python3 tools/reset_ble.py

# Step 3: Basic import test
echo ""
echo "🧪 Step 3: Testing module imports..."
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from impact_bridge.ble.wtvb_parse import parse_5561
    from impact_bridge.ble.amg_parse import parse_amg_frame
    print('✅ All parsers import successfully')
except Exception as e:
    print(f'❌ Import failed: {e}')
    exit(1)
"

# Step 4: Device detection
echo ""
echo "📡 Step 4: Scanning for BLE devices..."
timeout 10 python3 tools/ble_scan.py

# Step 5: Critical calibration (establish baseline)
echo ""
echo "🎯 Step 5: CRITICAL - Running calibration to establish baseline..."
echo "This will take about 30 seconds and establish fresh baseline values."
read -p "Press Enter to start calibration (make sure BT50 is stationary)..."
python3 tools/calibrate_bt50_with_logging.py

# Step 6: Check calibration results
echo ""
echo "📊 Step 6: Checking calibration results..."
if [ -d "logs/calibration" ]; then
    latest_cal=$(ls -t logs/calibration/bt50_calibration_*.json | head -1)
    if [ -f "$latest_cal" ]; then
        echo "Latest calibration: $latest_cal"
        echo "Baseline values:"
        python3 -c "
import json
try:
    with open('$latest_cal', 'r') as f:
        data = json.load(f)
    print(f\"  X-axis: {data.get('baseline_x', 'N/A')} raw counts\")
    print(f\"  Y-axis: {data.get('baseline_y', 'N/A')} raw counts\")
    print(f\"  Z-axis: {data.get('baseline_z', 'N/A')} raw counts\")
    print(f\"  Threshold: {data.get('recommended_threshold', 'N/A')} raw counts\")
except Exception as e:
    print(f'Could not read calibration: {e}')
"
    fi
fi

# Step 7: Bridge test
echo ""
echo "🌉 Step 7: Starting Fixed Bridge (main test)..."
echo "This will:"
echo "  - Connect to AMG Timer (60:09:C3:1F:DC:1A)"
echo "  - Connect to BT50 Sensor (F8:FE:92:31:12:E3)"
echo "  - Start impact detection with raw count processing"
echo "  - Log to logs/main/ and logs/debug/"
echo ""
echo "Expected behavior:"
echo "  - Should see connection messages"
echo "  - BT50 data streaming at ~30Hz"
echo "  - AMG frames when timer events occur"
echo "  - Impact events when BT50 is moved/tapped"
echo ""
echo "Press Ctrl+C to stop the bridge when testing is complete."
echo ""
read -p "Press Enter to start the bridge..."

python3 scripts/fixed_bridge.py

echo ""
echo "✅ Test sequence complete!"
echo ""
echo "📋 Post-test checklist:"
echo "  1. Check logs/main/ for event logs (CSV + NDJSON)"
echo "  2. Check logs/debug/ for detailed debug info"
echo "  3. Verify impact detection worked when BT50 was moved"
echo "  4. Verify AMG timer events if timer was used"
echo ""
echo "🔍 To analyze results:"
echo "  - tail -f logs/main/bridge_main_*.ndjson | jq '.'"
echo "  - python3 analyze_bt50.py"
echo "  - python3 tools/detailed_bt50_analysis.py"