# TinTown Impact Bridge

*Continue of Target Sensor logging*

Raspberry Pi 4B BLE bridge for steel-plate impact detection using AMG Commander timer and WitMotion BT50 vibration sensors.

## Development Environment

**⚠️ IMPORTANT**: Primary development should be done **on the Raspberry Pi** where the BLE sensors are connected.  
**Local Windows**: Use as a replica for code viewing/editing only.

### Repository Structure
- **Production**: Code runs on Raspberry Pi with actual BLE hardware
- **Replica**: Local development environment for code editing (this instance)
- **Excluded**: Large documentation folders and logs are not synced to git

## Project Status - September 10, 2025

✅ **Raw Count Calibration System** - Successfully implemented and validated  
✅ **AMG Protocol Decoded** - Complete 14-byte frame structure with shot detection  
✅ **Dual Device Connection** - Both AMG timer and BT50 sensor working simultaneously  
✅ **Impact Detection Validated** - 150-count threshold with stable baseline tracking  

**Key Achievement**: Implemented robust calibration-based impact detection using raw sensor counts, eliminating scale factor complexities and achieving stable baseline tracking.
