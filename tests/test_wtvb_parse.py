import struct
from src.impact_bridge.ble.wtvb_parse import parse_5561


def make_frame(vx_raw: int, vy_raw: int, vz_raw: int) -> bytes:
    # header 0x55 0x61 then three int16 little-endian values
    return bytes([0x55, 0x61]) + struct.pack('<hhh', vx_raw, vy_raw, vz_raw)


def approx(a, b, rel=1e-3):
    if b == 0:
        return abs(a) < rel
    return abs(a - b) <= rel * max(abs(a), abs(b))


def test_parse_single_frame():
    # craft known int16 values and assert parsed scaled values match expectation
    vx_raw, vy_raw, vz_raw = 1000, -1000, 0
    payload = make_frame(vx_raw, vy_raw, vz_raw)

    pkt = parse_5561(payload)
    assert pkt is not None
    assert 'samples' in pkt and len(pkt['samples']) == 1

    s = pkt['samples'][0]
    # scale used in parse_5561: 16.0 / 32768.0
    scale = 16.0 / 32768.0
    assert approx(s['vx'], vx_raw * scale)
    assert approx(s['vy'], vy_raw * scale)
    assert approx(s['vz'], vz_raw * scale)


def test_parse_multiple_frames_and_avg():
    # two frames concatenated
    f1 = make_frame(500, 500, 500)
    f2 = make_frame(-500, -500, -500)
    payload = f1 + f2

    pkt = parse_5561(payload)
    assert pkt is not None
    assert 'samples' in pkt and len(pkt['samples']) == 2

    # average should be approximately zero for each axis
    assert approx(pkt['VX'], 0.0, rel=1e-2)
    assert approx(pkt['VY'], 0.0, rel=1e-2)
    assert approx(pkt['VZ'], 0.0, rel=1e-2)
