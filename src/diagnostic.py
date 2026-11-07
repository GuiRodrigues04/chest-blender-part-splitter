"""Diagnóstico e análise geométrica de malhas para o Chest Part Splitter."""

from typing import Dict, Any, List, Tuple, Optional
import bpy
import bmesh
from mathutils import Vector
from .constants import MIN_FACE_AREA_BU, SCALE_TOLERANCE



def get_scene_scale_to_mm(scene) -> float:
    """Retorna o fator de conversão de unidades do Blender para milímetros."""
    if scene and scene.unit_settings:
        scale_length = scene.unit_settings.scale_length
        if scale_length > 0:
            return scale_length * 1000.0
    return 1000.0


def analyze_target_mesh(obj: bpy.types.Object, scene: bpy.types.Scene) -> dict:
    """Executa diagnóstico completo da malha do objeto alvo.
    
    Retorna métricas de dimensões físicas em mm, volume, contagem de triângulos,
    status de manifoldness, escala aplicada e integridade de faces.
    """
    if not obj or obj.type != 'MESH':
        return {
            "valid": False,
            "errors": ["Objeto alvo inválido ou não é uma malha (MESH)."],
            "warnings": [],
            "dims_mm": (0.0, 0.0, 0.0),
            "triangles": 0,
            "faces": 0,
            "volume_mm3": 0.0,
            "is_manifold": False,
            "non_manifold_edges": 0,
            "has_unapplied_scale": False,
            "is_non_uniform_scale": False,
            "degenerate_faces": 0,
        }

    errors = []
    warnings = []
    scale_to_mm = get_scene_scale_to_mm(scene)

    # 1. Análise de transformações e escala no objeto
    scale = obj.scale
    is_singular = (abs(scale.x) < 1e-7 or abs(scale.y) < 1e-7 or abs(scale.z) < 1e-7)
    if is_singular:
        errors.append("A escala do objeto possui componentes nulos (matriz singular).")

    has_unapplied_scale = (
        abs(scale.x - 1.0) > SCALE_TOLERANCE
        or abs(scale.y - 1.0) > SCALE_TOLERANCE
        or abs(scale.z - 1.0) > SCALE_TOLERANCE
    )
    is_non_uniform_scale = (
        abs(scale.x - scale.y) > SCALE_TOLERANCE
        or abs(scale.x - scale.z) > SCALE_TOLERANCE
    )

    if has_unapplied_scale:
        warnings.append(
            f"Escala não aplicada: ({scale.x:.3f}, {scale.y:.3f}, {scale.z:.3f}). Recomenda-se criar cópia com transformações aplicadas."
        )

    # 2. Avaliação de malha com modificadores
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    try:
        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        # Transforma o snapshot para World Space para métricas físicas fidedignas sob qualquer escala/rotação
        bm.transform(obj.matrix_world)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        face_count = len(bm.faces)
        tri_count = sum(len(f.verts) - 2 for f in bm.faces)

        # Cálculo de volume físico em mm³ (World Space)
        vol_bu = abs(bm.calc_volume(signed=True))
        vol_mm3 = vol_bu * (scale_to_mm ** 3)

        # Checagem de arestas não-manifold
        non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
        is_manifold = (non_manifold_edges == 0 and face_count > 0)

        if not is_manifold and face_count > 0:
            warnings.append(
                f"Malha possui {non_manifold_edges} aresta(s) abertas ou não-manifold."
            )

        # Checagem de faces degeneradas
        degenerate_faces = len(validate_bmesh_mesh_geometry(bm, scale_to_mm)['degenerate_faces'])
        if degenerate_faces > 0:
            warnings.append(
                f"Malha possui {degenerate_faces} face(s) com área nula ou degenerada."
            )

        # Dimensões físicas avaliadas no espaço de mundo em mm
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        if xs:
            dims_mm = (
                round((max(xs) - min(xs)) * scale_to_mm, 2),
                round((max(ys) - min(ys)) * scale_to_mm, 2),
                round((max(zs) - min(zs)) * scale_to_mm, 2),
            )
        else:
            dims_mm = (0.0, 0.0, 0.0)

        bm.free()
    finally:
        eval_obj.to_mesh_clear()

    is_valid = len(errors) == 0

    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "dims_mm": dims_mm,
        "triangles": tri_count,
        "faces": face_count,
        "volume_mm3": round(vol_mm3, 2),
        "is_manifold": is_manifold,
        "non_manifold_edges": non_manifold_edges,
        "has_unapplied_scale": has_unapplied_scale,
        "is_non_uniform_scale": is_non_uniform_scale,
        "degenerate_faces": degenerate_faces,
    }


