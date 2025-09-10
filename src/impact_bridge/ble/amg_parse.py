"""
AMG Timer Data Parser
Based on analysis of DenisZhadan/AmgLabCommander and ankitaios24/AMG-Commander-Bluetooth

Hex data structure for AMG timers:
- bytes[0]: Type/State identifier  
- bytes[1]: Shot state (3=active, 5=start, 8=stopped)
- bytes[2]: Current shot number
- bytes[3]: Total shots
- bytes[4-5]: Current shot time (2 bytes, big-endian)
- bytes[6-7]: Split time (2 bytes, big-endian)
- bytes[8-9]: First shot time (2 bytes, big-endian)
- bytes[10-11]: Second shot time (2 bytes, big-endian)
- bytes[12-13]: Current round/series (2 bytes, big-endian)
"""

from enum import IntEnum
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ShotState(IntEnum):
    """Shot states from AMG timer"""
    ACTIVE = 3
    START = 5
    STOPPED = 8

def convert_time_bytes(byte1: int, byte2: int) -> float:
    """
    Convert two bytes to time value in seconds
    Based on Java implementation: value = 256 * value1 + value2; return value / 100.0
    """
    value = (byte1 << 8) | byte2  # Big-endian 16-bit value
    if byte2 < 0:  # Handle signed byte conversion
        value += 256
    return value / 100.0  # Convert to seconds with centisecond precision

def parse_amg_timer_data(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse AMG timer hex data into structured format
    
    Args:
        data: Raw bytes from AMG timer notification
        
    Returns:
        Dict with parsed timer data or None if invalid
    """
    if len(data) < 14:
        logger.warning(f"AMG data too short: {len(data)} bytes, need at least 14")
        return None
    
    try:
        # Convert bytes to list for easier access
        bytes_list = list(data)
        
        # Parse header
        type_id = bytes_list[0]
        shot_state_raw = bytes_list[1]
        
        # Validate shot state
        try:
            shot_state = ShotState(shot_state_raw)
        except ValueError:
            logger.warning(f"Unknown shot state: {shot_state_raw}")
            shot_state = ShotState.ACTIVE  # Default
        
        # Parse shot data
        current_shot = bytes_list[2]
        total_shots = bytes_list[3]
        
        # Parse time values (2-byte big-endian each)
        current_time = convert_time_bytes(bytes_list[4], bytes_list[5])
        split_time = convert_time_bytes(bytes_list[6], bytes_list[7])
        first_shot_time = convert_time_bytes(bytes_list[8], bytes_list[9])
        second_shot_time = convert_time_bytes(bytes_list[10], bytes_list[11])
        current_round = (bytes_list[12] << 8) | bytes_list[13]
        
        # Determine event type based on state and data
        event_type = "String"  # Default to String for timer events
        
        if shot_state == ShotState.START:
            event_detail = "Timer Started"
        elif shot_state == ShotState.STOPPED:
            event_detail = "Timer Stopped"
        elif shot_state == ShotState.ACTIVE:
            if type_id == 1 and shot_state_raw == 3:
                event_detail = f"Shot {current_shot}: {current_time:.2f}s"
            elif 10 <= type_id <= 26:
                event_detail = f"Shot Sequence {current_shot}/{total_shots}: {current_time:.2f}s"
            else:
                event_detail = f"Timer Active: {current_time:.2f}s"
        else:
            event_detail = f"State {shot_state_raw}: {current_time:.2f}s"
        
        result = {
            'type_id': type_id,
            'shot_state': shot_state.name,
            'shot_state_raw': shot_state_raw,
            'current_shot': current_shot,
            'total_shots': total_shots,
            'current_time': current_time,
            'split_time': split_time,
            'first_shot_time': first_shot_time,
            'second_shot_time': second_shot_time,
            'current_round': current_round,
            'event_type': event_type,
            'event_detail': event_detail,
            'raw_hex': data.hex().upper()
        }
        
        logger.debug(f"Parsed AMG data: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error parsing AMG data: {e}, hex: {data.hex()}")
        return None

def format_amg_event(parsed_data: Dict[str, Any]) -> str:
    """
    Format parsed AMG data into human-readable string for logging
    
    Args:
        parsed_data: Result from parse_amg_timer_data()
        
    Returns:
        Formatted string description
    """
    if not parsed_data:
        return "Invalid AMG data"
    
    state = parsed_data['shot_state']
    current_time = parsed_data['current_time']
    event_detail = parsed_data['event_detail']
    
    if state == 'START':
        return f"Timer Started (Round {parsed_data['current_round']})"
    elif state == 'STOPPED':
        return f"Timer Stopped - Total: {current_time:.2f}s"
    elif state == 'ACTIVE':
        return event_detail
    else:
        return f"{state}: {event_detail}"

# Test function for validation
def test_amg_parser():
    """Test AMG parser with sample data"""
    # Example hex data (would need real data to test properly)
    test_data = bytes.fromhex("010300010502004000300020001000")  # 14 bytes
    
    result = parse_amg_timer_data(test_data)
    if result:
        print(f"Parsed: {result}")
        print(f"Formatted: {format_amg_event(result)}")
    else:
        print("Failed to parse test data")

if __name__ == "__main__":
    test_amg_parser()