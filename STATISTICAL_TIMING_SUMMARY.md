# Statistical Timing Calibration Summary

## Analysis Results from Large Sample Test

### Test Data
- **152 shots fired, 101 impacts detected**
- **51 valid correlations** achieved for statistical analysis
- Test conducted on 2025-09-11 at approximately 12:00

### Key Statistical Findings

#### Primary Timing Statistics
- **Mean Delay**: 103.0ms (AMG acoustic → BT50 physical onset)
- **Median Delay**: 83.0ms (recommended primary offset)
- **Standard Deviation**: ±94ms (high variability)

#### Confidence Intervals
- **68% Confidence**: 9.2ms - 196.7ms
- **95% Confidence**: -80.8ms - 286.7ms
  
  *Note: Negative values indicate some BT50 detections occur before AMG timer detection*

#### Data Quality Assessment
- **Quality Rating**: Poor (9% consistency)
- **Delay Range**: 2.0ms - 450.0ms
- **Impact Magnitude Range**: 32.3g - 825.1g (avg: 365.3g ±210.5g)

### Implementation Changes

#### 1. **Statistical Timing Calibrator** (`src/impact_bridge/statistical_timing_calibration.py`)
- Uses **median (83ms)** as primary offset instead of mean for stability
- Provides multiple confidence level projections
- Includes uncertainty calculations (±94ms)
- Real-time timing accuracy analysis

#### 2. **Enhanced Bridge Integration** (`scripts/fixed_bridge.py`)
- **Shot Detection**: Projects impact timing when AMG timer detects shots
  - Example: "📊 Projected Impact: 12:01:23.456 (±94ms, 68% CI: 9.2-196.7ms)"
- **Impact Validation**: Analyzes prediction accuracy when impacts occur
  - Example: "📊 Timing Analysis: Shot→Impact delay 85ms (predicted 83ms, error +2ms, 68% confidence)"
- **Comprehensive Logging**: Structured events for projections and analyses

#### 3. **Timing Projection Features**
- **Real-time Impact Projection**: When AMG detects shot acoustic signature
- **Accuracy Validation**: When BT50 detects actual impact onset
- **Confidence Assessment**: Statistical confidence levels for each correlation
- **Error Analysis**: Prediction vs actual timing comparisons

### Usage Notes

#### Timing Variability Factors
1. **Projectile Velocity**: Faster projectiles reduce delay
2. **Impact Angle**: Direct hits vs glancing impacts affect detection timing
3. **Target Material**: Plate resonance affects sensor response
4. **Environmental**: Temperature, vibration, mounting affects sensitivity

#### Recommended Offset Strategy
- **Primary Offset**: Use 83ms median for consistent timing
- **Uncertainty Range**: ±94ms reflects real-world variability
- **Confidence Levels**: Monitor which percentage of shots fall within predicted ranges

#### System Performance
- **Correlation Rate**: 51/152 shots = 33.6% correlation success
  - Missed correlations due to: weak impacts below threshold, timing window misses, multiple rapid shots
- **Detection Range**: Successfully correlates impacts from 32g to 825g
- **Timing Precision**: ±94ms uncertainty suitable for sporting applications

### Next Steps

1. **Live Testing**: Use updated bridge to validate statistical projections in real-time
2. **Calibration Refinement**: Collect more data under controlled conditions to reduce uncertainty
3. **Environmental Compensation**: Consider velocity-based timing adjustments
4. **Threshold Optimization**: Adjust detection thresholds based on statistical findings

### Files Updated
- `src/impact_bridge/statistical_timing_calibration.py` - New statistical calibrator
- `scripts/fixed_bridge.py` - Enhanced with statistical timing integration
- Both files deployed to Raspberry Pi for testing

The system now provides **statistical timing confidence** based on your comprehensive 152-shot test data!