#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('./src'))

try:
    from impact_bridge.event_logger import StructuredEventLogger, EventDetector
    from impact_bridge.ble.wtvb_parse import parse_5561
    from impact_bridge.ble.amg_parse import parse_amg_timer_data
    print("✓ All modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Now run the actual bridge
if __name__ == "__main__":
    import subprocess
    import sys
    
    # Run the dev_bridge with proper environment
    cmd = [sys.executable, "scripts/dev_bridge.py", "--decode", "--units", "g"]
    subprocess.run(cmd)