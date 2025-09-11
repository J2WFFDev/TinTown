# TinTown Timing Calibration Test Procedure

## ✅ **Pi Deployment Complete**
- `timing_calibration.py` deployed to Pi
- Updated `fixed_bridge.py` with timing integration deployed  
- `latest_timing_calibration.json` config deployed (526ms baseline)

## 🧪 **Test Procedure**

### **Step 1: Quick Validation Test**
Test that the bridge starts with timing calibration:

```bash
ssh raspberrypi 'cd ~/projects/TinTown && timeout 10 python3 scripts/fixed_bridge.py'
```

**Expected Output:**
```
✓ Successfully imported RealTimeTimingCalibrator
✓ Timing calibrator initialized with 526ms expected delay
=== TIMING CALIBRATION STATUS ===
Expected delay: 526ms
Correlation window: 1520ms
...
```

### **Step 2: Live Bridge Test**
Run the bridge and watch for timing correlation:

```bash
ssh raspberrypi 'cd ~/projects/TinTown && sudo python3 scripts/fixed_bridge.py'
```

**What to Watch For:**
1. **Bridge Initialization**:
   - Timing calibrator loads 526ms baseline
   - AMG timer connects (60:09:C3:1F:DC:1A)
   - BT50 sensor connects (F8:FE:92:31:12:E3)

2. **During Shooting** (fire test shots):
   - Shot events: `📝 String: Timer DC:1A - Shot #1 at 10:27:26.901`
   - Impact events: `📝 Impact Detected: Sensor 12:E3 Mag = 189 at 10:27:27.427`
   - Correlations: `✅ Correlated Shot #1 → Impact 189.0g (delay: 526ms, confidence: 0.95)`

3. **On Bridge Stop** (Ctrl+C):
   ```
   === TIMING CORRELATION STATISTICS ===
   Total correlated pairs: X
   Correlation success rate: XX.X%
   Average timing delay: XXXms
   Expected timing delay: 526ms
   =====================================
   ```

### **Step 3: Timing Analysis Test**
Analyze the logs created during testing:

```bash
ssh raspberrypi 'cd ~/projects/TinTown && ls -la logs/debug/bridge_debug_*.log logs/main/bridge_main_*.csv'
```

### **Step 4: Success Criteria**
- ✅ Bridge starts without errors
- ✅ Timing calibrator initializes with 526ms baseline
- ✅ Shot events logged with timestamps
- ✅ Impact events logged with timestamps  
- ✅ Correlation messages appear for shot-impact pairs
- ✅ Success rate ≥ 80% for test shots
- ✅ Average delay close to 526ms baseline

## 🚨 **Troubleshooting**

### **Import Errors:**
```bash
# Check Python path and module availability
ssh raspberrypi 'cd ~/projects/TinTown && python3 -c "import sys; print(sys.path); from src.impact_bridge.timing_calibration import RealTimeTimingCalibrator; print(\"Import successful\")"'
```

### **No Device Connections:**
- Ensure AMG timer is powered on
- Ensure BT50 sensor is powered on  
- Check Bluetooth status: `ssh raspberrypi 'sudo systemctl status bluetooth'`

### **No Correlations:**
- Verify shots are being detected in logs
- Verify impacts are being detected in logs
- Check timing window (1520ms should be sufficient)

## 📊 **Expected Timing Results**
Based on our analysis:
- **Baseline Timing**: 526ms delay shot → impact
- **Timing Range**: 99ms - 906ms (wide variation expected)
- **Correlation Window**: 1520ms captures 99.7% of variations
- **Success Rate**: Should achieve ≥80% with proper setup

## 🎯 **Test Commands Summary**

**Quick Test:**
```bash
ssh raspberrypi 'cd ~/projects/TinTown && timeout 10 python3 scripts/fixed_bridge.py'
```

**Live Test:**  
```bash
ssh raspberrypi 'cd ~/projects/TinTown && sudo python3 scripts/fixed_bridge.py'
```

**Check Logs:**
```bash
ssh raspberrypi 'cd ~/projects/TinTown && tail -20 logs/debug/bridge_debug_*.log'
```

---
**Status**: 🚀 **READY FOR LIVE TESTING ON PI**