# TinTown Enhanced Development Tools

## 🎯 **Overview**

The TinTown Bridge system includes enhanced development tools for timing calibration analysis, impact detection refinement, and system performance monitoring. These tools are designed to be used during the development phase to refine timing correlation logic and validate system performance.

## 🔧 **Development Configuration System**

### **Configuration Files**
- **`config/development.yaml`** - Main development configuration
- **`src/impact_bridge/dev_config.py`** - Configuration manager

### **Key Features**
- **Development vs Production modes** - Toggle enhanced features
- **Configurable logging levels** - Control debug verbosity
- **Enhanced impact detection settings** - Tune thresholds and parameters
- **Analysis tools control** - Enable/disable analysis features

### **Configuration Options**

```yaml
# Enable development mode with enhanced features
development_mode: true

# Enhanced logging configuration
enhanced_logging:
  enabled: true
  sample_logging: true          # Log every BT50 sample
  impact_analysis: true         # Detailed impact analysis
  timing_correlation: true      # Enhanced correlation logging

# Enhanced impact detection settings  
enhanced_impact:
  onset_threshold: 30.0         # Onset detection threshold (g)
  peak_threshold: 150.0         # Peak detection threshold (g)
  lookback_samples: 10          # Sample history for onset detection

# Analysis tools
analysis_tools:
  enabled: true
  strip_chart_generator: true   # Generate detailed strip charts
  correlation_analyzer: true    # Multi-shot correlation analysis
```

### **Usage in Bridge**
The development configuration is automatically loaded and applied:

```python
# Development configuration is integrated into fixed_bridge.py
if DEV_CONFIG_AVAILABLE and dev_config:
    dev_config.print_config_summary()
    # Thresholds configured from development.yaml
    peak_threshold = dev_config.get_peak_threshold()
    onset_threshold = dev_config.get_onset_threshold()
```

## 📊 **Enhanced Sample Extraction Tool**

### **File**: `extract_impact_samples.py`

### **Purpose**
Extract and analyze detailed sample data around impact events for timing validation and waveform analysis.

### **Basic Usage**
```bash
# Extract sample data for specific impact
python3 extract_impact_samples.py logs/debug/bridge_debug_20250911_095505.log 09:55:21.429

# With enhanced analysis options
python3 extract_impact_samples.py logs/debug/bridge_debug_20250911_095505.log 09:55:21.429 --waveform-analysis --export-csv
```

### **Command Line Options**
- `--export-csv` - Export data to CSV format for Excel/analysis
- `--export-json` - Export data to JSON format for programmatic use
- `--waveform-analysis` - Perform detailed waveform characteristic analysis
- `--multi-shot` - Analyze multiple shot correlations in session

### **Output Features**

#### **Strip Chart Display**
```
🎯 IMPACT EVENT STRIP CHART
========================================================================================================================
#   Time         Offset   X_Raw  Y_Raw  Z_Raw  Magnitude Notes
------------------------------------------------------------------------------------------------------------------------
20 09:55:21.380  -49.0ms  2014     0     0     4.0g
21 09:55:21.429   +0.0ms  1995    41     0    43.7g ← IMPACT DETECTED
22 09:55:21.461  +32.0ms  2001   248     0   248.2g ← PEAK MAGNITUDE
23 09:55:21.523  +94.0ms  2020   188     0   188.3g ← ABOVE PEAK THRESHOLD
```

#### **Waveform Analysis**
- **Rise Time**: Onset to peak duration
- **Fall Time**: Peak to baseline duration  
- **Peak/Onset Ratio**: Impact intensity measurement
- **Impact Energy**: Simplified area under curve

#### **Data Export**
- **CSV Format**: Compatible with Excel, MATLAB, Python pandas
- **JSON Format**: Structured data for custom analysis scripts

### **Development Integration**
The tool automatically detects the enhanced logging format and extracts:
- **Raw X,Y,Z values** from BT50 sensor
- **Precise timestamps** for timing analysis
- **Magnitude calculations** for impact detection validation

## 🎯 **Timing Analysis Dashboard**

### **File**: `timing_analysis_dashboard.py`

### **Purpose**
Automated analysis and reporting for complete testing sessions, providing comprehensive timing correlation and system performance metrics.

### **Usage**
```bash
# Analyze today's session
python3 timing_analysis_dashboard.py

# Analyze specific date
python3 timing_analysis_dashboard.py 20250911
```

### **Analysis Features**

#### **Timing Correlation Analysis**
- Shot-impact correlation rates
- Average timing delays
- Delay consistency (standard deviation)
- Correlation confidence trends

#### **Impact Characteristics Analysis**  
- Onset magnitude statistics
- Peak magnitude statistics
- Confidence score analysis
- Detection reliability metrics

#### **System Performance Analysis**
- Session duration tracking
- Event processing rates
- System stability metrics
- Error rate analysis

### **Report Output**
```
📋 SESSION ANALYSIS SUMMARY
========================================================================================================================
📅 Session Date: 20250911
⏱️  Duration: 5.2 minutes  
📊 Total Events: 156

🎯 TIMING CORRELATION:
   Shots: 8
   Impacts: 8  
   Correlation Rate: 100.0%
   Average Delay: 411.2ms ± 45.3ms

📈 IMPACT ANALYSIS:
   Total Impacts: 8
   Onset Magnitude: 87.3g (avg)
   Peak Magnitude: 223.1g (avg)
   Confidence Score: 0.87 (avg)

🏆 SYSTEM ASSESSMENT:
   ✅ Excellent correlation rate (100.0%)
   ✅ High impact detection confidence (0.87)
```

## 🎯 **Enhanced Impact Detection System**

