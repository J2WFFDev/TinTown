# TinTown Timing Integration - Ready for Testing!

## ✅ **Integration Complete**

I have successfully integrated the timing calibration system into your existing `scripts/fixed_bridge.py`. Here's what was changed:

### **1. Added Timing Calibration Import**
```python
from impact_bridge.timing_calibration import RealTimeTimingCalibrator
```

### **2. Initialized Timing Calibrator in Bridge**
- Loads calibration from `latest_timing_calibration.json` (our discovered 526ms baseline)
- Falls back gracefully if timing modules aren't available
- Logs initialization status

### **3. Enhanced AMG Shot Detection**
**Before:**
```python
self.logger.info(f"📝 String: Timer DC:1A - Shot #{shot_number}")
```

**After:**
```python
timestamp = datetime.now()
self.logger.info(f"📝 String: Timer DC:1A - Shot #{shot_number} at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
# Add to timing calibrator for correlation
if self.timing_calibrator:
    self.timing_calibrator.add_shot_event(timestamp, shot_number, "DC:1A")
```

### **4. Enhanced BT50 Impact Detection**  
**Before:**
```python
self.logger.info(f"📝 Impact Detected: Sensor 12:E3 Mag = {magnitude_corrected:.0f}")
```

**After:**
```python
timestamp = datetime.now()
self.logger.info(f"📝 Impact Detected: Sensor 12:E3 Mag = {magnitude_corrected:.0f} at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
# Add to timing calibrator for correlation
if self.timing_calibrator:
    self.timing_calibrator.add_impact_event(timestamp, magnitude_corrected, "12:E3", vx_raw)
```

### **5. Added Timing Statistics Reporting**
On bridge shutdown, you'll now see:
```
=== TIMING CORRELATION STATISTICS ===
Total correlated pairs: X
Correlation success rate: XX.X%
Average timing delay: XXXms
Expected timing delay: 526ms
Calibration status: active/learning
=====================================
```

## 🧪 **Ready for Testing**

### **What You'll See During Testing:**

#### **Normal Operation:**
```
[10:27:26.901] INFO: 📝 String: Timer DC:1A - Shot #1 at 10:27:26.901
[10:27:27.427] INFO: 📝 Impact Detected: Sensor 12:E3 Mag = 189 at 10:27:27.427
[10:27:27.428] INFO: ✅ Correlated Shot #1 → Impact 189.0g (delay: 526ms, confidence: 0.95)
```

#### **Timing Learning:**
```
[10:27:30.100] INFO: 📊 Updated expected delay: 526ms → 531ms (based on 5 recent samples)
```

#### **Correlation Health:**
```
[10:27:35.200] INFO: ✅ Correlation health: 100% success, avg delay 528ms (expected 526ms)
```

### **Expected Timing Behavior:**
- **Shot Detection**: AMG timer frame type 0x03 (shot events)
- **Impact Detection**: BT50 magnitude > 150g threshold
- **Correlation Window**: 1520ms (captures 99.7% of timing variations)  
- **Expected Delay**: 526ms ± 663ms tolerance
- **Adaptive Learning**: System refines timing based on observed patterns

### **Files Modified/Created:**
- ✅ **Modified**: `scripts/fixed_bridge.py` (timing integration)
- ✅ **Created**: `src/impact_bridge/timing_calibration.py` (core system)
- ✅ **Created**: `src/impact_bridge/timing_integration.py` (integration example)
- ✅ **Created**: `tools/timing_analysis.ps1` (analysis tool) 
- ✅ **Created**: `latest_timing_calibration.json` (calibration config)
- ✅ **Created**: `doc/timing_calibration_report.md` (comprehensive documentation)

## 🚀 **How to Test**

### **1. Start the Enhanced Bridge**
```powershell
cd C:\sandbox\TargetSensor\TinTown
python scripts/fixed_bridge.py
```

### **2. Look for Initialization Messages**
```
✓ Successfully imported RealTimeTimingCalibrator
✓ Timing calibrator initialized with 526ms expected delay
=== TIMING CALIBRATION STATUS ===
Expected delay: 526ms
Correlation window: 1520ms
...
```

### **3. Fire Test Shots and Watch for:**
- Shot events with timestamps
- Impact events with timestamps  
- Correlation messages showing shot-impact pairs
- Timing statistics in logs

### **4. Check Results on Shutdown**
The bridge will display correlation statistics when you stop it (Ctrl+C).

## 🔍 **Validation Checklist**

**Before Testing:**
- [ ] Bridge starts without errors
- [ ] Timing calibrator initialization logged
- [ ] Calibration config loaded (526ms baseline)

**During Testing:**
- [ ] Shot events logged with timestamps
- [ ] Impact events logged with timestamps
- [ ] Correlation messages appear (✅ Correlated Shot #X → Impact Xg)
- [ ] No errors or exceptions in timing code

**After Testing:**
- [ ] Correlation statistics displayed on shutdown
- [ ] Success rate ≥ 80% for correlated shots
- [ ] Average delay close to 526ms baseline
- [ ] Updated calibration saved to JSON file

## ⚠️ **Troubleshooting**

### **If "Timing calibrator not available":**
- Check that `src/impact_bridge/timing_calibration.py` exists
- Verify Python path includes `src` directory  
- Review import error messages in console

### **If "No correlations found":**
- Verify both timer and sensor are connected
- Check that shots are being detected (📝 String messages)
- Check that impacts are being detected (📝 Impact messages)  
- Ensure timing window is appropriate (1520ms should capture most)

### **If correlation success rate is low (<50%):**
- Check for timing drift (average delay significantly different from 526ms)
- Verify impact threshold (150g) is appropriate
- Consider increasing correlation window temporarily

## 🎯 **Success Metrics**

- **Correlation Rate**: ≥80% of shots should correlate with impacts
- **Timing Accuracy**: Average delay should be 526ms ± 100ms
- **System Stability**: No performance impact on existing bridge functionality
- **Learning**: System should adapt to timing changes over multiple sessions

---

**Status**: ✅ **READY FOR LIVE TESTING**  
**Next Step**: Run `python scripts/fixed_bridge.py` and fire test shots!  
**Documentation**: See `doc/timing_calibration_report.md` for complete details