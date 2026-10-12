"""No Blender: selecionar malhas e executar no Text Editor.
Não altera cena, seleção, materiais ou geometria; grava JSON ao lado do .blend.
Sem arquivo salvo, grava no diretório temporário do Blender.
Não mede espessura, interseções, cobertura ou imprimibilidade.
"""
import bpy
import bmesh
import json
from pathlib import Path
from collections import Counter


def measure(obj, evaluated=False):
    scene = bpy.context.scene
    scale = (scene.unit_settings.scale_length or 1.0) * 1000.0
    owner = None
    bm = None
    try:
        if evaluated:
            owner = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = owner.to_mesh()
            bm = bmesh.new()
            bm.from_mesh(mesh)
        elif obj.mode == 'EDIT':
            # Cópia da malha de edição, sem sincronização/mutação do original.
            bm = bmesh.from_edit_mesh(obj.data).copy()
            mesh = obj.data
        else:
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
        bm.transform(obj.matrix_world)
        bm.verts.index_update()
        bm.edges.index_update()
        bm.faces.index_update()
        bm.normal_update()
        # Duplicatas pela identidade dos vértices, não coincidência espacial.
        keys = Counter(tuple(sorted(v.index for v in f.verts)) for f in bm.faces)
        bounds = [
            (max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts)) * scale
            if bm.verts else 0.0 for i in range(3)
        ]
        suspicious = [
            {"edge": e.index, "vertices": [v.index for v in e.verts],
             "incidence": len(e.link_faces),
             "coords_world_mm": [[c * scale for c in v.co] for v in e.verts]}
            for e in bm.edges if not e.is_manifold
        ]
        return {
            "object": obj.name, "evaluated": evaluated,
            "edit_mode_evaluated_warning": obj.mode == 'EDIT' and evaluated,
            "matrix_world": [list(row) for row in obj.matrix_world],
            "scale_to_mm": scale, "verts": len(bm.verts), "faces": len(bm.faces),
            "signed_volume_mm3": bm.calc_volume(signed=True) * scale ** 3,
            "bounds_mm": bounds,
            "boundary_edges": sum(e.is_boundary for e in bm.edges),
            "wire_edges": sum(len(e.link_faces) == 0 for e in bm.edges),
            "branch_edges": sum(len(e.link_faces) > 2 for e in bm.edges),
            "non_contiguous_manifold_edges": sum(
                e.is_manifold and not e.is_contiguous for e in bm.edges),
            "areas_below_1e_minus_8_mm2": [
                f.index for f in bm.faces if f.calc_area() * scale ** 2 < 1e-8],
            "duplicate_faces_same_vertex_ids": sum(n - 1 for n in keys.values()),
            "material_slots": [m.name if m else None for m in mesh.materials],
            "face_material_counts": dict(Counter(f.material_index for f in bm.faces)),
            "invalid_material_faces": [
                f.index for f in bm.faces
                if f.material_index >= len(mesh.materials) and len(mesh.materials) > 0],
            "non_manifold_edges_detail": suspicious,
            "not_measured": ["thickness", "self_intersections",
                            "spatial_duplicate_faces", "A_B_overlap", "source_coverage"],
        }
    finally:
        if bm is not None:
            bm.free()
        if owner is not None:
            owner.to_mesh_clear()


result = {"blender": bpy.app.version_string, "scene": bpy.context.scene.name,
          "unit_system": bpy.context.scene.unit_settings.system,
          "scale_length": bpy.context.scene.unit_settings.scale_length,
          "objects": []}
for obj in list(bpy.context.selected_objects):
    if obj.type != 'MESH':
        continue
    for evaluated in (False, True):
        try:
            result["objects"].append(measure(obj, evaluated))
        except Exception as exc:
            result["objects"].append({"object": obj.name,
                                     "evaluated": evaluated, "error": str(exc)})
folder = Path(bpy.data.filepath).parent if bpy.data.filepath else Path(bpy.app.tempdir)
path = folder / "part_splitter_diagnostico.json"
path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print("Diagnóstico:", path)
