#!/usr/bin/env python3
"""
TinTown Development Configuration Manager

Manages development vs production configurations for enhanced logging, 
timing analysis, and debugging features during the development phase.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DevConfig:
    """Development configuration manager for TinTown bridge"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/development.yaml"
        self.config = self._load_config()
        self.is_dev_mode = self.config.get('development_mode', False)
        
        # Apply production overrides if not in development mode
        if not self.is_dev_mode:
            self._apply_production_overrides()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load development configuration from YAML file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                logger.info(f"📋 Loaded development config from {self.config_path}")
                return config
            else:
                logger.warning(f"Development config not found: {self.config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading development config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default development configuration"""
        return {
            'development_mode': False,
            'enhanced_logging': {'enabled': False},
            'analysis_tools': {'enabled': False},
            'enhanced_impact': {'enabled': True},
            'timing_calibration': {'enhanced_mode': True}
        }
    
    def _apply_production_overrides(self):
        """Apply production overrides when not in development mode"""
        overrides = self.config.get('production_overrides', {})
        for section, settings in overrides.items():
            if section in self.config:
                self.config[section].update(settings)
        logger.info("🏭 Applied production configuration overrides")
    
    # Enhanced Logging Configuration
    def is_enhanced_logging_enabled(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('enabled', False)
    
    def is_sample_logging_enabled(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('sample_logging', False)
    
    def is_impact_analysis_enabled(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('impact_analysis', False)
    
    def is_timing_correlation_logging_enabled(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('timing_correlation', False)
    
    def should_log_all_samples(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('log_all_samples', False)
    
    def should_log_impact_samples(self) -> bool:
        return self.config.get('enhanced_logging', {}).get('log_impact_samples', True)
    
    def get_impact_window_samples(self) -> int:
        return self.config.get('enhanced_logging', {}).get('impact_window_samples', 50)
    
    # Debug Levels
    def get_bridge_debug_level(self) -> str:
        return self.config.get('enhanced_logging', {}).get('bridge_debug', 'INFO')
    
    def get_timing_debug_level(self) -> str:
        return self.config.get('enhanced_logging', {}).get('timing_debug', 'INFO')
    
    def get_impact_debug_level(self) -> str:
        return self.config.get('enhanced_logging', {}).get('impact_debug', 'INFO')
    
    # Analysis Tools Configuration
    def are_analysis_tools_enabled(self) -> bool:
        return self.config.get('analysis_tools', {}).get('enabled', False)
    
    def is_strip_chart_generator_enabled(self) -> bool:
        return self.config.get('analysis_tools', {}).get('strip_chart_generator', False)
    
    def is_correlation_analyzer_enabled(self) -> bool:
        return self.config.get('analysis_tools', {}).get('correlation_analyzer', False)
    
    def get_export_formats(self) -> list:
        return self.config.get('analysis_tools', {}).get('export_formats', ['json'])
    
    # Enhanced Impact Detection Configuration  
    def is_enhanced_impact_enabled(self) -> bool:
        return self.config.get('enhanced_impact', {}).get('enabled', True)
    
    def get_onset_threshold(self) -> float:
        return self.config.get('enhanced_impact', {}).get('onset_threshold', 30.0)
    
    def get_peak_threshold(self) -> float:
        return self.config.get('enhanced_impact', {}).get('peak_threshold', 150.0)
    
    def get_lookback_samples(self) -> int:
        return self.config.get('enhanced_impact', {}).get('lookback_samples', 10)
    
    def is_confidence_logging_enabled(self) -> bool:
        return self.config.get('enhanced_impact', {}).get('confidence_logging', True)
    
    # Timing Calibration Configuration
    def is_enhanced_timing_enabled(self) -> bool:
        return self.config.get('timing_calibration', {}).get('enhanced_mode', True)
    
    def get_timing_learning_rate(self) -> float:
        return self.config.get('timing_calibration', {}).get('learning_rate', 0.1)
    
    def is_validation_logging_enabled(self) -> bool:
        return self.config.get('timing_calibration', {}).get('validation_logging', True)
    
    def is_baseline_analysis_enabled(self) -> bool:
        return self.config.get('timing_calibration', {}).get('baseline_analysis', True)
    
    # Performance Monitoring
    def is_performance_monitoring_enabled(self) -> bool:
        return self.config.get('performance_monitoring', {}).get('enabled', False)
    
    def is_sample_rate_tracking_enabled(self) -> bool:
        return self.config.get('performance_monitoring', {}).get('sample_rate_tracking', False)
    
    def is_processing_time_tracking_enabled(self) -> bool:
        return self.config.get('performance_monitoring', {}).get('processing_time_tracking', False)
    
    # Development Utilities
    def is_auto_backup_enabled(self) -> bool:
        return self.config.get('dev_utilities', {}).get('auto_backup_logs', False)
    
    def is_test_mode_markers_enabled(self) -> bool:
        return self.config.get('dev_utilities', {}).get('test_mode_markers', True)
    
    def is_timing_validation_enabled(self) -> bool:
        return self.config.get('dev_utilities', {}).get('timing_validation', True)
    
    def is_data_export_enabled(self) -> bool:
        return self.config.get('dev_utilities', {}).get('data_export', True)
    
    # Configuration Status
    def get_mode_description(self) -> str:
        if self.is_dev_mode:
            return "🔧 Development Mode (Enhanced logging and analysis enabled)"
        else:
            return "🏭 Production Mode (Optimized performance)"
    
    def print_config_summary(self):
        """Print configuration summary for startup logging"""
        logger.info("="*60)
        logger.info("🔧 TINTOWN DEVELOPMENT CONFIGURATION")
        logger.info("="*60)
        logger.info(f"Mode: {self.get_mode_description()}")
        logger.info(f"Enhanced Logging: {'✅' if self.is_enhanced_logging_enabled() else '❌'}")
        logger.info(f"Sample Logging: {'✅' if self.is_sample_logging_enabled() else '❌'}")
        logger.info(f"Impact Analysis: {'✅' if self.is_impact_analysis_enabled() else '❌'}")
        logger.info(f"Timing Correlation: {'✅' if self.is_timing_correlation_logging_enabled() else '❌'}")
        logger.info(f"Analysis Tools: {'✅' if self.are_analysis_tools_enabled() else '❌'}")
        logger.info(f"Enhanced Impact Detection: {'✅' if self.is_enhanced_impact_enabled() else '❌'}")
        logger.info(f"Performance Monitoring: {'✅' if self.is_performance_monitoring_enabled() else '❌'}")
        
        if self.is_enhanced_impact_enabled():
            logger.info(f"  Onset Threshold: {self.get_onset_threshold():.1f}g")
            logger.info(f"  Peak Threshold: {self.get_peak_threshold():.1f}g")
            logger.info(f"  Lookback Samples: {self.get_lookback_samples()}")
        
        logger.info("="*60)

# Global development configuration instance
dev_config = DevConfig()

# Convenience functions for easy access
def is_dev_mode() -> bool:
    return dev_config.is_dev_mode

def is_enhanced_logging_enabled() -> bool:
    return dev_config.is_enhanced_logging_enabled()

def is_sample_logging_enabled() -> bool:
    return dev_config.is_sample_logging_enabled()

def is_analysis_tools_enabled() -> bool:
    return dev_config.are_analysis_tools_enabled()

def get_enhanced_impact_config() -> dict:
    return {
        'enabled': dev_config.is_enhanced_impact_enabled(),
        'onset_threshold': dev_config.get_onset_threshold(),
        'peak_threshold': dev_config.get_peak_threshold(),
        'lookback_samples': dev_config.get_lookback_samples()
    }

if __name__ == "__main__":
    # Test the configuration system
    logging.basicConfig(level=logging.INFO)
    dev_config.print_config_summary()
    
    print(f"\nTesting configuration access:")
    print(f"Development mode: {is_dev_mode()}")
    print(f"Enhanced logging: {is_enhanced_logging_enabled()}")
    print(f"Sample logging: {is_sample_logging_enabled()}")
    print(f"Analysis tools: {is_analysis_tools_enabled()}")
    print(f"Enhanced impact config: {get_enhanced_impact_config()}")