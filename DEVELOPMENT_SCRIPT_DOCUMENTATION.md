# 🎯 **TinTown Development Script - Complete Process Documentation**

## 📋 **Key Development Command**

```bash
ssh raspberrypi 'cd ~/projects/TinTown && timeout 30 sudo python3 scripts/fixed_bridge.py'
```

## 🔧 **Complete Process Breakdown**

### **1. SSH Connection & Environment Setup**
- **SSH to Raspberry Pi**: Connects to the Pi running the TinTown hardware
- **Directory Change**: Changes to `/home/jrwest/projects/TinTown` working directory
- **Timeout Protection**: 30-second automatic termination to prevent hanging sessions
- **Elevated Privileges**: `sudo` required for Bluetooth Low Energy (BLE) access

---

## 🚀 **Bridge Initialization Sequence**

### **Phase 1: Module Imports & Validation**
```
✓ Successfully imported corrected parse_5561 with 1mg scale factor
✓ Successfully imported ShotDetector  
✓ Successfully imported RealTimeTimingCalibrator
✓ Successfully imported EnhancedImpactDetector
✓ Successfully imported development configuration
```

**What This Does:**
- **WitMotion Parser**: Loads BT50 sensor data parsing (5561 protocol)
- **Shot Detection**: Imports AMG timer shot detection logic
- **Timing Calibration**: Loads enhanced timing correlation system
- **Enhanced Impact Detection**: Imports onset-based impact detection
- **Development Config**: Loads development vs production configuration

### **Phase 2: Development Configuration Loading**
```
🔧 TINTOWN DEVELOPMENT CONFIGURATION
============================================================
Mode: 🔧 Development Mode (Enhanced logging and analysis enabled)
Enhanced Logging: ✅
Sample Logging: ✅  
Impact Analysis: ✅
Timing Correlation: ✅
Analysis Tools: ✅
Enhanced Impact Detection: ✅
Performance Monitoring: ✅
  Onset Threshold: 30.0g
  Peak Threshold: 150.0g
  Lookback Samples: 10
============================================================
```

**Configuration Applied:**
- **Development Mode**: Enables enhanced logging and analysis features
- **Sample Logging**: Every BT50 sample logged with timestamps for strip chart analysis
- **Onset Threshold**: 30g for impact onset detection (vs 150g for peak)
- **Enhanced Analysis**: Detailed timing correlation and impact progression tracking

### **Phase 3: System Components Initialization**
```
✓ Timing calibrator initialized with 526ms expected delay
✓ Using development config for enhanced impact detection
✓ Enhanced impact detector initialized (onset detection enabled)
```

**Components Activated:**
- **Timing Calibrator**: Loads with 526ms baseline delay from previous analysis
- **Enhanced Impact Detector**: Configured with development thresholds (30g onset, 150g peak)
- **Adaptive Learning**: System ready to refine timing correlation based on new data

---

## 📡 **Hardware Connection & Calibration**

### **Phase 4: Bluetooth System Reset**
```
[09:55:05.209] INFO: 🔄 Starting BLE reset
[09:55:09.915] INFO: 🔧 Reset Bluetooth adapter  
[09:55:10.918] INFO: ✓ BLE reset complete
```

**BLE Reset Process:**
- **Bluetooth Adapter Reset**: Clears any stuck connections
- **Clean State**: Ensures reliable BLE communication
- **Hardware Preparation**: Prepares for device connections

### **Phase 5: Device Connections**

#### **AMG Timer Connection:**
```
[09:55:10.922] INFO: Connecting to AMG timer...
[09:55:12.309] INFO: 📝 Status: Timer DC:1A - Connected
[09:55:12.434] INFO: AMG timer and shot notifications enabled
```

**AMG Timer Setup:**
- **Device ID**: 60:09:C3:1F:DC:1A (AMG Commander Timer)
- **Protocol**: AMG 14-byte frame structure
- **Shot Detection**: Ready to receive shot event notifications
- **String Management**: Handles multi-shot strings with individual shot timing

