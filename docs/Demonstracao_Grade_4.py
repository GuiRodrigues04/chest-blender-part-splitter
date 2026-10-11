"""Isolated geometry example; not a Blender test or a reproduction of the screenshot."""
import json
import math

side_mm = 103.0
margin_mm = 1.0
diameter_mm = 10.0
clearance_mm = 0.10
limit = side_mm / math.sqrt(2.0)
radius_with_margin = diameter_mm / 2.0 + clearance_mm + margin_mm

def profile_fits(u, v):
    # Square rotated 45 degrees: abs(u) + abs(v) <= limit.
    # Maximum for a circular footprint adds radius * sqrt(2).
    return abs(u) + abs(v) + radius_with_margin * math.sqrt(2.0) <= limit

def grid(offset):
    return [(sx * offset, sy * offset) for sx in (-1, 1) for sy in (-1, 1)]

legacy_offset = (limit - margin_mm) * 0.55
valid_offset = (limit - radius_with_margin * math.sqrt(2.0)) / 2.0 * 0.8
legacy = grid(legacy_offset)
alternative = grid(valid_offset)
assert not any(profile_fits(u, v) for u, v in legacy)
assert all(profile_fits(u, v) for u, v in alternative)
assert 2 * valid_offset > diameter_mm + 2 * clearance_mm

print(json.dumps({
    'scope': 'isolated mathematical demonstration; not Blender execution',
    'square_side_mm': side_mm,
    'axes_rotation_degrees': 45,
    'legacy_candidates_uv_mm': legacy,
    'legacy_fit': [profile_fits(u, v) for u, v in legacy],
    'possible_candidates_uv_mm': alternative,
    'possible_fit': [profile_fits(u, v) for u, v in alternative],
}, indent=2))
