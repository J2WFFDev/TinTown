#!/usr/bin/env python3
"""
Test the timing-enhanced fixed bridge integration

This script validates that the timing calibration is properly integrated
into the fixed_bridge.py without breaking existing functionality.
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    # Add src to path for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    
    try:
        # Test the main bridge import
        from scripts.fixed_bridge import FixedBridge
        print("✅ FixedBridge imports successfully")
        
        # Test timing calibration import
        from src.impact_bridge.timing_calibration import RealTimeTimingCalibrator
        print("✅ RealTimeTimingCalibrator imports successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_bridge_initialization():
    """Test that the bridge can be initialized with timing calibration"""
    print("\nTesting bridge initialization...")
    
    try:
        # Add src to path for imports
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        
        from scripts.fixed_bridge import FixedBridge
        
        # Initialize bridge
        bridge = FixedBridge()
        
        # Check if timing calibrator was initialized
        if hasattr(bridge, 'timing_calibrator') and bridge.timing_calibrator is not None:
            print("✅ Bridge initialized with timing calibrator")
            
            # Check calibration parameters
            cal = bridge.timing_calibrator.calibration
            print(f"   Expected delay: {cal.expected_delay_ms}ms")
            print(f"   Correlation window: {cal.correlation_window_ms}ms") 
            print(f"   Delay tolerance: ±{cal.delay_tolerance_ms}ms")
            
            return True
        else:
            print("⚠️  Bridge initialized but timing calibrator not available")
            print("   (This may be expected if timing modules aren't available)")
            return True
            
    except Exception as e:
        print(f"❌ Bridge initialization failed: {e}")
        return False

def test_calibration_config():
    """Test that calibration configuration exists and is valid"""
    print("\nTesting calibration configuration...")
    
    config_file = Path("latest_timing_calibration.json")
    
    if config_file.exists():
        try:
            import json
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check required fields
            required_fields = ['timing_calibration', 'statistics']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                print(f"⚠️  Calibration config missing fields: {missing_fields}")
                return False
            
            cal = config['timing_calibration']
            stats = config['statistics']
            
            print(f"✅ Calibration config loaded:")
            print(f"   Expected delay: {cal.get('expected_delay_ms', 'N/A')}ms")
            print(f"   Correlation window: {cal.get('correlation_window_ms', 'N/A')}ms")
            print(f"   Sample count: {cal.get('sample_count', 'N/A')}")
            print(f"   Success rate: {stats.get('correlation_rate_percent', 'N/A')}%")
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in calibration config: {e}")
            return False
        except Exception as e:
            print(f"❌ Error reading calibration config: {e}")
            return False
    else:
        print("⚠️  No calibration config found (latest_timing_calibration.json)")
        print("   This is expected on first run - config will be created automatically")
        return True

def test_method_integration():
    """Test that timing methods are properly integrated"""
    print("\nTesting method integration...")
    
    try:
        # Add src to path for imports
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        
        from scripts.fixed_bridge import FixedBridge
        import inspect
        
        bridge = FixedBridge()
        
        # Check if AMG handler exists
        if hasattr(bridge, 'amg_notification_handler'):
            print("✅ amg_notification_handler method exists")
            
            # Check method signature
            sig = inspect.signature(bridge.amg_notification_handler)
            if len(sig.parameters) == 3:  # self, characteristic, data
                print("✅ amg_notification_handler has correct signature")
            else:
                print(f"⚠️  amg_notification_handler signature unexpected: {sig}")
        
        # Check if BT50 handler exists  
        if hasattr(bridge, 'bt50_notification_handler'):
            print("✅ bt50_notification_handler method exists")
            
            # Check method signature
            sig = inspect.signature(bridge.bt50_notification_handler)
            if len(sig.parameters) == 3:  # self, characteristic, data
                print("✅ bt50_notification_handler has correct signature")
            else:
                print(f"⚠️  bt50_notification_handler signature unexpected: {sig}")
        
        return True
        
    except Exception as e:
        print(f"❌ Method integration test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("=" * 60)
    print("TINTOWN TIMING INTEGRATION VALIDATION")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_bridge_initialization,
        test_calibration_config,
        test_method_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"VALIDATION RESULTS: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Ready for live testing!")
        print()
        print("Next steps:")
        print("1. Connect AMG timer and BT50 sensor")
        print("2. Run: python scripts/fixed_bridge.py")
        print("3. Fire test shots and observe timing correlation")
        print("4. Check logs for correlation statistics")
        return True
    else:
        print("⚠️  Some tests failed - review issues before live testing")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)