#### **BT50 Sensor Connection:**
```
[09:55:14.103] INFO: 📝 Status: Sensor 12:E3 - Connected
[09:55:15.107] INFO: 🎯 Starting automatic calibration...
```

**BT50 Sensor Setup:**
- **Device ID**: F8:FE:92:31:12:E3 (WitMotion BT50 IMU Sensor)
- **Protocol**: WitMotion 5561 data format
- **Sample Rate**: ~20Hz continuous sampling
- **Data Stream**: X,Y,Z accelerometer values + calculated magnitudes

### **Phase 6: Sensor Calibration Process**
```
🎯 Performing startup calibration...
📋 Please ensure sensor is STATIONARY during calibration
⏱️  Collecting 100+ samples for baseline establishment...
📊 Collected 100/100 samples...

[09:55:16.233] INFO: Calibration complete: X=2010, Y=0, Z=0
[09:55:16.235] INFO: ✅ Calibration completed successfully!
[09:55:16.236] INFO: 📊 Baseline established: X=2010, Y=0, Z=0
[09:55:16.236] INFO: 📈 Noise levels: X=±12.1, Y=±0.0, Z=±0.0
[09:55:16.236] INFO: 🎯 Impact threshold: 150 counts from baseline
```

**Calibration Details:**
- **Baseline Establishment**: Determines sensor rest position (X=2010, Y=0, Z=0)
- **Noise Analysis**: Measures sensor noise levels (±12.1g X-axis typical)
- **Threshold Calculation**: Sets 150-count impact detection threshold above baseline
- **100 Sample Average**: Uses statistical analysis for accurate baseline

---

## 🎯 **Operational Readiness**

### **Phase 7: System Ready State**
```
[09:55:16.306] INFO: 📝 Status: Sensor 12:E3 - Listening
[09:55:16.306] INFO: BT50 sensor and impact notifications enabled  
[09:55:16.307] INFO: 🎯 Bridge ready for String
```

**Ready State Capabilities:**
- **Shot Detection**: AMG timer monitoring for shot events
- **Impact Detection**: BT50 sensor monitoring with enhanced onset detection
- **Timing Correlation**: Real-time shot-impact correlation with adaptive learning
- **Development Logging**: Enhanced sample data logging for analysis

---

## 📊 **Live Operation & Enhanced Logging**

### **During Shot Testing:**

#### **Shot Event Processing:**
```
[09:55:21.017] INFO: 📝 String: Timer DC:1A - Shot #1 at 09:55:21.017
[09:55:21.021] INFO: Shot #1 recorded at 09:55:21.017
```

**Shot Detection Process:**
- **AMG Protocol Parsing**: Decodes 14-byte AMG timer frames
- **Shot Identification**: Extracts shot number and precise timestamp
- **Timing Calibrator**: Records shot event for correlation analysis

#### **Enhanced Impact Detection:**
```
[09:55:21.592] INFO: 🎯 Complete Impact Event:
[09:55:21.593] INFO:   Onset: 09:55:21.429 (43.7g)
[09:55:21.594] INFO:   Peak:  09:55:21.461 (248.2g)  
[09:55:21.594] INFO:   Onset→Peak: 32.4ms
[09:55:21.594] INFO:   Duration: 163.2ms, Samples: 5, Confidence: 0.95
```

**Enhanced Impact Analysis:**
- **Onset Detection**: First sample crossing 30g threshold (43.7g at 09:55:21.429)
- **Peak Detection**: Maximum magnitude sample (248.2g at 09:55:21.461)
- **Timing Progression**: 32.4ms from onset to peak (proper chronology)
- **Quality Assessment**: 0.95 confidence score (excellent detection)

#### **Timing Correlation:**
```
[09:55:21.599] INFO: ✅ Correlated Shot #1 → Impact 248.2g (delay: 411ms, confidence: 0.91)
```

**Correlation Process:**
- **Onset-Based Timing**: Uses impact onset timestamp (not peak)
- **Shot-Impact Delay**: 411ms from shot to impact onset
- **High Confidence**: 0.91 correlation confidence
- **Adaptive Learning**: Updates expected delay based on successful correlations

