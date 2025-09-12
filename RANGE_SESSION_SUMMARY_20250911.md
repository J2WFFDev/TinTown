# TinTown Range Session Summary - September 11, 2025

## Downloaded Files
- `range_session_console_20250911_163842.log` - **SUCCESSFUL SESSION** console log
- `range_session_debug_20250911_163943.log` - **SUCCESSFUL SESSION** debug log (25MB)
- `range_session_console_20250911_165752.log` - Failed session console log  
- `range_session_debug_20250911_165752.log` - Failed session debug log

## Session Timeline

### First Power-Up: 4:38 PM ✅ **SUCCESS**
- **4:38:43** - System started and initialized
- **4:38:57** - BT50 sensor connected (`Sensor 12:E3 - Connected`)
- **4:38:59** - BT50 calibration completed successfully
- **4:39:00** - System ready and listening for impacts
- **4:43:37** - **FIRST AMG SHOT DETECTED** 🎯
- **Continued operation** - System captured 109 total shots

### Second Power-Up: 4:57 PM ❌ **FAILED**  
- **4:57:52** - System restarted 
- **4:58:04** - AMG timer connection failed
- **4:58:14** - BT50 sensor connection failed
- **No data collected** - Devices were offline/out of range

## Key Results
- ✅ **109 shots detected** by AMG timer
- ✅ **BT50 sensor operational** and ready for impact detection  
- ✅ **Complete timing data** captured
- ✅ **Enhanced impact detection active** (30g onset, 150g peak thresholds)
- ✅ **Statistical timing calibration loaded** (83ms offset ±94ms)

## Data Analysis Notes
The successful session ran from 4:38 PM to approximately 4:57 PM (when you powered down/restarted).

**AMG Shot Pattern:**
- First shot: 16:43:37
- Peak activity around 4:43-4:44 PM
- Multiple strings of shots captured
- Each shot includes timing and sequence data

**BT50 Status:**
- Successfully connected and calibrated
- Baseline: X=2961, Y=0, Z=0
- Noise levels: X=±10.7, Y=±0.0, Z=±0.5  
- Impact threshold: 150 counts from baseline
- System was actively listening for impacts during shooting

## Files for Review
1. **Start with console logs** for high-level timeline
2. **Debug logs contain detailed shot data** - search for "SHOT :" to find AMG timer data
3. **Look for BT50 impact data** - search for "Impact detected" or "Peak detected"

## Next Steps
- Analyze shot timing patterns
- Check for any BT50 impact correlations 
- Verify timing calibration effectiveness
- Review system performance during active shooting