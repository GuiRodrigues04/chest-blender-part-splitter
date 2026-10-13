"""Executar em cópia de Testes_2.blend no Text Editor. Somente leitura."""
import bpy
import bmesh
import json

settings = getattr(bpy.context.scene, "chest_splitter", None)
if settings is None:
    raise RuntimeError("Ative a extensão para ler os parâmetros salvos.")
indices = [int(i) for i in settings.loop_vertex_indices.split(",") if i.strip()]
rows = []
for name in ["Cube", "Cube__B"]:
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != 'MESH':
        continue
    bm = None
    try:
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data).copy()
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        invalid = [i for i in indices if i < 0 or i >= len(bm.verts)]
        missing = []
        if not invalid:
            for i, a in enumerate(indices):
                b = indices[(i + 1) % len(indices)]
                if bm.edges.get((bm.verts[a], bm.verts[b])) is None:
                    missing.append([a, b])
        rows.append({"object": name, "verts": len(bm.verts),
                     "edges": len(bm.edges), "faces": len(bm.faces),
                     "invalid_indices": invalid, "missing_edges": missing})
    finally:
        if bm is not None:
            bm.free()
print(json.dumps({"target": settings.target_object.name if settings.target_object else None,
                  "saved_signature": settings.loop_topology_signature,
                  "indices_count": len(indices), "checks": rows},
                 indent=2, ensure_ascii=False))