### **Development Mode Sample Logging:**
```
DEBUG: BT50 sample: 09:55:21.429 vx_raw=1995, vy_raw=41, vz_raw=0, magnitude=43.7
DEBUG: BT50 sample: 09:55:21.461 vx_raw=2001, vy_raw=248, vz_raw=0, magnitude=248.2
```

**Enhanced Logging Features:**
- **Every Sample Logged**: Timestamp + raw X,Y,Z values + calculated magnitude
- **Strip Chart Data**: Enables detailed 40+ sample analysis around impacts
- **Development Analysis**: Supports waveform analysis and timing validation

---

## 📈 **Data Collection & Analysis Outputs**

### **Log Files Generated:**

#### **Main Event Log:**
- **File**: `logs/main/bridge_main_20250911.ndjson`
- **Content**: JSON-structured event log (shots, impacts, correlations)
- **Usage**: Dashboard analysis, session reports

#### **Debug Sample Log:**
- **File**: `logs/debug/bridge_debug_20250911_095505.log`  
- **Content**: Detailed sample data, timing analysis, system debugging
- **Usage**: Strip chart analysis, waveform analysis

#### **Timing Calibration Data:**
- **File**: `latest_timing_calibration.json`
- **Content**: Adaptive timing correlation parameters
- **Usage**: Baseline timing, correlation learning

### **Analysis Capabilities After Test:**

#### **Strip Chart Analysis:**
```bash
python3 extract_impact_samples.py logs/debug/bridge_debug_20250911_095505.log 09:55:21.429
```
- **40+ Sample Chart**: Detailed impact progression with X,Y,Z values
- **Timing Analysis**: Onset detection validation
- **Waveform Analysis**: Rise time, fall time, impact energy

#### **Session Dashboard:**
```bash  
python3 timing_analysis_dashboard.py
```
- **Correlation Statistics**: Success rates, timing consistency
- **Impact Analysis**: Magnitude statistics, confidence trends
- **System Performance**: Processing rates, session metrics

---

## 🎯 **Key Development Insights**

### **What This 30-Second Test Accomplishes:**

1. **✅ System Validation**: Confirms all hardware connections and software components
2. **✅ Timing Baseline**: Establishes/validates current timing correlation (~411ms)
3. **✅ Impact Detection**: Tests enhanced onset detection vs peak detection
4. **✅ Data Collection**: Generates detailed logs for strip chart and session analysis
5. **✅ Configuration Validation**: Confirms development mode settings are active
6. **✅ Quality Assessment**: Provides confidence scores for detection accuracy

### **Critical Development Data Generated:**

- **Precise Timing**: Shot-impact correlation with millisecond accuracy
- **Impact Progression**: Complete waveform from onset through peak to baseline
- **Detection Quality**: Confidence scoring for detection reliability
- **System Performance**: Processing rates and stability metrics
- **Baseline Calibration**: Sensor noise levels and threshold validation

### **Immediate Analysis Available:**
- **Strip Charts**: Detailed sample-level impact analysis
- **Correlation Reports**: Multi-shot timing consistency analysis  
- **Waveform Analysis**: Impact characteristics and energy assessment
- **Data Export**: CSV/JSON formats for custom analysis

---

## 🚀 **Summary: Development Script Process**

**The `timeout 30 sudo python3 scripts/fixed_bridge.py` command is your complete TinTown development testing script that:**

🔧 **Initializes**: All enhanced development components with proper configuration  
📡 **Connects**: AMG timer and BT50 sensor with full protocol support  
🎯 **Calibrates**: Sensor baseline and impact detection thresholds  
📊 **Monitors**: Real-time shot-impact correlation with enhanced timing  
📈 **Logs**: Detailed sample data for comprehensive post-test analysis  
✅ **Validates**: System performance and detection accuracy  

**In just 30 seconds, you get a complete system validation with detailed timing analysis data ready for strip chart analysis and correlation refinement! 🎯**