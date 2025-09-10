#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from src.impact_bridge.event_logger import StructuredEventLogger

# Test device ID format
logger = StructuredEventLogger("logs", "logs/debug")
logger.timer_connected("DC:1A") 
logger.sensor_connected("12:E3")
logger.close()

print("✓ Device ID format test completed")
print("Check logs/main/bridge_main_*.csv for correct format")