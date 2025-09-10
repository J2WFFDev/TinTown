"""Configuration management for the Impact Bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class DetectorConfig:
    """Configuration for impact detection algorithms."""
    
    trigger_high: float = 0.05
    trigger_low: float = 0.01
    ring_min_ms: int = 10
    dead_time_ms: int = 50
    warmup_ms: int = 2000
    baseline_min: float = 1e-6
    min_amp: float = 0.01


@dataclass
class LoggingConfig:
    """Configuration for logging and data persistence."""
    
    dir: str = "./logs"
    file_prefix: str = "bridge"
    mode: str = "regular"  # regular or verbose
    debug_dir: str = "./logs/debug"
    verbose_whitelist: List[str] = None
    
    def __post_init__(self) -> None:
        if self.verbose_whitelist is None:
            self.verbose_whitelist = []


@dataclass
class DatabaseConfig:
    """Configuration for database and data ingest."""
    
    dir: str = "./db"
    file: str = "bridge.db"
    enable_ingest: bool = True


@dataclass
class AmgConfig:
    """Configuration for AMG Commander BLE connection."""
    
    adapter: str = "hci0"
    mac: str = ""
    name: str = ""
    start_uuid: str = ""
    write_uuid: str = ""
    init_cmds: List[str] = None
    commands: Dict[str, Dict[str, str]] = None
    reconnect_initial_sec: float = 2.0
    reconnect_max_sec: float = 20.0
    reconnect_jitter_sec: float = 1.0
    
    def __post_init__(self) -> None:
        if self.init_cmds is None:
            self.init_cmds = []
        if self.commands is None:
            self.commands = {}


@dataclass
class SensorConfig:
    """Configuration for individual BT50 sensor."""
    
    sensor: str  # sensor ID
    adapter: str = "hci0"
    mac: str = ""
    notify_uuid: str = ""
    config_uuid: str = ""
    plate: str = ""  # plate identifier (P1, P2, etc.)
    idle_reconnect_sec: float = 300.0
    keepalive_batt_sec: float = 30.0
    reconnect_initial_sec: float = 0.1
    reconnect_max_sec: float = 2.0
    reconnect_jitter_sec: float = 0.5


@dataclass
class AppConfig:
    """Main application configuration."""
    
    amg: Optional[AmgConfig] = None
    sensors: List[SensorConfig] = None
    detector: DetectorConfig = None
    logging: LoggingConfig = None
    database: DatabaseConfig = None
    
    def __post_init__(self) -> None:
        if self.sensors is None:
            self.sensors = []
        if self.detector is None:
            self.detector = DetectorConfig()
        if self.logging is None:
            self.logging = LoggingConfig()
        if self.database is None:
            self.database = DatabaseConfig()


def load_config(config_path: str) -> AppConfig:
    """Load configuration from YAML file with environment variable support."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with config_file.open("r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
    
    if not raw_config:
        raise ValueError(f"Empty or invalid configuration file: {config_path}")
    
    # Process environment variable substitutions
    _substitute_env_vars(raw_config)
    
    # Build configuration objects
    config = AppConfig()
    
    # AMG configuration
    if "amg" in raw_config:
        amg_data = raw_config["amg"]
        config.amg = AmgConfig(**amg_data)
    
    # Sensor configurations
    if "sensors" in raw_config:
        config.sensors = [SensorConfig(**sensor_data) for sensor_data in raw_config["sensors"]]
    
    # Detector configuration
    if "detector" in raw_config:
        config.detector = DetectorConfig(**raw_config["detector"])
    
    # Logging configuration
    if "logging" in raw_config:
        logging_data = raw_config["logging"]
        # Handle verbose_whitelist specially to ensure it's a list
        if "verbose_whitelist" in logging_data and logging_data["verbose_whitelist"]:
            if isinstance(logging_data["verbose_whitelist"], dict):
                # Convert dict keys to list (compatibility with existing configs)
                logging_data["verbose_whitelist"] = list(logging_data["verbose_whitelist"].keys())
        config.logging = LoggingConfig(**logging_data)
    
    # Database configuration
    if "database" in raw_config:
        config.database = DatabaseConfig(**raw_config["database"])
    
    return config


def _substitute_env_vars(data: Any) -> None:
    """Recursively substitute environment variables in configuration data."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                data[key] = os.getenv(env_var, value)
            else:
                _substitute_env_vars(value)
    elif isinstance(data, list):
        for item in data:
            _substitute_env_vars(item)


def validate_config(config: AppConfig) -> List[str]:
    """Validate configuration and return list of validation errors."""
    errors = []
    
    # Validate AMG configuration if present
    if config.amg:
        if not config.amg.mac:
            errors.append("AMG MAC address is required")
        if not config.amg.start_uuid:
            errors.append("AMG start_uuid is required")
    
    # Validate sensor configurations
    for i, sensor in enumerate(config.sensors):
        if not sensor.mac:
            errors.append(f"Sensor {i}: MAC address is required")
        if not sensor.notify_uuid:
            errors.append(f"Sensor {i}: notify_uuid is required")
        if not sensor.sensor:
            errors.append(f"Sensor {i}: sensor ID is required")
    
    # Validate detector configuration
    if config.detector.trigger_high <= 0:
        errors.append("Detector trigger_high must be positive")
    if config.detector.trigger_low <= 0:
        errors.append("Detector trigger_low must be positive")
    if config.detector.trigger_low >= config.detector.trigger_high:
        errors.append("Detector trigger_low must be less than trigger_high")
    
    # Validate paths exist or can be created
    for path_name, path_str in [
        ("logging.dir", config.logging.dir),
        ("logging.debug_dir", config.logging.debug_dir),
        ("database.dir", config.database.dir),
    ]:
        path = Path(path_str)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            errors.append(f"Cannot create directory {path_name}: {path_str} - {e}")
    
    return errors