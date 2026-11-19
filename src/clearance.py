"""Effective clearances without changing independently saved values."""

def bottom_clearance(settings):
    if getattr(settings, "clearance_use_general", False):
        return None
    return (getattr(settings, "part_clearance_bottom_mm", 0.0)
            if getattr(settings, "part_clearance_bottom_enable", False) else None)

def radial_clearance(settings):
    return (getattr(settings, "part_clearance_mm", 0.0)
            if getattr(settings, "clearance_use_general", False)
            else getattr(settings, "clearance_per_side_mm", 0.15))

def end_clearance(settings):
    return (getattr(settings, "part_clearance_mm", 0.0)
            if getattr(settings, "clearance_use_general", False)
            else getattr(settings, "end_clearance_mm", 0.2))
