"""Inventário somente leitura da cena aberta. Não é teste funcional do corte.

Uso: blender --disable-autoexec -b casos/Padrao_1.blend --python INVENTARIO_BLENDER.py -- resultado.json
Execute em cópia do caso; este script não salva nem modifica a cena.
"""
import bpy
import json
import sys
from collections import Counter
from pathlib import Path

def properties(group):
    result = {}
    if not group:
        return result
    for prop in group.bl_rna.properties:
        name=prop.identifier
        if name=='rna_type': continue
        try:
            value=getattr(group,name)
            if isinstance(value,bpy.types.ID): value=value.name
            elif isinstance(value,(str,int,float,bool)) or value is None: pass
            elif prop.type=='COLLECTION': value=f'{len(value)} items'
            else: value=list(value)
            result[name]=value
        except Exception as exc: result[name]=f'unreadable: {type(exc).__name__}'
    return result

scene=bpy.context.scene
report={'note':'Inventário, não validação funcional', 'blender':bpy.app.version_string,
        'filepath':bpy.data.filepath,'unit_scale_length':scene.unit_settings.scale_length,
        'active':getattr(bpy.context.view_layer.objects.active,'name',None),
        'splitter_settings':properties(getattr(scene,'chest_splitter',None)), 'objects':[]}
for obj in scene.objects:
    entry={'name':obj.name,'type':obj.type,'mode':obj.mode,'selected':obj.select_get(),
           'matrix_world':[list(row) for row in obj.matrix_world],
           'parent':getattr(obj.parent,'name',None),
           'modifiers':[{'name':m.name,'type':m.type} for m in obj.modifiers],
           'collections':[c.name for c in obj.users_collection]}
    if obj.type=='MESH':
        mesh=obj.data
        entry.update({'mesh':mesh.name,'users':mesh.users,'vertices':len(mesh.vertices),
                      'edges':len(mesh.edges),'faces':len(mesh.polygons),
                      'materials':[getattr(m,'name',None) for m in mesh.materials],
                      'face_material_counts':dict(Counter(p.material_index for p in mesh.polygons)),
                      'selected_faces':[p.index for p in mesh.polygons if p.select]})
    report['objects'].append(entry)
destination=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else Path('inventario_blender.json')
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('INVENTARIO:',destination)
