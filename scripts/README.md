# TinTown Impact Bridge - Core Scripts

This directory contains the main bridge scripts:

## Key Scripts (to be implemented on Pi):

- `fixed_bridge.py` - Latest production bridge with raw count calibration
- `run_bridge.py` - CLI interface for bridge management  
- `minimal_bridge.py` - Simplified test bridge for debugging

## Usage:

```bash
# Run calibration first (MANDATORY)
python ../tools/calibrate_bt50_with_logging.py

# Start the bridge
python fixed_bridge.py
```

**Note**: These scripts require BLE hardware and should be run on the Raspberry Pi.