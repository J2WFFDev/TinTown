# TinTown Impact Bridge - Tests

This directory contains unit tests and validation:

## Test Coverage:

- **Unit Tests**: Core detection algorithms
- **BLE Protocol Tests**: AMG and BT50 protocol validation  
- **Integration Tests**: Multi-component scenarios
- **Calibration Tests**: Raw count baseline validation

## Running Tests:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=impact_bridge

# Run specific test
pytest test_detector.py::TestHitDetector::test_simple_impact_detection
```

## Test Requirements:

Tests that require BLE hardware should be run on the Raspberry Pi with actual devices connected.