def stable_signed_volume_mm3(bm, scale_to_mm):
    """Double-precision signed volume, independent of BMesh float summation.

    Translation near one source vertex limits cancellation. Signed fans also
    handle concave planar polygons; no coordinate or topology is modified.
    """
    import math
    if not bm.verts:
        return 0.0
    reference = tuple(next(iter(bm.verts)).co)
    terms = []
    for face in bm.faces:
        points = [tuple((float(v.co[i])-reference[i])*scale_to_mm for i in range(3)) for v in face.verts]
        if len(points) < 3:
            continue
        a = points[0]
        for b, c in zip(points[1:-1], points[2:]):
            terms.append((a[0]*(b[1]*c[2]-b[2]*c[1]) +
                          a[1]*(b[2]*c[0]-b[0]*c[2]) +
                          a[2]*(b[0]*c[1]-b[1]*c[0]))/6.0)
    return math.fsum(terms)


def sanitize_mesh_micro_degeneracies(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> bool:
    """Repair local Boolean roundoff, including long, nearly collinear slivers.

    Only connected micro-edges or invalid faces thinner than 0.0001 mm may be
    dissolved. Small real facets are retained. Roll back unless strict geometry,
    manifoldness, bounds and volume checks accept the complete repair.
    """
    eps_bu = 1e-4 / max(1e-6, scale_to_mm)
    before = validate_bmesh_mesh_geometry(bm, scale_to_mm)
    before_volume = stable_signed_volume_mm3(bm, scale_to_mm)
    bm.faces.ensure_lookup_table()
    def sliver_edges():
        bm.faces.index_update()
        report = validate_bmesh_mesh_geometry(bm, scale_to_mm)
        bm.faces.ensure_lookup_table()
        edges = set()
        for index in report['degenerate_faces']:
            face = bm.faces[index]
            longest = max((e.calc_length() for e in face.edges), default=0.0)
            # Area alone also flags small but well-shaped facets. Require a
            # sub-micrometre height before touching a face, regardless of size.
            if longest > 0 and 2 * face.calc_area() / longest <= eps_bu:
                edges.update(face.edges)
        return list(edges)

    micro_edges = [e for e in bm.edges if e.is_valid and e.calc_length() < eps_bu]
    if not micro_edges and not sliver_edges():
        return False
    
    parent = {}
    def find(v):
        p = parent.get(v, v)
        if p != v:
            p = find(p)
            parent[v] = p
        return p

    def union(v_from, v_to):
        root_from = find(v_from)
        root_to = find(v_to)
        if root_from != root_to:
            parent[root_from] = root_to

    for e in micro_edges:
        if e.is_valid and len(e.verts) == 2:
            union(e.verts[1], e.verts[0])

    targetmap = {}
    for v in list(parent.keys()):
        root = find(v)
        if v != root:
            targetmap[v] = root

    bounds = [(min(v.co[i] for v in bm.verts), max(v.co[i] for v in bm.verts)) for i in range(3)]
    backup = bm.copy()
    accepted = False

    try:
        if targetmap:
            bmesh.ops.weld_verts(bm, targetmap=targetmap)
        # One dissolve can expose another collinear triangle in the same fan.
        for _ in range(4):
            edges = sliver_edges()
            if not edges:
                break
            bmesh.ops.dissolve_degenerate(bm, edges=edges, dist=eps_bu)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        after = validate_bmesh_mesh_geometry(bm, scale_to_mm)
        if not after['is_valid'] or not bm.faces or not bm.verts:
            return False
        if len(after['non_manifold_edges']) > len(before['non_manifold_edges']):
            return False
        volume_tolerance = max(1e-5, abs(before_volume) * 1e-8)
        if abs(stable_signed_volume_mm3(bm, scale_to_mm) - before_volume) > volume_tolerance:
            return False
        for i, (low, high) in enumerate(bounds):
            if abs(min(v.co[i] for v in bm.verts) - low) > eps_bu or abs(max(v.co[i] for v in bm.verts) - high) > eps_bu:
                return False
        accepted = True
        return True
    except Exception:
        return False
    finally:
        if not accepted:
            # Copy through a temporary Mesh because BMesh has no from_bmesh API.
            tmp_mesh = bpy.data.meshes.new('_splitter_cleanup_rollback')
            try:
                backup.to_mesh(tmp_mesh)
                bm.clear()
                bm.from_mesh(tmp_mesh)
            finally:
                bpy.data.meshes.remove(tmp_mesh)
        backup.free()


def validate_mesh_repair_change(before, after, scale_to_mm):
    """Accept only closed repairs within 0.0001 mm, including material areas.

    Candidate generation is local welding/dissolving only; these checks never
    authorize filling holes, remeshing or removing small colour islands.
    """
    from collections import defaultdict
    report = validate_bmesh_mesh_geometry(after, scale_to_mm)
    if not after.faces or not report['is_valid'] or not report['is_manifold']:
        return False
    old_volume = abs(before.calc_volume()) * scale_to_mm ** 3
    new_volume = abs(after.calc_volume()) * scale_to_mm ** 3
    if new_volume <= 1e-9 or abs(new_volume-old_volume) > max(1e-5, old_volume*1e-8):
        return False
    def areas(bm):
        result = defaultdict(float)
        for face in bm.faces:
            result[face.material_index] += face.calc_area()*scale_to_mm**2
        return result
    original, candidate = areas(before), areas(after)
    if set(original) != set(candidate):
        return False
    if any(abs(candidate[k]-value) > max(1e-6, value*1e-10) for k,value in original.items()):
        return False
    tolerance = 0.0001 / scale_to_mm
    for axis in range(3):
        for bound in (min, max):
            if abs(bound(v.co[axis] for v in before.verts)-bound(v.co[axis] for v in after.verts)) > tolerance:
                return False
    from .repair_surface import surface_samples_within
    return surface_samples_within(before, after, tolerance)



def validate_bmesh_mesh_geometry(bm: bmesh.types.BMesh, scale_to_mm: float = 1000.0) -> Dict[str, Any]:
    """Valida a geometria de um BMesh medindo integridade, áreas nulas e degenerações (INV-010 / DEV-01)."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 1. Arestas de comprimento nulo calibradas pela escala física (< 0.1 µm)
    eps_length_bu = 1e-4 / max(1e-6, scale_to_mm)
    null_edges = [e.index for e in bm.edges if e.calc_length() < eps_length_bu]

    # 2. Faces de área nula / colineares / com vértices coincidentes
    min_face_area_mm2 = 1e-6
    eps_dist_bu_sq = (eps_length_bu) ** 2
    degenerate_faces = []
    for f in bm.faces:
        area_mm2 = f.calc_area() * (scale_to_mm ** 2)
        # Small area alone does not imply degeneracy: imported meshes may
        # contain tiny, well-shaped facets at colour boundaries. Require a
        # sub-tolerance altitude as well, using the same physical tolerance
        # as the coincident-vertex/zero-edge checks.
        longest_mm = max((e.calc_length() * scale_to_mm for e in f.edges), default=0.0)
        collapsed = (area_mm2 <= 0.0 or longest_mm <= 0.0 or
                     (area_mm2 < min_face_area_mm2 and
                      2.0 * area_mm2 / longest_mm <= eps_length_bu * scale_to_mm))
        if collapsed:
            degenerate_faces.append(f.index)
        else:
            coords = [v.co for v in f.verts]
            has_coincident = False
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    if (coords[i] - coords[j]).length_squared < eps_dist_bu_sq:
                        has_coincident = True
                        break
                if has_coincident:
                    break
            if has_coincident:
                degenerate_faces.append(f.index)

    # 3. Arestas não-manifold
    non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold]

    # 4. Volume orientado
    vol_bu = bm.calc_volume(signed=True)
    vol_mm3 = vol_bu * (scale_to_mm ** 3)

    return {
        "is_valid": len(null_edges) == 0 and len(degenerate_faces) == 0,
        "null_edges": null_edges,
        "degenerate_faces": degenerate_faces,
        "non_manifold_edges": non_manifold_edges,
        "is_manifold": len(non_manifold_edges) == 0,
        "volume_mm3": vol_mm3,
    }
