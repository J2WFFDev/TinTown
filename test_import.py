#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

try:
    from src.impact_bridge.event_logger import StructuredEventLogger, EventDetector
    print("✓ Event logger modules imported successfully")
    
    # Test basic functionality
    logger = StructuredEventLogger("logs", "logs/debug")
    logger.bridge_initialized()
    logger.close()
    print("✓ Basic logging test completed")
    
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()