### **File**: `src/impact_bridge/enhanced_impact_detection.py`

### **Key Improvements**
1. **Onset-First Detection** - Detects impact start, not just peak
2. **Proper Chronology** - Ensures onset occurs before peak
3. **Detailed Logging** - Complete impact progression tracking
4. **Confidence Scoring** - Quality assessment for each detection

### **Detection Process**
```python
# 1. Continuous monitoring for onset (30g threshold)
if magnitude >= onset_threshold:
    start_impact_detection(sample)

# 2. Track samples through peak to baseline return
while in_impact:
    record_sample(sample)
    if magnitude < onset_threshold:
        end_impact_detection()

# 3. Analyze complete impact sequence
impact_event = create_impact_event(
    onset_sample,     # First sample in sequence
    peak_sample,      # Highest magnitude sample
    duration,         # Total impact duration
    confidence        # Detection quality score
)
```

### **Timing Correlation Integration**
```python
# Use ONSET timestamp for shot correlation (key improvement!)
self.timing_calibrator.add_impact_event(
    timestamp=impact_event.onset_timestamp,  # Not peak timestamp!
    magnitude=impact_event.peak_magnitude,
    device_id="12:E3"
)
```

## 📈 **Usage Workflows**

### **Development Phase Testing**

1. **Configure Development Mode**
   ```bash
   # Edit config/development.yaml
   development_mode: true
   enhanced_logging:
     sample_logging: true
   ```

2. **Run Bridge with Enhanced Logging**
   ```bash
   ssh raspberrypi 'cd ~/projects/TinTown && sudo python3 scripts/fixed_bridge.py'
   ```

3. **Perform Test Shots**
   - Fire test shots during bridge operation
   - Enhanced system logs detailed timing correlation

4. **Analyze Results**
   ```bash
   # Extract detailed sample data
   python3 extract_impact_samples.py logs/debug/bridge_debug_20250911_095505.log 09:55:21.429 --waveform-analysis
   
   # Generate session report
   python3 timing_analysis_dashboard.py
   ```

### **Timing Calibration Refinement**

1. **Collect Baseline Data**
   - Run multiple test sessions with various shot patterns
   - Use dashboard to analyze correlation consistency

2. **Adjust Thresholds**
   - Modify `onset_threshold` in development.yaml
   - Test impact detection sensitivity

3. **Validate Changes**
   - Compare before/after correlation statistics  
   - Use strip charts to verify onset detection accuracy

4. **Production Deployment**
   ```yaml
   # Switch to production mode
   development_mode: false
   ```

## 🔧 **Maintenance and Updates**

### **Adding New Analysis Features**
1. **Update `dev_config.py`** - Add configuration options
2. **Modify bridge code** - Integrate new features with config checks
3. **Extend analysis tools** - Add new analysis functions
4. **Update documentation** - Document new capabilities

### **Log Format Changes**
- **Sample logging format** is controlled by bridge development configuration
- **Analysis tools** automatically detect format changes
- **Backward compatibility** maintained through format detection

### **Performance Considerations**
- **Development mode** enables verbose logging (impacts performance)
- **Production mode** disables analysis overhead
- **Configurable features** allow selective enablement

## 📊 **Troubleshooting**

### **Common Issues**

#### **"No sample data found"**
- Ensure enhanced logging is enabled in development.yaml
- Check that debug log contains "BT50 sample:" entries
- Verify correct timestamp format in extraction command

#### **"Development configuration not available"**
- Check that `config/development.yaml` exists
- Verify `src/impact_bridge/dev_config.py` is accessible
- Review bridge startup messages for import errors

#### **Poor correlation rates**
- Adjust onset_threshold in development configuration
- Review strip charts for timing accuracy
- Check for system timing drift in dashboard analysis

### **Debug Commands**
```bash
# Test development configuration
python3 src/impact_bridge/dev_config.py

# Validate log file format
grep "BT50 sample:" logs/debug/bridge_debug_*.log | head -5

# Check bridge initialization
grep -E "(Enhanced|Development)" logs/main/bridge_main_*.ndjson
```

## 🎯 **Future Enhancements**

### **Planned Features**
- **Real-time analysis dashboard** - Live monitoring during tests
- **Machine learning integration** - Adaptive threshold adjustment
- **Multi-sensor correlation** - Analysis across multiple BT50 sensors
- **Automated report generation** - Scheduled analysis reports

### **Development Roadmap**
1. **Phase 1**: Enhanced logging and analysis (✅ Complete)
2. **Phase 2**: Real-time monitoring capabilities
3. **Phase 3**: Advanced correlation algorithms
4. **Phase 4**: Production optimization and deployment

---

## 📚 **Quick Reference**

### **Essential Files**
- **`config/development.yaml`** - Development configuration
- **`scripts/fixed_bridge.py`** - Main bridge with enhanced features  
- **`extract_impact_samples.py`** - Sample extraction and analysis
- **`timing_analysis_dashboard.py`** - Session analysis and reporting

### **Key Commands**
```bash
# Start enhanced bridge
sudo python3 scripts/fixed_bridge.py

# Analyze impact samples  
python3 extract_impact_samples.py <log_file> <impact_time> --waveform-analysis

# Generate session report
python3 timing_analysis_dashboard.py

# Test configuration
python3 src/impact_bridge/dev_config.py
```

### **Configuration Quick Settings**
```yaml
# Maximum development features
development_mode: true
enhanced_logging: {enabled: true, sample_logging: true}
analysis_tools: {enabled: true}

# Production mode  
development_mode: false
# (Automatic production overrides applied)
```

**Your enhanced TinTown development toolkit is ready for comprehensive timing calibration analysis and system refinement! 🎯**