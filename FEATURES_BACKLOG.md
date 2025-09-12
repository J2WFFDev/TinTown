# TinTown Bridge - Features Backlog List

*Prioritized list of features and enhancements for the TinTown Bridge system*

---

## 🔋 **Priority 1: BT50 Battery % Monitoring**

### **Feature Description**
Implement battery percentage monitoring for the WitMotion BT50 sensor to provide real-time battery status and low battery warnings.

### **Technical Requirements**
- **Protocol Integration**: Parse battery data from WitMotion 5561 protocol
- **Data Source**: BT50 sensor battery status via BLE characteristic
- **Display Format**: Show battery percentage in bridge console logs
- **Alerting**: Warn when battery drops below configurable threshold (default: 20%)
- **Logging**: Include battery status in impact event logs

### **Implementation Details**
```python
# Expected battery data parsing
battery_percentage = parse_battery_from_bt50_data(sensor_data)
```

### **Acceptance Criteria**
- [ ] Battery percentage displayed in real-time during bridge operation
- [ ] Low battery warnings logged when threshold reached
- [ ] Battery status included in impact event metadata
- [ ] Configurable battery warning threshold in YAML config
- [ ] Battery data persisted to logs for historical tracking

### **Estimated Effort**: Medium (2-3 hours)
### **Dependencies**: WitMotion protocol documentation for battery characteristic
### **Priority**: High - Critical for field operations

---

## 🔧 **Priority 2: Hardware & System Updates**

### **Update Sensors to New Model**
- **Description**: Upgrade from current WitMotion BT50 to newer sensor models
- **Benefits**: Improved accuracy, better battery life, enhanced features
- **Status**: 🔴 Not Started - Research phase needed
- **Effort**: Large (1-2 weeks) - Protocol changes required

### **Update MCU to Non-Pi Platform**
- **Description**: Migrate from Raspberry Pi to dedicated MCU (ESP32, STM32, etc.)
- **Benefits**: Lower power, faster boot, reduced cost, embedded reliability
- **Status**: 🔴 Not Started - Architecture redesign needed
- **Effort**: Large (3-4 weeks) - Complete system port required

### **Time Sync of Sensors to MCU Master**
- **Description**: Implement master clock synchronization on bridge startup
- **Benefits**: Eliminate timing drift between sensors, improved correlation accuracy
- **Status**: 🔴 Not Started - Protocol design needed
- **Effort**: Medium (1-2 weeks) - BLE timing protocol required

---

## 🔄 **Priority 3: Connectivity & Reliability**

### **Test BLE Reconnection & Bridge Reset**
- **Description**: Automatic BLE reconnection handling and bridge restart capabilities
- **Benefits**: Improved system reliability, reduced manual intervention
- **Status**: 🔴 Not Started - Testing framework needed
- **Effort**: Medium (1 week) - Connection management logic

### **Add Sensor Detection and Selection**
- **Description**: Automatic sensor discovery and manual sensor assignment interface
- **Benefits**: Easy sensor management, multi-sensor support, flexible configuration
- **Status**: 🔴 Not Started - UI design needed
- **Effort**: Medium (1-2 weeks) - BLE scanning + UI components

### **Resolve WiFi Connection Advertisement**
- **Description**: Define how bridge advertises network connectivity and internet access
- **Benefits**: Clear network status, remote monitoring capabilities
- **Status**: 🔴 Not Started - Network architecture decisions needed
- **Effort**: Small (3-5 days) - Network status reporting

### **Offline Mode Operations**
- **Description**: Complete offline functionality with time/date management and data upload
- **Features**: Manual time/date setting, local data storage, batch upload when connected, offline competition mode
- **Benefits**: Field operations without internet, reliable data capture, sync when connectivity restored
- **Status**: 🔴 Not Started - Offline architecture design needed
- **Effort**: Large (2-3 weeks) - Complete offline workflow + sync system

---

## 🌐 **Priority 4: Web Administration Portal**

### **Web Portal for Admin Sensor Setup**
- **Description**: Web interface for configuring sensors to plates for competition stages
- **Features**: Sensor assignment, plate mapping, calibration interface, system settings
- **Status**: 🔴 Not Started - Full web stack needed
- **Effort**: Large (2-3 weeks) - Web framework + API development

### **Stage Portal**
- **Description**: Stage-specific configuration and monitoring interface
- **Features**: Stage setup, sensor assignment, live monitoring, stage-specific settings
- **Status**: 🔴 Not Started - Depends on admin portal
- **Effort**: Medium (1-2 weeks) - Stage management system

---

## 👥 **Priority 5: User Interface Views**

