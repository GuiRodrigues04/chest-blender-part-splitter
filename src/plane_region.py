"""Finite planar selection, shared by the cutter, guide, preview and fingerprints."""
from dataclasses import dataclass
from mathutils import Vector


@dataclass(frozen=True)
class PlaneRegion:
    corners: tuple

    def coordinates(self, point):
        a, b, _, d = self.corners
        u, v, p = b-a, d-a, point-a
        uu, vv, uv = u.dot(u), v.dot(v), u.dot(v)
        det = uu*vv-uv*uv
        if det <= max(uu*vv, 1e-30)*1e-12:
            raise ValueError('O retângulo de corte tem tamanho nulo. Aumente largura e altura.')
        return ((p.dot(u)*vv-p.dot(v)*uv)/det,
                (p.dot(v)*uu-p.dot(u)*uv)/det)

    def contains(self, point, tolerance=1e-6):
        return all(-tolerance <= x <= 1+tolerance for x in self.coordinates(point))

    def clip_segment(self, a, b):
        """Clip in the actual affine guide frame, including nonuniform scale/shear."""
        pa, pb = self.coordinates(a), self.coordinates(b)
        low, high = 0.0, 1.0
        for x, y in zip(pa, pb):
            delta = y-x
            if abs(delta) < 1e-15:
                if x < -1e-6 or x > 1+1e-6:
                    return None
            else:
                t0, t1 = -x/delta, (1-x)/delta
                low, high = max(low, min(t0, t1)), min(high, max(t0, t1))
                if low > high+1e-9:
                    return None
        return a.lerp(b, max(0.0, low)), a.lerp(b, min(1.0, high))

    def shifted(self, delta):
        return PlaneRegion(tuple(p+delta for p in self.corners))


def guide_region(scene):
    from .constants import PLANE_GUIDE_NAME
    guide = scene.objects.get(PLANE_GUIDE_NAME)
    if guide is None or guide.type != 'MESH':
        return None
    if guide.mode == 'EDIT':
        import bmesh
        points = [v.co.copy() for v in bmesh.from_edit_mesh(guide.data).verts]
    else:
        points = [v.co.copy() for v in guide.data.vertices]
    if not points:
        return None
    x0, x1 = min(p.x for p in points), max(p.x for p in points)
    y0, y1 = min(p.y for p in points), max(p.y for p in points)
    z = sum(p.z for p in points)/len(points)
    mw = guide.matrix_world
    return PlaneRegion(tuple(mw @ Vector(p) for p in
                             ((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z))))


def resolve_plane_region(scene, settings, with_offset=False):
    if getattr(settings, 'plane_extent_mode', 'FULL') != 'LIMITED':
        return None
    from .geometry_plane import PlaneSliceError
    region = guide_region(scene)
    if region is None:
        raise PlaneSliceError('Crie o guia do plano para definir a área limitada.')
    try:
        region.coordinates(region.corners[0])
    except ValueError as exc:
        raise PlaneSliceError(str(exc)) from exc
    if with_offset:
        from .plane_state import resolve_plane_state
        from .diagnostic import get_scene_scale_to_mm
        _, normal = resolve_plane_state(scene, settings)
        region = region.shifted(normal * settings.plane_offset_mm/get_scene_scale_to_mm(scene))
    return region


def region_signature(scene, settings):
    if getattr(settings, 'plane_extent_mode', 'FULL') != 'LIMITED':
        return ()
    region = guide_region(scene)
    return tuple(tuple(p) for p in region.corners) if region else ('MISSING_GUIDE',)


def dimension_mm(settings, axis):
    from .diagnostic import get_scene_scale_to_mm
    region = guide_region(settings.id_data)
    if region is None:
        return 100.0
    a, b, _, d = region.corners
    return ((b-a) if axis == 0 else (d-a)).length*get_scene_scale_to_mm(settings.id_data)


def set_dimension_mm(settings, axis, value):
    from .constants import PLANE_GUIDE_NAME
    guide = settings.id_data.objects.get(PLANE_GUIDE_NAME)
    current = dimension_mm(settings, axis)
    if guide and current > 1e-12:
        guide.scale[axis] *= max(.01, value)/current
