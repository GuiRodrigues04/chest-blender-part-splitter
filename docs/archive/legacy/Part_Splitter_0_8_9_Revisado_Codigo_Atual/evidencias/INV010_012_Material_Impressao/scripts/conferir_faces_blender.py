"""Executar no Text Editor do Blender, com cópia da cena aberta.
Somente leitura; não modifica objetos nem seleciona/apaga faces.
Confirma polígonos de área quase nula em todos os meshes salvos.
"""
import bpy
import bmesh
import json

scale = (bpy.context.scene.unit_settings.scale_length or 1.0) * 1000.0
rows = []
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    bm = None
    try:
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data).copy()
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bm.faces.index_update()
        bad = []
        for f in bm.faces:
            area = f.calc_area() * scale ** 2
            if area < 1e-8:
                bad.append({"face": f.index, "area_mm2": area,
                            "material_index": f.material_index,
                            "coords_world_mm": [[c * scale for c in v.co]
                                                for v in f.verts]})
        rows.append({"object": obj.name, "mesh": obj.data.name,
                     "faces": len(bm.faces), "degenerate_faces": bad})
    finally:
        if bm is not None:
            bm.free()
print(json.dumps({"blender": bpy.app.version_string,
                  "scale_to_mm": scale, "results": rows},
                 indent=2, ensure_ascii=False))