### **Range Officer (RO) View**
- **Description**: Real-time range monitoring interface for Range Officers
- **Features**: Live impact monitoring, safety alerts, stage status, emergency controls
- **Status**: 🔴 Not Started - User requirements gathering needed
- **Effort**: Medium (1-2 weeks) - Specialized dashboard

### **Scorekeeper View**
- **Description**: Interface for official scoring and results management
- **Features**: Impact validation, score calculation, results export, dispute resolution
- **Status**: 🔴 Not Started - Scoring system design needed
- **Effort**: Large (2-3 weeks) - Complete scoring workflow

### **Match Director View**
- **Description**: Overall competition management and oversight interface
- **Features**: Multi-stage monitoring, competition flow, system status, reporting
- **Status**: 🔴 Not Started - Competition management requirements needed
- **Effort**: Large (2-3 weeks) - Competition management system

### **Team View**
- **Description**: Team performance monitoring and results interface
- **Features**: Team progress, individual scores, stage results, performance analytics
- **Status**: 🔴 Not Started - Team management system needed
- **Effort**: Medium (1-2 weeks) - Team dashboard + analytics

### **Coach View**
- **Description**: Training and performance analysis interface for coaches
- **Features**: Detailed analytics, training metrics, progress tracking, improvement suggestions
- **Status**: 🔴 Not Started - Analytics framework needed
- **Effort**: Large (2-3 weeks) - Advanced analytics + ML insights

---

## 🌩️ **Priority 6: Long-Term Cloud Integration**

### **Cloud Data Platform**
- **Description**: Comprehensive cloud-based data storage and processing platform
- **Features**: Secure data upload, real-time sync, historical data analysis, performance trends
- **Benefits**: Centralized data management, advanced analytics, cross-competition insights
- **Status**: 🔴 Not Started - Cloud architecture design needed
- **Effort**: Very Large (1-2 months) - Complete cloud infrastructure

### **PractiScore Integration**
- **Description**: Direct integration with PractiScore competition management system
- **Features**: Automatic score upload, competitor registration sync, match results integration
- **Benefits**: Seamless competition workflow, reduced manual data entry, official scoring compliance
- **Status**: 🔴 Not Started - PractiScore API research needed
- **Effort**: Large (3-4 weeks) - API integration + data mapping

### **Shot Analytics Platform**
- **Description**: Advanced shot analysis and performance tracking system
- **Features**: Shot pattern analysis, performance trends, comparative analytics, training recommendations
- **Benefits**: Deep performance insights, data-driven training, competitive advantage analysis
- **Status**: 🔴 Not Started - Analytics platform architecture needed
- **Effort**: Very Large (2-3 months) - ML/AI analytics engine

---

## 📊 **Backlog Management**

### **Status Legend**
- **🔴 Not Started** - Feature identified but no work begun
- **🟡 In Progress** - Active development underway  
- **🟢 Completed** - Feature implemented and tested
- **🔵 On Hold** - Paused pending dependencies or decisions

### **Prioritization Criteria**
1. **Critical Operations** - Features essential for live fire testing (Battery monitoring, BLE reliability)
2. **Hardware Evolution** - Next-generation platform improvements (New sensors, Non-Pi MCU)
3. **System Reliability** - Robustness and error handling enhancements (BLE reconnection, time sync, offline mode)
4. **Administration Tools** - Setup and configuration interfaces (Web portals, sensor management)
5. **User Experience** - Role-specific interfaces and dashboards (RO, Scorekeeper, Coach views)
6. **Cloud & Integration** - Long-term platform evolution (Cloud data, PractiScore, Shot Analytics)
7. **Performance & Analytics** - Advanced features and optimizations

---

## 🚀 **Current Sprint Focus**

### **Active Development**
- **BT50 Battery % Monitoring** - Research WitMotion protocol for battery data

### **Next Sprint Candidates**
- **BLE Reconnection Testing** - Critical for field reliability
- **Sensor Detection & Selection** - Foundation for multi-sensor support
- **Time Sync Implementation** - Eliminate timing drift issues

### **Future Major Initiatives**
- **Hardware Platform Migration** - Non-Pi MCU transition
- **Offline Mode Implementation** - Complete offline operations with sync capabilities
- **Web Administration System** - Complete admin portal development  
- **User Role Interfaces** - Specialized dashboards for different competition roles

### **Long-Term Vision (6+ months)**
- **Cloud Data Platform** - Comprehensive cloud-based data management and analytics
- **PractiScore Integration** - Direct integration with competition management systems
- **Shot Analytics Platform** - AI-powered performance analysis and insights

---

**Document Created**: September 11, 2025  
**Last Updated**: September 11, 2025  
**Maintainer**: GitHub Copilot  
**Status**: Active Backlog Management