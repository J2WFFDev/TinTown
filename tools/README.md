# TinTown Impact Bridge - Tools

This directory contains utilities and calibration tools:

## Key Tools (to be implemented on Pi):

- `calibrate_bt50_with_logging.py` - **MANDATORY** calibration before bridge startup
- `reset_ble.py` - BLE connection cleanup utility
- `ble_scan.py` - Device discovery and scanning
- `database.py` - Database management and validation

## Critical Calibration Requirement:

```bash
# MUST run before starting bridge - establishes baseline values
python calibrate_bt50_with_logging.py
```

**Current Validated Baseline (Session 20250909_174244):**
- X-axis: 2089 raw counts (gravity-oriented)
- Y-axis: 0 raw counts  
- Z-axis: 0 raw counts
- Threshold: 150 raw counts

**Note**: These tools require BLE hardware and should be run on the Raspberry Pi.